"""Tests for the Open Agent Executor."""

import pytest

from homomics_lab.agent.agent_loop import AgentLoopResult
from homomics_lab.agent.open_agent.executor import OpenAgentExecutor
from homomics_lab.agent.open_agent.models import OpenAgentBudget
from homomics_lab.agent.plan.models import DataState, Phase, PlanResult
from homomics_lab.context.working_memory import WorkingMemory
from homomics_lab.skills.models import SkillDefinition, SkillInputSchema
from homomics_lab.skills.registry import SkillRegistry
from homomics_lab.tools.models import ToolDefinition
from homomics_lab.tools.registry import ToolRegistry


class FakeLLM:
    """LLM client that returns a fixed string."""

    def __init__(self, response: str = "fake response"):
        self.response = response
        self.calls = []

    def is_configured(self):
        return True

    async def chat_completion(self, **kwargs):
        self.calls.append(kwargs)
        return self.response

    async def chat_completion_message(self, **kwargs):
        # Not used by executor directly, but AgentLoop may call it.
        from types import SimpleNamespace

        return SimpleNamespace(content=self.response, tool_calls=None), {"cost_usd": 0.0}


class FakeSkillExecutor:
    """Captures skill calls and returns a canned result."""

    def __init__(self, result=None):
        self.result = result or {"success": True, "value": 42}
        self.calls = []

    async def execute(self, skill_id: str, inputs: dict):
        self.calls.append((skill_id, inputs))
        return self.result


class FakeTrace:
    trace_id = "trace-1"


class FakeTraceStore:
    async def start_trace(self, **kwargs):
        return FakeTrace()

    async def add_node(self, **kwargs):
        pass

    async def update_node(self, **kwargs):
        pass


def _make_phase(step_type: str, params: dict = None) -> Phase:
    return Phase(
        phase_type=step_type,
        parameters={"open_agent_step_type": step_type, **(params or {})},
    )


def _make_plan(*phases: Phase) -> PlanResult:
    return PlanResult(
        phases=list(phases),
        strategy_name="open-agent",
        data_state=DataState(),
        derivation="open-agent",
    )


@pytest.fixture
def tool_registry():
    reg = ToolRegistry()
    reg.register(
        ToolDefinition(
            name="web_search",
            description="Search the web",
            input_schema={"type": "object"},
            source="builtin",
        )
    )
    return reg


@pytest.fixture
def skill_registry():
    reg = SkillRegistry()
    reg.register(
        SkillDefinition(
            id="demo-skill",
            name="demo-skill",
            version="1.0",
            category="test",
            description="A demo skill",
            input_schema=SkillInputSchema(),
        )
    )
    return reg


@pytest.mark.asyncio
async def test_summarize_phase_returns_direct_response():
    llm = FakeLLM("This is the final summary.")
    executor = OpenAgentExecutor(llm_client=llm)
    plan = _make_plan(_make_phase("summarize"))
    working_memory = WorkingMemory()

    result = await executor.execute(plan, "hello", working_memory)

    assert result.mode == "direct_response"
    assert result.response_text == "This is the final summary."
    assert working_memory.messages[-1].sender == "agent"
    assert len(llm.calls) == 1


@pytest.mark.asyncio
async def test_execute_skill_phase_uses_injected_executor(skill_registry):
    skill_executor = FakeSkillExecutor({"success": True, "value": 42})
    executor = OpenAgentExecutor(
        skill_registry=skill_registry,
        skill_executor=skill_executor,
    )
    plan = _make_plan(
        _make_phase(
            "execute_skill",
            {
                "skill_intents": [
                    {"skill_id": "demo-skill", "inputs": {"x": 1}, "reason": "test"}
                ]
            },
        )
    )

    result = await executor.execute(plan, "run demo skill", WorkingMemory())

    assert skill_executor.calls == [("demo-skill", {"x": 1})]
    assert result.mode == "direct_response"
    assert "42" in result.response_text


