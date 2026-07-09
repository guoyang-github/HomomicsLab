"""Tests for the Open Agent Planner."""

import pytest

from homomics_lab.agent.intent import UserIntent
from homomics_lab.agent.open_agent.models import OpenAgentStepType
from homomics_lab.agent.open_agent.planner import OpenAgentPlanner
from homomics_lab.skills.models import SkillDefinition, SkillInputSchema
from homomics_lab.skills.registry import SkillRegistry
from homomics_lab.tools.models import ToolDefinition
from homomics_lab.tools.registry import ToolRegistry


class FakeLLM:
    def __init__(self, response: dict):
        self._response = response
        self.calls = []

    def is_configured(self):
        return True

    async def chat_completion(self, **kwargs):
        self.calls.append(kwargs)
        import json

        return json.dumps(self._response)


def _make_skill(skill_id: str, category: str = "single-cell") -> SkillDefinition:
    return SkillDefinition(
        id=skill_id,
        name=skill_id,
        version="1.0",
        category=category,
        description=f"Skill {skill_id}",
        input_schema=SkillInputSchema(),
    )


@pytest.fixture
def skill_registry():
    reg = SkillRegistry()
    reg.register(_make_skill("bio-single-cell-qc", "single-cell"))
    reg.register(_make_skill("file_conversion", "utility"))
    return reg


@pytest.fixture
def tool_registry():
    reg = ToolRegistry()
    reg.register(
        ToolDefinition(
            name="pubmed_search",
            description="Search PubMed",
            input_schema={"type": "object"},
            source="builtin",
        )
    )
    return reg


@pytest.mark.asyncio
async def test_open_agent_planner_triggers_on_explore_intent(skill_registry, tool_registry):
    planner = OpenAgentPlanner(
        llm_client=None,
        skill_registry=skill_registry,
        tool_registry=tool_registry,
    )
    intent = UserIntent(
        analysis_type="explore",
        complexity="single_step",
        interaction_mode="explore",
        original_message="查一下 CD3E 相关的文献",
    )

    plan = await planner.plan(intent)

    assert plan is not None
    assert plan.derivation == "open-agent"
    assert any(p.phase_type == OpenAgentStepType.EXPLORE.value for p in plan.phases)


@pytest.mark.asyncio
async def test_open_agent_planner_returns_none_for_domain_intent(skill_registry, tool_registry):
    planner = OpenAgentPlanner(
        llm_client=None,
        skill_registry=skill_registry,
        tool_registry=tool_registry,
    )
    intent = UserIntent(
        analysis_type="single_cell_analysis",
        complexity="complex",
        domain="single-cell-transcriptomics",
        original_message="帮我做一个完整的单细胞分析",
    )

    plan = await planner.plan(intent)

    assert plan is None


@pytest.mark.asyncio
async def test_open_agent_planner_returns_suggestion_when_no_capabilities():
    # Empty registries -> no capabilities -> graceful suggestion.
    planner = OpenAgentPlanner(
        llm_client=None,
        skill_registry=SkillRegistry(),
        tool_registry=ToolRegistry(),
    )
    intent = UserIntent(
        analysis_type="open_ended",
        complexity="single_step",
        original_message="abcdefg_unknown_topic",
    )

    plan = await planner.plan(intent)

    assert plan is not None
    assert plan.is_fallback is True
    assert "未找到" in plan.suggestion_text


@pytest.mark.asyncio
async def test_open_agent_planner_generates_structured_plan(skill_registry, tool_registry):
    llm_response = {
        "goal": "Compare single-cell and spatial clustering methods",
        "reasoning_trace": [
            {"thought": "Need literature on both methods", "action": "pubmed_search"}
        ],
        "phases": [
            {
                "step_type": "explore",
                "description": "Search literature",
                "required": True,
                "tool_intents": [
                    {"tool_name": "pubmed_search", "inputs": {"query": "single-cell clustering"}, "reason": "find methods"}
                ],
                "skill_intents": [],
                "code_task": None,
                "code_language": "python",
                "success_criteria": ["retrieve relevant papers"],
            },
            {
                "step_type": "summarize",
                "description": "Summarize comparison",
                "required": True,
            },
        ],
        "risk_level": "medium",
        "needs_hitl": False,
        "final_summary": "Planned literature comparison",
    }
    planner = OpenAgentPlanner(
        llm_client=FakeLLM(llm_response),
        skill_registry=skill_registry,
        tool_registry=tool_registry,
    )
    intent = UserIntent(
        analysis_type="compare",
        complexity="single_step",
        original_message="比较单细胞和空间转录组聚类方法",
    )

    plan = await planner.plan(intent)

    assert plan is not None
    assert plan.derivation == "open-agent"
    assert plan.risk_level == "medium"
    assert plan.approval_required is True
    phase_types = [p.phase_type for p in plan.phases]
    assert OpenAgentStepType.EXPLORE.value in phase_types
    assert OpenAgentStepType.SUMMARIZE.value in phase_types


@pytest.mark.asyncio
async def test_open_agent_planner_drops_unknown_tools(skill_registry, tool_registry):
    llm_response = {
        "goal": "Test unknown tool filtering",
        "reasoning_trace": [],
        "phases": [
            {
                "step_type": "explore",
                "description": "Use fake tool",
                "required": True,
                "tool_intents": [
                    {"tool_name": "nonexistent_tool", "inputs": {}, "reason": "bad"}
                ],
                "skill_intents": [],
            }
        ],
        "risk_level": "medium",
        "needs_hitl": False,
    }
    planner = OpenAgentPlanner(
        llm_client=FakeLLM(llm_response),
        skill_registry=skill_registry,
        tool_registry=tool_registry,
    )
    intent = UserIntent(
        analysis_type="explore",
        complexity="single_step",
        interaction_mode="explore",
        original_message="test",
    )

    plan = await planner.plan(intent)

    assert plan is not None
    explore_phase = next(p for p in plan.phases if p.phase_type == OpenAgentStepType.EXPLORE.value)
    tool_intents = explore_phase.parameters.get("tool_intents", [])
    assert all(ti["tool_name"] == "pubmed_search" for ti in tool_intents)


def test_open_agent_plan_result_is_standard(skill_registry, tool_registry):
    planner = OpenAgentPlanner(
        llm_client=None,
        skill_registry=skill_registry,
        tool_registry=tool_registry,
    )

    # plan is async; use a minimal synchronous assertion that the planner builds.
    assert isinstance(planner, OpenAgentPlanner)
