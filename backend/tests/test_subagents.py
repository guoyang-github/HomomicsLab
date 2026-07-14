"""Tests for the specialist + critic sub-agent layer."""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import pytest

from homomics_lab.agent.agent_loop import AgentLoopResult
from homomics_lab.agent.progress_events import (
    MAX_EVENT_ERROR_CHARS,
    MAX_EVENT_OUTPUT_CHARS,
    build_agent_event,
    parent_context_fields,
    subagent_actor,
)
from homomics_lab.agent.subagents import (
    CriticAgent,
    SpecialistAgent,
    SpecialistCriticOrchestrator,
    filter_tools_by_role,
    read_only_tools,
)
from homomics_lab.hpc.state import ExecutionState
from homomics_lab.skills.agent_executor import AgentSkillExecutor
from homomics_lab.skills.registry import SkillRegistry
from homomics_lab.skills.runtime import SkillRuntimeExecutor


class FakeTool:
    def __init__(self, name, risk_level="low"):
        self.name = name
        self.risk_level = risk_level


class FakeRegistry:
    def __init__(self, tools):
        self._tools = tools

    def list_all(self):
        return self._tools


@dataclass
class FakeRole:
    role_id: str
    name: str
    allowed_tools: List[str]
    allowed_skills: List[str]


class FakeLoop:
    def __init__(self, response_text: str):
        self.response_text = response_text

    async def run(self, **kwargs):
        return AgentLoopResult(response_text=self.response_text)


def fake_loop_factory(response_text: str):
    def _factory(*args, **kwargs):
        return FakeLoop(response_text)
    return _factory


def test_filter_tools_by_role_allows_skills_and_tools():
    registry = FakeRegistry([
        FakeTool("file_read"),
        FakeTool("bio-single-cell-annotation-celltypist"),
        FakeTool("bio-spatial-transcriptomics-preprocessing"),
        FakeTool("shell_exec", "high"),
    ])
    role = FakeRole(
        role_id="sc",
        name="Single-Cell Specialist",
        allowed_tools=["file_read"],
        allowed_skills=["bio-single-cell-*"],
    )
    names = filter_tools_by_role(registry, role)
    assert "file_read" in names
    assert "bio-single-cell-annotation-celltypist" in names
    assert "bio-spatial-transcriptomics-preprocessing" not in names
    assert "shell_exec" not in names  # role restrictions do not include shell_exec


def test_read_only_tools_exclude_writes():
    registry = FakeRegistry([
        FakeTool("file_read"),
        FakeTool("web_search"),
        FakeTool("file_write"),
        FakeTool("shell_exec", "high"),
        FakeTool("bio-x", "medium"),
    ])
    names = read_only_tools(registry)
    assert set(names) == {"file_read", "web_search"}


@pytest.mark.asyncio
async def test_specialist_returns_loop_output():
    agent = SpecialistAgent(
        llm_client=None,
        tool_registry=FakeRegistry([FakeTool("file_read"), FakeTool("bio-x")]),
        role=FakeRole("sc", "SC", ["file_read"], ["bio-*"]),
        loop_factory=fake_loop_factory("Looks good."),
    )
    result = await agent.review_plan("do QC", {"phases": []})
    assert result.response_text == "Looks good."
    assert result.metadata["role"] == "sc"


@pytest.mark.asyncio
async def test_critic_parses_json_review():
    response = (
        '{"action": "revise", "summary": "Missing QC", '
        '"concerns": ["no QC step"], "suggestions": ["add QC"]}'
    )
    agent = CriticAgent(
        llm_client=None,
        tool_registry=FakeRegistry([FakeTool("file_read"), FakeTool("file_write")]),
        loop_factory=fake_loop_factory(response),
    )
    review = await agent.review(
        specialist_output=SimpleNamespace(response_text="Plan A"),
        plan={"phases": []},
        request="analyze",
    )
    assert review.action == "revise"
    assert review.summary == "Missing QC"
    assert review.concerns == ["no QC step"]
    assert review.suggestions == ["add QC"]