@pytest.mark.asyncio
async def test_code_act_phase_runs_generated_code(monkeypatch):
    async def fake_run_code_act(*args, **kwargs):
        return {"success": True, "result": "computed output"}

    monkeypatch.setattr(
        "homomics_lab.agent.open_agent.executor.run_code_act", fake_run_code_act
    )

    executor = OpenAgentExecutor()
    plan = _make_plan(
        _make_phase(
            "code_act",
            {"code_task": "add 1 + 1", "code_language": "python"},
        )
    )

    result = await executor.execute(plan, "compute", WorkingMemory())

    assert result.mode == "direct_response"
    assert "computed output" in result.response_text


@pytest.mark.asyncio
async def test_explore_phase_uses_agent_loop(tool_registry, monkeypatch):
    async def fake_loop_run(*args, **kwargs):
        return AgentLoopResult(
            response_text="explored the web",
            llm_calls=1,
            tool_calls_count=2,
            cost_usd=0.01,
            tool_calls=[],
        )

    monkeypatch.setattr(
        "homomics_lab.agent.open_agent.executor.AgentLoop.run", fake_loop_run
    )

    executor = OpenAgentExecutor(
        llm_client=FakeLLM("unused"),
        tool_registry=tool_registry,
    )
    plan = _make_plan(
        _make_phase(
            "explore",
            {"tool_intents": [{"tool_name": "web_search", "inputs": {}, "reason": "search"}]},
        )
    )

    result = await executor.execute(plan, "search", WorkingMemory())

    assert result.mode == "direct_response"
    assert result.response_text == "explored the web"


@pytest.mark.asyncio
async def test_repeated_errors_escalate_to_hitl(monkeypatch):
    async def failing_code_act(*args, **kwargs):
        raise RuntimeError("simulated code failure")

    monkeypatch.setattr(
        "homomics_lab.agent.open_agent.executor.run_code_act", failing_code_act
    )

    executor = OpenAgentExecutor()
    plan = _make_plan(
        _make_phase("code_act", {"code_task": "task 1"}),
        _make_phase("code_act", {"code_task": "task 2"}),
    )

    result = await executor.execute(plan, "run failing code", WorkingMemory())

    assert result.mode == "awaiting_hitl"
    assert result.hitl_checkpoint is not None
    assert "repeated errors" in result.hitl_checkpoint.context_summary.lower()


@pytest.mark.asyncio
async def test_budget_stops_execution():
    llm = FakeLLM("reasoning output")
    executor = OpenAgentExecutor(
        llm_client=llm,
        budget=OpenAgentBudget(max_llm_calls=1),
    )
    plan = _make_plan(
        _make_phase("reason", {"description": "reason 1"}),
        _make_phase("reason", {"description": "reason 2"}),
    )

    result = await executor.execute(plan, "think twice", WorkingMemory())

    assert len(result.phase_outputs) == 1
    assert "执行已停止" in result.response_text
    assert "LLM call budget" in result.response_text


@pytest.mark.asyncio
async def test_offline_fallback_when_llm_not_configured():
    executor = OpenAgentExecutor(llm_client=None)
    plan = _make_plan(_make_phase("summarize"))

    result = await executor.execute(plan, "summarize without llm", WorkingMemory())

    assert result.mode == "direct_response"
    assert "未配置 LLM" in result.response_text


@pytest.mark.asyncio
async def test_trace_store_records_phases():
    trace_store = FakeTraceStore()
    executor = OpenAgentExecutor(
        llm_client=FakeLLM("final"),
        trace_store=trace_store,
    )
    plan = _make_plan(_make_phase("summarize"))

    result = await executor.execute(
        plan,
        "traced request",
        WorkingMemory(),
        context={"trace_id": "existing-trace"},
    )

    assert result.trace_id == "trace-1"
    assert result.mode == "direct_response"
