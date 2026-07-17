"""Tests for IntentRouter helpers."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from homomics_lab.agent.intent.models import UserIntent
from homomics_lab.agent.turn_intent_router import IntentRouter


def test_build_initial_progress_uses_display_steps():
    tree = SimpleNamespace(
        tasks=[
            SimpleNamespace(
                id="t1",
                name="annotation",
                description="Run CellTypist",
                phase="annotation",
            )
        ],
        display_steps=[
            SimpleNamespace(
                id="ds_1",
                description="Annotate cells with CellTypist",
                phase_type="annotation",
                analysis_type="annotation",
            ),
            SimpleNamespace(
                id="ds_2",
                description="Compare predicted labels with existing annotations",
                phase_type="annotation",
                analysis_type="label_comparison",
            ),
        ],
    )
    progress, tasks = IntentRouter.build_initial_progress(tree)
    assert progress["total"] == 2
    assert len(tasks) == 2
    assert tasks[0]["analysis_type"] == "annotation"
    assert tasks[1]["analysis_type"] == "label_comparison"


def test_build_initial_progress_falls_back_to_tasks():
    tree = SimpleNamespace(
        tasks=[
            SimpleNamespace(
                id="t1",
                name="qc",
                description="Quality control",
                phase="qc",
            )
        ],
        display_steps=[],
    )
    progress, tasks = IntentRouter.build_initial_progress(tree)
    assert progress["total"] == 1
    assert len(tasks) == 1
    assert tasks[0]["name"] == "qc"


# ---------------------------------------------------------------------------
# Turn-level progress events + preflight call-point tests
# ---------------------------------------------------------------------------


class _SentinelError(Exception):
    pass


def _make_execute_intent(message: str = "run qc on sample.h5ad") -> UserIntent:
    return UserIntent(
        analysis_type="single_cell_qc",
        complexity="complex",
        original_message=message,
        interaction_mode="execute",
        domain="single-cell-transcriptomics",
    )


@pytest.mark.asyncio
async def test_emit_turn_event_forwards_to_runner_callback():
    events = []

    async def cb(payload):
        events.append(payload)

    runner = SimpleNamespace(_event_callback=cb)
    router = IntentRouter(runner)
    await router._emit_turn_event({"type": "planning", "message": "规划开始"})
    assert events == [{"type": "planning", "message": "规划开始"}]


@pytest.mark.asyncio
async def test_emit_turn_event_swallows_callback_errors():
    async def cb(payload):
        raise RuntimeError("ws dead")

    runner = SimpleNamespace(_event_callback=cb)
    router = IntentRouter(runner)
    # Must not raise: event delivery never breaks routing.
    await router._emit_turn_event({"type": "planning"})


@pytest.mark.asyncio
async def test_emit_turn_event_noop_without_callback():
    router = IntentRouter(SimpleNamespace(_event_callback=None))
    await router._emit_turn_event({"type": "planning"})


@pytest.mark.asyncio
async def test_planning_event_fires_before_preflight_on_execute_path():
    """The 'planning' progress event is pushed before DataPreflight runs."""
    order = []

    async def cb(payload):
        if payload.get("type") == "planning":
            order.append("planning")

    class FakePreflight:
        def __init__(self, llm_client):
            pass

        async def run(self, **kwargs):
            order.append("preflight")
            from homomics_lab.agent.data_preflight import PreflightResult

            return PreflightResult()

    class FakeDecomposer:
        async def decompose_with_plan(self, intent, context=None):
            raise _SentinelError("stop after preflight")

    runner = SimpleNamespace(
        _event_callback=cb,
        _llm_client=None,
        _tool_registry=None,
        task_decomposer=FakeDecomposer(),
    )
    router = IntentRouter(runner)

    with patch(
        "homomics_lab.agent.turn_intent_router.DataPreflight", FakePreflight
    ):
        with pytest.raises(_SentinelError):
            await router.route(
                intent=_make_execute_intent(),
                user_message="run qc on sample.h5ad",
                working_memory=SimpleNamespace(),
                project_id="proj_no_such_project",
                session_id="sess_1",
                plan_store=None,
                job_service=None,
                enqueue_skills=False,
            )

    assert order == ["planning", "preflight"]


@pytest.mark.asyncio
async def test_planning_event_omitted_without_callback_execute_path_still_works():
    """Without an event callback the execute path is unchanged (no crash)."""

    class FakeDecomposer:
        async def decompose_with_plan(self, intent, context=None):
            raise _SentinelError("stop after preflight")

    runner = SimpleNamespace(
        _event_callback=None,
        _llm_client=None,
        _tool_registry=None,
        task_decomposer=FakeDecomposer(),
    )
    router = IntentRouter(runner)
    with pytest.raises(_SentinelError):
        await router.route(
            intent=_make_execute_intent(),
            user_message="run qc on sample.h5ad",
            working_memory=SimpleNamespace(),
            project_id="proj_no_such_project",
            session_id="sess_1",
            plan_store=None,
            job_service=None,
            enqueue_skills=False,
        )


def test_exploration_gate_uses_precomputed_project_has_data():
    """The gate accepts a precomputed data scan (gathered concurrently)."""
    router = IntentRouter(SimpleNamespace(_event_callback=None))
    intent = UserIntent(
        analysis_type="single_cell",
        complexity="complex",
        original_message="为什么这些细胞聚在一起？",
        interaction_mode="execute",
    )
    with patch(
        "homomics_lab.agent.turn_intent_router.settings"
    ) as mock_settings:
        mock_settings.exploration_enabled = True
        # Without the precomputed flag a project with no data returns False;
        # passing project_has_data=True must skip the filesystem scan.
        with patch.object(
            IntentRouter, "_project_has_data_files", side_effect=AssertionError("scanned")
        ):
            assert (
                router._should_route_to_exploration(
                    intent, "为什么这些细胞聚在一起？", [], "proj_x", True
                )
                is True
            )
