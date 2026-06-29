"""Tests for high-risk tool approval and resume in the agent loop."""

import pytest

from homomics_lab.agent.agent_loop import AgentLoop
from homomics_lab.agent.turn_runner import TurnRunner
from homomics_lab.context.working_memory import WorkingMemory
from homomics_lab.models.common import ChatMessage, MessageType
from homomics_lab.tools.approval_store import PersistentApprovalStore
from homomics_lab.tools.models import ToolDefinition
from homomics_lab.tools.registry import ToolRegistry


class _FakeMessage:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []


class _FakeToolCall:
    def __init__(self, id, name, arguments):
        self.id = id
        self.function = _FakeFunction(name, arguments)


class _FakeFunction:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


class _FakeLLM:
    def __init__(self, responses):
        self._responses = list(responses)
        self._idx = 0

    async def chat_completion_message(self, **kwargs):
        if self._idx >= len(self._responses):
            raise RuntimeError("No more fake responses")
        resp = self._responses[self._idx]
        self._idx += 1
        return resp, {"cost_usd": 0.0, "prompt_tokens": 0, "completion_tokens": 0}

    async def chat_completion(self, **kwargs):
        return "Final summary."


@pytest.fixture
def approval_registry(tmp_path):
    reg = ToolRegistry()
    reg.register(
        ToolDefinition(
            name="dangerous_action",
            description="A high-risk action",
            input_schema={
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
            risk_level="high",
            handler=lambda command: {"output": f"executed {command}"},
        )
    )
    return reg


@pytest.mark.asyncio
async def test_tool_approval_resume_executes_after_approval(
    approval_registry, tmp_path
):
    store = PersistentApprovalStore(db_path=tmp_path / "approvals.db")
    llm = _FakeLLM([
        _FakeMessage(tool_calls=[_FakeToolCall("tc1", "dangerous_action", '{"command": "x"}')]),
        _FakeMessage(content="Done."),
    ])
    loop = AgentLoop(
        llm_client=llm,
        tool_registry=approval_registry,
        max_rounds=2,
        approval_store=store,
    )

    result = await loop.run(user_message="run dangerous action", history=[])
    assert result.awaiting_approval is True
    call_id = result.approval_request["call_id"]

    runner = TurnRunner(llm_client=llm, tool_registry=approval_registry, approval_store=store)
    wm = WorkingMemory()
    wm.add_message(ChatMessage(id="m1", type=MessageType.TEXT, content="run dangerous action", sender="user"))
    resume_result = await runner.respond_to_tool_approval(
        call_id=call_id,
        approved=True,
        working_memory=wm,
        project_id="proj_1",
    )

    assert resume_result.mode == "direct_response"
    assert "executed" in resume_result.response_text or "Done" in resume_result.response_text


@pytest.mark.asyncio
async def test_tool_approval_decline_skips_execution(
    approval_registry, tmp_path
):
    store = PersistentApprovalStore(db_path=tmp_path / "approvals.db")
    llm = _FakeLLM([
        _FakeMessage(tool_calls=[_FakeToolCall("tc1", "dangerous_action", '{"command": "x"}')]),
    ])
    loop = AgentLoop(
        llm_client=llm,
        tool_registry=approval_registry,
        max_rounds=2,
        approval_store=store,
    )

    result = await loop.run(user_message="run dangerous action", history=[])
    call_id = result.approval_request["call_id"]

    runner = TurnRunner(llm_client=llm, tool_registry=approval_registry, approval_store=store)
    wm = WorkingMemory()
    resume_result = await runner.respond_to_tool_approval(
        call_id=call_id,
        approved=False,
        working_memory=wm,
        project_id="proj_1",
    )

    assert "拒绝" in resume_result.response_text