@pytest.mark.asyncio
async def test_critic_handles_non_json():
    agent = CriticAgent(
        llm_client=None,
        tool_registry=FakeRegistry([FakeTool("file_read")]),
        loop_factory=fake_loop_factory("I think this is wrong."),
    )
    review = await agent.review(
        specialist_output=SimpleNamespace(response_text="Plan A"),
        plan={"phases": []},
    )
    assert review.action == "ask_user"
    assert review.concerns


@pytest.mark.asyncio
async def test_orchestrator_chains_specialist_and_critic():
    registry = FakeRegistry([FakeTool("file_read"), FakeTool("file_write")])
    orchestrator = SpecialistCriticOrchestrator(
        llm_client=None,
        tool_registry=registry,
        role=FakeRole("sc", "SC", ["file_read"], []),
    )

    def make_loop(response_text: str):
        return fake_loop_factory(response_text)

    orchestrator.specialist.loop_factory = make_loop("Specialist says add QC.")
    orchestrator.critic.loop_factory = make_loop(
        '{"action": "approve", "summary": "Good after QC", "concerns": [], "suggestions": []}'
    )
    review = await orchestrator.review("analyze", {"phases": []})
    assert review.action == "approve"
    assert review.specialist_output.response_text == "Specialist says add QC."


# ---------------------------------------------------------------------------
# Structured progress event contract (homomics_lab.agent.progress_events)
# ---------------------------------------------------------------------------


def test_agent_event_contract_top_level_omits_actor_and_parent():
    event = build_agent_event("tool_start", tool="shell_exec")
    assert event["type"] == "tool_start"
    assert "timestamp" in event
    assert "actor" not in event
    assert "parent_id" not in event


def test_agent_event_contract_child_execution_includes_actor_and_parent():
    event = build_agent_event(
        "tool_end",
        actor=subagent_actor("bio-x"),
        parent_id="job-1",
        tool="shell_exec",
        success=True,
        output="o" * (MAX_EVENT_OUTPUT_CHARS + 500),
        error_message="e" * (MAX_EVENT_ERROR_CHARS + 500),
    )
    assert event["actor"] == "subagent:bio-x"
    assert event["parent_id"] == "job-1"
    assert len(event["output"]) == MAX_EVENT_OUTPUT_CHARS
    assert len(event["error_message"]) == MAX_EVENT_ERROR_CHARS


def test_parent_context_fields_are_all_or_nothing():
    assert parent_context_fields("subagent:x", "job-1") == {
        "actor": "subagent:x",
        "parent_id": "job-1",
    }
    assert parent_context_fields(None, "job-1") == {}
    assert parent_context_fields("subagent:x", None) == {}


def test_execution_state_attribution_round_trip():
    """The SSE payload (ExecutionState.to_dict) is the frontend boundary."""
    top = ExecutionState(job_id="j", status="RUNNING")
    payload = top.to_dict()
    assert "actor" not in payload
    assert "parent_id" not in payload
    assert ExecutionState.from_dict(payload).actor is None

    child = ExecutionState(
        job_id="j", status="COMPLETED", actor="subagent:sk", parent_id="job-1"
    )
    payload = child.to_dict()
    assert payload["actor"] == "subagent:sk"
    assert payload["parent_id"] == "job-1"
    restored = ExecutionState.from_dict(payload)
    assert restored.actor == "subagent:sk"
    assert restored.parent_id == "job-1"


# ---------------------------------------------------------------------------
# Agent loop fakes (shared by the model-selection and event tests below)
# ---------------------------------------------------------------------------


class _Result:
    def __init__(self, success=True, output=None, error_message=None) -> None:
        self.success = success
        self.output = output if output is not None else {}
        self.error_message = error_message


