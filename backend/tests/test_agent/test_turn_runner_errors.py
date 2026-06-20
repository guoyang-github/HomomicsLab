"""Tests for structured error handling in TurnRunner."""

import pytest

from homomics_lab.agent.errors import ExecutionError, IntentError
from homomics_lab.agent.intent_analyzer import UserIntent
from homomics_lab.agent.turn_runner import ExecutionMode, TurnRunner
from homomics_lab.context.working_memory import WorkingMemory


class FakeAnalyzer:
    def __init__(self, exc=None, intent=None):
        self.exc = exc
        self.intent = intent

    async def analyze(self, *args, **kwargs):
        if self.exc is not None:
            raise self.exc
        return self.intent or UserIntent(analysis_type="qa", complexity="direct_response")


@pytest.mark.asyncio
async def test_retryable_intent_error_produces_structured_result():
    analyzer = FakeAnalyzer(exc=IntentError("Cannot understand"))
    runner = TurnRunner(intent_analyzer=analyzer)
    wm = WorkingMemory()
    result = await runner.run_turn(
        session_id="s1",
        user_message="???",
        working_memory=wm,
        project_id="p1",
    )
    assert result.mode == ExecutionMode.ERROR
    assert "Cannot understand" in result.response_text
    assert result.agent_message is not None
    content = result.agent_message.content
    assert content["error"]["recovery_action"] == "clarify"


@pytest.mark.asyncio
async def test_unexpected_analyzer_error_wrapped_as_intent_error():
    analyzer = FakeAnalyzer(exc=RuntimeError("boom"))
    runner = TurnRunner(intent_analyzer=analyzer)
    wm = WorkingMemory()
    result = await runner.run_turn(
        session_id="s1",
        user_message="hi",
        working_memory=wm,
        project_id="p1",
    )
    assert result.mode == ExecutionMode.ERROR
    assert "boom" in result.response_text
    assert result.agent_message.content["error"]["error_type"] == "IntentError"


def test_turn_error_to_payload():
    err = ExecutionError("exec failed")
    payload = err.to_payload()
    assert payload["message"] == "exec failed"
    assert payload["recovery_action"] == "retry"
    assert payload["retryable"] is True
