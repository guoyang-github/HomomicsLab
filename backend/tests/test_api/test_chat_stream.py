"""Tests for the chat session WebSocket registry and turn-event streaming."""

import pytest
from types import SimpleNamespace
from unittest.mock import patch

from homomics_lab.api import chat as chat_module
from homomics_lab.api.chat import (
    SendMessageRequest,
    _broadcast_to_session,
    _has_session_listeners,
    _make_turn_event_callback,
    _register_session_socket,
    _unregister_session_socket,
    send_message,
)


class FakeSocket:
    """Minimal WebSocket stand-in recording pushed payloads."""

    def __init__(self, fail: bool = False):
        self.sent = []
        self.fail = fail

    async def send_json(self, payload):
        if self.fail:
            raise RuntimeError("socket dead")
        self.sent.append(payload)


@pytest.fixture(autouse=True)
def clean_registry():
    chat_module._session_sockets.clear()
    yield
    chat_module._session_sockets.clear()


def test_register_unregister_session_socket():
    ws = FakeSocket()
    assert not _has_session_listeners("s1")
    _register_session_socket("s1", ws)
    assert _has_session_listeners("s1")
    _unregister_session_socket("s1", ws)
    assert not _has_session_listeners("s1")
    # Unregistering twice / unknown sessions is a no-op.
    _unregister_session_socket("s1", ws)
    _unregister_session_socket("unknown", ws)


@pytest.mark.asyncio
async def test_broadcast_drops_dead_sockets_and_keeps_alive_ones():
    dead = FakeSocket(fail=True)
    alive = FakeSocket()
    _register_session_socket("s1", dead)
    _register_session_socket("s1", alive)

    await _broadcast_to_session("s1", {"type": "token", "token": "hi"})

    assert alive.sent == [{"type": "token", "token": "hi"}]
    # The dead socket was evicted from the registry.
    remaining = chat_module._session_sockets.get("s1")
    assert remaining == {alive}


@pytest.mark.asyncio
async def test_broadcast_noop_without_listeners():
    # Must not raise when no socket is registered.
    await _broadcast_to_session("nobody", {"type": "token", "token": "x"})


@pytest.mark.asyncio
async def test_turn_event_callback_maps_answer_tokens_to_token_contract():
    ws = FakeSocket()
    _register_session_socket("s1", ws)
    cb = _make_turn_event_callback("s1")

    await cb({"type": "answer_token", "token": "Hel"})
    await cb({"type": "answer_token", "token": "lo"})
    await cb({"type": "answer_done"})

    assert ws.sent == [
        {"type": "token", "token": "Hel"},
        {"type": "token", "token": "lo"},
        {"type": "token", "done": True},
    ]


@pytest.mark.asyncio
async def test_turn_event_callback_maps_reset():
    ws = FakeSocket()
    _register_session_socket("s1", ws)
    cb = _make_turn_event_callback("s1")

    await cb({"type": "answer_reset"})

    assert ws.sent == [{"type": "token", "reset": True}]


@pytest.mark.asyncio
async def test_turn_event_callback_wraps_other_events_as_agent_event():
    ws = FakeSocket()
    _register_session_socket("s1", ws)
    cb = _make_turn_event_callback("s1")

    payload = {"type": "planning", "message": "正在分析数据并规划执行步骤…"}
    await cb(payload)

    assert ws.sent == [{"type": "agent_event", "payload": payload}]


def _fake_http_request(working_memory):
    memory_manager = SimpleNamespace()

    async def load_session(session_id, project_id):
        return working_memory, None

    memory_manager.load_session = load_session
    app_state = SimpleNamespace(
        memory_manager=memory_manager,
        tool_registry=None,
        cbkb=None,
        context_engine=None,
        project_state_manager=None,
        llm_client=None,
        capability_index=None,
        analysis_template_store=None,
        workflow_execution_service=None,
        skill_executor=None,
        skill_dag=None,
    )
    return SimpleNamespace(app=SimpleNamespace(state=app_state))


class _FakeTurnRunner:
    """Captures the kwargs passed to run_turn."""

    captured = None

    def __init__(self, **kwargs):
        pass

    async def run_turn(self, **kwargs):
        type(self).captured = kwargs
        return SimpleNamespace(
            mode="completed",
            response_text="ok",
            agent_message=None,
            attachments=[],
            plan_id=None,
            job_id=None,
            task_tree=None,
        )


class _FakeTraceStore:
    async def start_trace(self, **kwargs):
        return None


@pytest.mark.asyncio
async def test_send_passes_event_callback_when_listener_registered():
    from homomics_lab.context.working_memory import WorkingMemory

    ws = FakeSocket()
    _register_session_socket("sess_stream", ws)

    async def fake_resolve(message, project_id, skill_executor):
        return message

    with patch.object(chat_module, "TurnRunner", _FakeTurnRunner), patch.object(
        chat_module, "resolve_chat_references", fake_resolve
    ):
        await send_message(
            SendMessageRequest(
                project_id="proj_1", session_id="sess_stream", message="hi"
            ),
            _fake_http_request(WorkingMemory()),
            job_service=None,
            plan_store=None,
            trace_store=_FakeTraceStore(),
        )

    callback = _FakeTurnRunner.captured.get("event_callback")
    assert callback is not None
    # The callback pushes token frames to the registered listener.
    await callback({"type": "answer_token", "token": "Hel"})
    assert ws.sent == [{"type": "token", "token": "Hel"}]


@pytest.mark.asyncio
async def test_send_omits_event_callback_without_listeners():
    from homomics_lab.context.working_memory import WorkingMemory

    async def fake_resolve(message, project_id, skill_executor):
        return message

    with patch.object(chat_module, "TurnRunner", _FakeTurnRunner), patch.object(
        chat_module, "resolve_chat_references", fake_resolve
    ):
        await send_message(
            SendMessageRequest(
                project_id="proj_1", session_id="sess_plain", message="hi"
            ),
            _fake_http_request(WorkingMemory()),
            job_service=None,
            plan_store=None,
            trace_store=_FakeTraceStore(),
        )

    assert _FakeTurnRunner.captured.get("event_callback") is None


@pytest.mark.asyncio
async def test_send_fire_and_forget_trace_does_not_block_on_slow_trace_store():
    """A slow start_trace must not delay the /send response."""

    import asyncio
    import time

    from homomics_lab.context.working_memory import WorkingMemory

    class SlowTraceStore:
        async def start_trace(self, **kwargs):
            await asyncio.sleep(5)
            return None

    async def fake_resolve(message, project_id, skill_executor):
        return message

    started = time.monotonic()
    with patch.object(chat_module, "TurnRunner", _FakeTurnRunner), patch.object(
        chat_module, "resolve_chat_references", fake_resolve
    ):
        await send_message(
            SendMessageRequest(project_id="proj_1", session_id="sess_slow", message="hi"),
            _fake_http_request(WorkingMemory()),
            job_service=None,
            plan_store=None,
            trace_store=SlowTraceStore(),
        )
    elapsed = time.monotonic() - started
    assert elapsed < 2, f"/send blocked on start_trace for {elapsed:.2f}s"