def _tool_def(name: str) -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        description=f"fake {name}",
        input_schema={},
        risk_level="low",
    )


class _FakeToolRegistry:
    def __init__(self, working_dir: Path) -> None:
        self.working_dir = working_dir

    def list_all(self) -> List[SimpleNamespace]:
        return [_tool_def("file_write"), _tool_def("shell_exec"), _tool_def("file_list")]

    def get(self, name: str) -> Optional[SimpleNamespace]:
        if name in {"file_write", "shell_exec", "file_list"}:
            return _tool_def(name)
        return None

    async def invoke_async(self, name: str, arguments: Dict[str, Any]) -> _Result:
        return _Result(output={"stdout": "ok"})


class _StubRouter:
    """Stand-in for LLMRouter that records select() calls."""

    def __init__(self, decision: Any = None, exc: Optional[Exception] = None) -> None:
        self.calls: List[Dict[str, Any]] = []
        self._decision = decision
        self._exc = exc

    def select(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self._exc is not None:
            raise self._exc
        return self._decision


class _FakeLLM:
    def __init__(self, responses: List[str], router: Any = None) -> None:
        self._responses = list(responses)
        self.router = router
        self.call_kwargs: List[Dict[str, Any]] = []

    def is_configured(self) -> bool:
        return True

    async def chat_completion(self, messages: Any, **kwargs: Any) -> str:
        self.call_kwargs.append(kwargs)
        if self._responses:
            return self._responses.pop(0)
        return '{"action":"final","final_output":{"ok":true}}'


def _agent_skill(metadata: Optional[Dict[str, Any]] = None) -> SimpleNamespace:
    base = {
        "instructions": "produce outputs",
        "allowed_tools": ["file_write", "shell_exec", "file_list"],
    }
    base.update(metadata or {})
    return SimpleNamespace(
        id="test-skill",
        description="test",
        metadata=base,
        runtime=SimpleNamespace(type="agent"),
        output_schema=None,
        source_dir=None,
        has_scripts=False,
    )


def _run_executor(executor: AgentSkillExecutor, skill: Any, working_dir: Path) -> Dict[str, Any]:
    return asyncio.run(executor.execute(skill, inputs={}, working_dir=working_dir))


# ---------------------------------------------------------------------------
# Per-skill model selection (model / model_tier -> LLMRouter -> chat kwargs)
# ---------------------------------------------------------------------------


def test_model_tier_resolves_through_router_and_pins_chat_model(tmp_path: Path) -> None:
    decision = SimpleNamespace(
        model="deepseek-coder",
        reason="catalog:code_generation:best capability match for code_generation",
    )
    router = _StubRouter(decision=decision)
    llm = _FakeLLM(
        responses=[
            '{"action":"tool","tool":"file_list","arguments":{"directory":"."}}',
            '{"action":"final","final_output":{"ok":true}}',
        ],
        router=router,
    )
    ex = AgentSkillExecutor(
        tool_registry=_FakeToolRegistry(tmp_path), llm_client=llm, max_iterations=5
    )
    result = _run_executor(ex, _agent_skill({"model_tier": "coding"}), tmp_path)

    assert result["success"] is True
    assert router.calls == [{"task_type": "code_generation", "prefer_cheap": False}]
    assert llm.call_kwargs
    for kwargs in llm.call_kwargs:
        assert kwargs.get("model") == "deepseek-coder"
        # Complexity routing must be skipped so the pinned model wins.
        assert "intent_type" not in kwargs


def test_model_tier_cheap_requests_prefer_cheap(tmp_path: Path) -> None:
    decision = SimpleNamespace(model="gpt-4o-mini", reason="cheap")
    router = _StubRouter(decision=decision)
    llm = _FakeLLM(
        responses=[
            '{"action":"tool","tool":"file_list","arguments":{"directory":"."}}',
            '{"action":"final","final_output":{"ok":true}}',
        ],
        router=router,
    )
    ex = AgentSkillExecutor(
        tool_registry=_FakeToolRegistry(tmp_path), llm_client=llm, max_iterations=3
    )
    _run_executor(ex, _agent_skill({"model_tier": "cheap"}), tmp_path)

    assert router.calls == [{"task_type": "cheap", "prefer_cheap": True}]
    assert all(k.get("model") == "gpt-4o-mini" for k in llm.call_kwargs)


def test_model_key_accepts_tier_alias(tmp_path: Path) -> None:
    decision = SimpleNamespace(model="qwen-turbo", reason="cheap")
    router = _StubRouter(decision=decision)
    llm = _FakeLLM(
        responses=[
            '{"action":"tool","tool":"file_list","arguments":{"directory":"."}}',
            '{"action":"final","final_output":{"ok":true}}',
        ],
        router=router,
    )
    ex = AgentSkillExecutor(
        tool_registry=_FakeToolRegistry(tmp_path), llm_client=llm, max_iterations=3
    )
    _run_executor(ex, _agent_skill({"model": "cheap"}), tmp_path)

    assert router.calls == [{"task_type": "cheap", "prefer_cheap": True}]
    assert all(k.get("model") == "qwen-turbo" for k in llm.call_kwargs)


def test_explicit_model_is_validated_and_pinned(tmp_path: Path) -> None:
    decision = SimpleNamespace(model="gpt-4o", reason="explicit")
    router = _StubRouter(decision=decision)
    llm = _FakeLLM(
        responses=[
            '{"action":"tool","tool":"file_list","arguments":{"directory":"."}}',
            '{"action":"final","final_output":{"ok":true}}',
        ],
        router=router,
    )
    ex = AgentSkillExecutor(
        tool_registry=_FakeToolRegistry(tmp_path), llm_client=llm, max_iterations=3
    )
    _run_executor(ex, _agent_skill({"model": "gpt-4o"}), tmp_path)

    assert router.calls == [{"model": "gpt-4o"}]
    assert all(k.get("model") == "gpt-4o" for k in llm.call_kwargs)


def test_unknown_model_tier_falls_back_to_default_with_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    router = _StubRouter(decision=SimpleNamespace(model="x", reason="catalog:cheap"))
    llm = _FakeLLM(
        responses=[
            '{"action":"tool","tool":"file_list","arguments":{"directory":"."}}',
            '{"action":"final","final_output":{"ok":true}}',
        ],
        router=router,
    )
    ex = AgentSkillExecutor(
        tool_registry=_FakeToolRegistry(tmp_path), llm_client=llm, max_iterations=3
    )
    with caplog.at_level("WARNING", logger="homomics_lab.skills.agent_executor"):
        result = _run_executor(ex, _agent_skill({"model_tier": "bogus"}), tmp_path)

    assert result["success"] is True
    assert router.calls == []  # never consulted for an unknown tier
    assert all(
        k.get("intent_type") == "code_generation" and "model" not in k
        for k in llm.call_kwargs
    )
    assert any("unknown model_tier" in r.message for r in caplog.records)


def test_router_failure_falls_back_to_default_with_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    router = _StubRouter(exc=RuntimeError("no provider configured"))
    llm = _FakeLLM(
        responses=[
            '{"action":"tool","tool":"file_list","arguments":{"directory":"."}}',
            '{"action":"final","final_output":{"ok":true}}',
        ],
        router=router,
    )
    ex = AgentSkillExecutor(
        tool_registry=_FakeToolRegistry(tmp_path), llm_client=llm, max_iterations=3
    )
    with caplog.at_level("WARNING", logger="homomics_lab.skills.agent_executor"):
        result = _run_executor(ex, _agent_skill({"model_tier": "reasoning"}), tmp_path)

    assert result["success"] is True
    assert len(router.calls) == 1
    assert all(
        k.get("intent_type") == "code_generation" and "model" not in k
        for k in llm.call_kwargs
    )
    assert any("Failed to resolve model_tier" in r.message for r in caplog.records)


def test_unconfigured_explicit_model_falls_back_with_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    # Router returns a different model: the requested one is not served by any
    # configured provider, so default routing must be used.
    decision = SimpleNamespace(model="gpt-4o-mini", reason="primary")
    router = _StubRouter(decision=decision)
    llm = _FakeLLM(
        responses=[
            '{"action":"tool","tool":"file_list","arguments":{"directory":"."}}',
            '{"action":"final","final_output":{"ok":true}}',
        ],
        router=router,
    )
    ex = AgentSkillExecutor(
        tool_registry=_FakeToolRegistry(tmp_path), llm_client=llm, max_iterations=3
    )
    with caplog.at_level("WARNING", logger="homomics_lab.skills.agent_executor"):
        _run_executor(ex, _agent_skill({"model": "nonexistent-model"}), tmp_path)

    assert all(
        k.get("intent_type") == "code_generation" and "model" not in k
        for k in llm.call_kwargs
    )
    assert any("no configured provider serves it" in r.message for r in caplog.records)


def test_no_model_declaration_keeps_default_routing(tmp_path: Path) -> None:
    router = _StubRouter(decision=SimpleNamespace(model="x", reason="catalog:cheap"))
    llm = _FakeLLM(
        responses=[
            '{"action":"tool","tool":"file_list","arguments":{"directory":"."}}',
            '{"action":"final","final_output":{"ok":true}}',
        ],
        router=router,
    )
    ex = AgentSkillExecutor(
        tool_registry=_FakeToolRegistry(tmp_path), llm_client=llm, max_iterations=3
    )
    _run_executor(ex, _agent_skill(), tmp_path)

    assert router.calls == []
    assert all(
        k.get("intent_type") == "code_generation" and "model" not in k
        for k in llm.call_kwargs
    )


# ---------------------------------------------------------------------------
# Subagent attribution on progress events
# ---------------------------------------------------------------------------


def _collect_states(executor: AgentSkillExecutor, skill: Any, working_dir: Path) -> List[ExecutionState]:
    states: List[ExecutionState] = []
    executor.progress_callback = states.append
    _run_executor(executor, skill, working_dir)
    return states


def test_child_execution_events_carry_actor_and_parent_id(tmp_path: Path) -> None:
    llm = _FakeLLM(
        responses=[
            '{"action":"tool","tool":"file_list","arguments":{"directory":"."}}',
            '{"action":"final","final_output":{"ok":true}}',
        ]
    )
    ex = AgentSkillExecutor(
        tool_registry=_FakeToolRegistry(tmp_path),
        llm_client=llm,
        max_iterations=5,
        parent_id="job-42",
    )
    states = _collect_states(ex, _agent_skill(), tmp_path)

    assert states
    events: List[Dict[str, Any]] = []
    for state in states:
        # Every state from a child execution is attributed at the top level.
        assert state.actor == "subagent:test-skill"
        assert state.parent_id == "job-42"
        events.extend((state.resource_usage or {}).get("agent_events", []))

    assert events  # tool_start/tool_end at minimum
    for event in events:
        assert event["actor"] == "subagent:test-skill"
        assert event["parent_id"] == "job-42"

    # The SSE payload shape: attribution at the payload top level.
    payload = states[0].to_dict()
    assert payload["actor"] == "subagent:test-skill"
    assert payload["parent_id"] == "job-42"

    # Exactly one terminal state closes the subagent's event group.
    terminal = [s for s in states if s.status in ("COMPLETED", "FAILED")]
    assert len(terminal) == 1
    assert terminal[0].status == "COMPLETED"
    assert terminal[0].actor == "subagent:test-skill"
    assert terminal[0].parent_id == "job-42"


def test_child_execution_failure_emits_failed_terminal(tmp_path: Path) -> None:
    # A tool the skill is not allowed to call -> immediate failure result.
    llm = _FakeLLM(
        responses=['{"action":"tool","tool":"not_a_tool","arguments":{}}']
    )
    ex = AgentSkillExecutor(
        tool_registry=_FakeToolRegistry(tmp_path),
        llm_client=llm,
        max_iterations=3,
        parent_id="job-9",
    )
    states = _collect_states(ex, _agent_skill(), tmp_path)

    terminal = [s for s in states if s.status in ("COMPLETED", "FAILED")]
    assert len(terminal) == 1
    assert terminal[0].status == "FAILED"
    assert terminal[0].actor == "subagent:test-skill"
    assert terminal[0].parent_id == "job-9"


def test_top_level_execution_events_have_no_actor_or_parent_id(tmp_path: Path) -> None:
    llm = _FakeLLM(
        responses=[
            '{"action":"tool","tool":"file_list","arguments":{"directory":"."}}',
            '{"action":"final","final_output":{"ok":true}}',
        ]
    )
    ex = AgentSkillExecutor(
        tool_registry=_FakeToolRegistry(tmp_path), llm_client=llm, max_iterations=5
    )
    states = _collect_states(ex, _agent_skill(), tmp_path)

    assert states
    events: List[Dict[str, Any]] = []
    for state in states:
        # Top-level runs keep the pre-contract shape: no attribution, and no
        # terminal state from the agent loop (the job runner owns lifecycle).
        assert state.actor is None
        assert state.parent_id is None
        assert state.status not in ("COMPLETED", "FAILED")
        payload = state.to_dict()
        assert "actor" not in payload
        assert "parent_id" not in payload
        events.extend((state.resource_usage or {}).get("agent_events", []))

    assert events
    for event in events:
        assert "actor" not in event
        assert "parent_id" not in event


def test_runtime_executor_propagates_parent_job_id_to_agent_loop(tmp_path: Path) -> None:
    executor = SkillRuntimeExecutor(registry=SkillRegistry(), working_dir=tmp_path)
    executor.set_parent_job_id("job-7")
    agent = executor._get_agent_executor()
    assert agent._parent_id == "job-7"
    # Updating the job id after the agent loop was lazily created must propagate.
    executor.set_parent_job_id("job-8")
    assert agent._parent_id == "job-8"


# ---------------------------------------------------------------------------
# Context firewall: driver-script failure errors stay bounded
# ---------------------------------------------------------------------------


def test_script_first_failure_error_is_truncated(tmp_path: Path) -> None:
    source_dir = tmp_path / "skill_src"
    (source_dir / "scripts" / "python").mkdir(parents=True)
    (source_dir / "scripts" / "python" / "core_analysis.py").write_text(
        "def run():\n    return 1\n", encoding="utf-8"
    )
    huge_error = "HEAD\n" + ("traceback line\n" * 5000) + "TAIL: the real failure"
    llm = _FakeLLM(responses=["```python\nprint('hi')\n```"])

    class _FailingRegistry(_FakeToolRegistry):
        async def invoke_async(self, name: str, arguments: Dict[str, Any]) -> _Result:
            return _Result(success=False, error_message=huge_error)

    skill = _agent_skill()
    skill.source_dir = source_dir
    ex = AgentSkillExecutor(
        tool_registry=_FailingRegistry(tmp_path), llm_client=llm, max_iterations=3
    )
    result = asyncio.run(
        ex._script_first_execute(skill, {}, tmp_path / "work", {}, preexisting_files={})
    )

    assert result is not None and result["success"] is False
    error = result["error"]
    assert "Generated driver script failed" in error
    # Bounded well below the raw log, and tail-priority so the actionable
    # final line survives truncation.
    assert len(error) < 3000
    assert "TAIL: the real failure" in error
    assert "[truncated" in error
