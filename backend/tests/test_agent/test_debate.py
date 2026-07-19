import json

import pytest

from homomics_lab.agent.core.dynamic_agent import DynamicAgent
from homomics_lab.agent.core.role import RoleDefinition
from homomics_lab.agent.debate import (
    DebateOption,
    LightweightDebate,
    LLMDebateJudge,
    RuleBasedDebateJudge,
)
from homomics_lab.llm_client import FakeLLMClient


class ScoredFakeLLMClient(FakeLLMClient):
    """Fake LLM client that returns a per-option-id score based on prompt content."""

    def __init__(self, scores_by_id):
        super().__init__(response="")
        self._scores_by_id = scores_by_id

    async def chat_completion(self, messages, **kwargs):
        prompt = messages[-1]["content"]
        for opt_id, score in self._scores_by_id.items():
            if f"Option ID: {opt_id}" in prompt:
                return json.dumps({"score": score, "reason": "mock"})
        return json.dumps({"score": 0.5, "reason": "mock"})


@pytest.fixture
def expert():
    role = RoleDefinition(role_id="sc", name="Single Cell Expert", allowed_skills=["sc_analysis"])
    return DynamicAgent(role=role)


@pytest.fixture
def experts(expert):
    return [expert]


@pytest.mark.asyncio
async def test_rule_based_judge_direct_skill_match(expert):
    judge = RuleBasedDebateJudge()
    option = DebateOption(id="sc_analysis", label="SC", metadata={"skill": "sc_analysis"})
    score = await judge.score(expert, option, {})
    assert score == pytest.approx(0.9)


@pytest.mark.asyncio
async def test_rule_based_judge_category_match():
    judge = RuleBasedDebateJudge()
    role = RoleDefinition(role_id="cat", name="Category Expert", allowed_skill_categories=["omics"])
    expert = DynamicAgent(role=role)
    option = DebateOption(id="opt", label="Opt", metadata={"category": "omics"})
    score = await judge.score(expert, option, {})
    assert score == pytest.approx(0.7)


@pytest.mark.asyncio
async def test_rule_based_judge_generalist():
    judge = RuleBasedDebateJudge()
    role = RoleDefinition(role_id="gen", name="Generalist")
    expert = DynamicAgent(role=role)
    option = DebateOption(id="opt", label="Opt")
    score = await judge.score(expert, option, {})
    assert score == pytest.approx(0.6)


@pytest.mark.asyncio
async def test_rule_based_judge_no_match(expert):
    judge = RuleBasedDebateJudge()
    option = DebateOption(id="other", label="Other")
    score = await judge.score(expert, option, {})
    assert score == pytest.approx(0.3)


def test_static_score_option_backward_compatibility(expert):
    option = DebateOption(id="sc_analysis", label="SC", metadata={"skill": "sc_analysis"})
    score = LightweightDebate._score_option(expert, option, {})
    assert score == pytest.approx(0.9)


@pytest.mark.asyncio
async def test_llm_judge_returns_llm_score(expert):
    client = FakeLLMClient(response='{"score": 0.85, "reason": "good match"}')
    judge = LLMDebateJudge(llm_client=client)
    option = DebateOption(id="sc_analysis", label="SC", metadata={"skill": "sc_analysis"})
    score = await judge.score(expert, option, {"topic": "test", "user_message": "do sc"})
    assert score == pytest.approx(0.85)


@pytest.mark.asyncio
async def test_llm_judge_falls_back_on_invalid_json(expert):
    client = FakeLLMClient(response="not valid json")
    judge = LLMDebateJudge(llm_client=client)
    option = DebateOption(id="sc_analysis", label="SC", metadata={"skill": "sc_analysis"})
    score = await judge.score(expert, option, {})
    assert score == pytest.approx(0.9)


@pytest.mark.asyncio
async def test_llm_judge_falls_back_on_out_of_range_score(expert):
    client = FakeLLMClient(response='{"score": 1.5, "reason": "too high"}')
    judge = LLMDebateJudge(llm_client=client)
    option = DebateOption(id="sc_analysis", label="SC", metadata={"skill": "sc_analysis"})
    score = await judge.score(expert, option, {})
    assert score == pytest.approx(0.9)


@pytest.mark.asyncio
async def test_lightweight_debate_run_with_rule_judge_produces_recommendation(experts):
    debate = LightweightDebate(experts=experts)
    candidates = [
        {"id": "sc_analysis", "label": "Single Cell", "metadata": {"skill": "sc_analysis"}},
        {"id": "other", "label": "Other"},
    ]
    result = await debate.run("topic", candidates, context={"user_message": "do sc"})
    assert result.recommendation is not None
    assert result.recommendation.id == "sc_analysis"


@pytest.mark.asyncio
async def test_lightweight_debate_run_with_llm_judge_produces_recommendation(experts):
    client = ScoredFakeLLMClient(scores_by_id={"a": 0.95, "b": 0.5})
    judge = LLMDebateJudge(llm_client=client)
    debate = LightweightDebate(experts=experts, judge=judge)
    candidates = [
        {"id": "a", "label": "A"},
        {"id": "b", "label": "B"},
    ]
    result = await debate.run("topic", candidates, context={"user_message": "do sc"})
    assert result.recommendation is not None
    assert result.recommendation.id == "a"


@pytest.mark.asyncio
async def test_lightweight_debate_default_judge_is_rule_based(experts):
    debate = LightweightDebate(experts=experts)
    assert isinstance(debate.judge, RuleBasedDebateJudge)


# --- Expert panel derivation (domain roles → debate experts) -----------------


def _registry_with_sc_role():
    from homomics_lab.domain.models import (
        DomainDefinition,
        DomainIntent,
        DomainRole,
    )
    from homomics_lab.domain.registry import DomainRegistry

    registry = DomainRegistry()
    registry.register(
        DomainDefinition(
            domain="debate-test-domain",
            intents=[
                DomainIntent(analysis_type="debate_test_analysis", keywords=["探针"]),
            ],
            roles=[
                DomainRole(
                    role_id="debate_test_specialist",
                    name="Debate Test Specialist",
                    description="Specialist for the debate test domain.",
                    allowed_skills=["debate-test-skill-*"],
                ),
            ],
        )
    )
    return registry


def test_experts_from_domain_registry_maps_roles():
    from homomics_lab.agent.debate import experts_from_domain_registry

    experts = experts_from_domain_registry(_registry_with_sc_role())
    assert len(experts) == 1
    role = experts[0].role
    assert role.role_id == "debate_test_specialist"
    assert role.name == "Debate Test Specialist"
    # Role skills and the domain's intent analysis types are both linked so
    # the rule judge can ground scores on debate candidates.
    assert "debate-test-skill-*" in role.allowed_skills
    assert "debate_test_analysis" in role.allowed_skills


def test_experts_from_empty_registry_returns_empty():
    from homomics_lab.agent.debate import experts_from_domain_registry
    from homomics_lab.domain.registry import DomainRegistry

    assert experts_from_domain_registry(DomainRegistry()) == []


def test_default_debate_experts_are_generalists():
    from homomics_lab.agent.debate import default_debate_experts

    experts = default_debate_experts()
    assert [e.role.role_id for e in experts] == [
        "methodologist",
        "data_engineer",
        "domain_reviewer",
    ]
    # Generalists: no skill grounding → the rule judge cannot produce a
    # recommendation, and clarification degrades to plain text.
    assert all(not e.role.allowed_skills for e in experts)
    assert all(not e.role.allowed_skill_categories for e in experts)


@pytest.mark.asyncio
async def test_debate_with_domain_experts_produces_recommendation():
    from homomics_lab.agent.debate import experts_from_domain_registry

    experts = experts_from_domain_registry(_registry_with_sc_role())
    debate = LightweightDebate(experts=experts)
    candidates = [
        {
            "id": "debate_test_analysis",
            "label": "Debate Test",
            "metadata": {"skill": "debate_test_analysis"},
        },
        {"id": "other_analysis", "label": "Other", "metadata": {"skill": "other_analysis"}},
    ]
    result = await debate.run("topic", candidates, context={"user_message": "探针"})
    assert result.recommendation is not None
    assert result.recommendation.id == "debate_test_analysis"


@pytest.mark.asyncio
async def test_debate_with_generalist_experts_has_no_recommendation():
    from homomics_lab.agent.debate import default_debate_experts

    debate = LightweightDebate(experts=default_debate_experts())
    candidates = [
        {"id": "a", "label": "A", "metadata": {"skill": "a"}},
        {"id": "b", "label": "B", "metadata": {"skill": "b"}},
    ]
    result = await debate.run("topic", candidates, context={"user_message": "x"})
    assert result.recommendation is None


def test_turn_runner_injects_domain_role_experts_into_debate():
    from homomics_lab.agent.turn_runner import TurnRunner
    from homomics_lab.domain.registry import get_domain_registry

    registry = get_domain_registry()
    domain = _registry_with_sc_role().get("debate-test-domain")
    registry.register(domain)
    try:
        runner = TurnRunner()
        role_ids = [e.role.role_id for e in runner._debate.experts]
        assert "debate_test_specialist" in role_ids
    finally:
        registry.unregister("debate-test-domain")


def test_turn_runner_falls_back_to_default_experts_without_domain_roles(monkeypatch):
    from homomics_lab.agent import debate as debate_module
    from homomics_lab.agent.turn_runner import TurnRunner

    # No derivable domain roles → the generic panel is used.
    monkeypatch.setattr(debate_module, "experts_from_domain_registry", lambda registry: [])
    experts = TurnRunner._build_debate_experts()
    assert [e.role.role_id for e in experts] == [
        "methodologist",
        "data_engineer",
        "domain_reviewer",
    ]


@pytest.mark.asyncio
async def test_clarification_flow_produces_recommendation_and_card():
    """End-to-end: ambiguous message + domain expert → debate recommendation →
    DEBATE_REQUEST card (the scenario the card is meant for)."""
    from homomics_lab.agent.intent.analyzer import CascadeIntentAnalyzer
    from homomics_lab.agent.intent.classifiers import KeywordIntentClassifier
    from homomics_lab.agent.intent.models import IntentDefinition
    from homomics_lab.agent.turn_runner import ExecutionMode, TurnRunner
    from homomics_lab.context.working_memory import WorkingMemory
    from homomics_lab.models.common import MessageType

    role = RoleDefinition(
        role_id="sc", name="SC Expert", allowed_skills=["single_cell_analysis"]
    )
    debate = LightweightDebate(experts=[DynamicAgent(role=role)])
    analyzer = CascadeIntentAnalyzer(
        definitions=[
            IntentDefinition(
                analysis_type="single_cell_analysis",
                keywords=["单细胞"],
                examples=[],
                domain="single-cell-transcriptomics",
            ),
            IntentDefinition(
                analysis_type="spatial_analysis",
                keywords=["空间"],
                examples=[],
                domain="spatial-transcriptomics",
            ),
        ],
        use_domain_registry=False,
        keyword_classifier=KeywordIntentClassifier(weight=0.05),
        llm_classifier=None,
        clarification_threshold=0.7,
        high_confidence_threshold=2.0,
        debate=debate,
        result_cache=False,
    )
    intent = await analyzer.analyze("做单细胞或空间分析可以吗")
    assert intent.interaction_mode == "clarify"
    debate_meta = intent.metadata.get("debate")
    assert debate_meta is not None
    assert debate_meta["recommendation"] is not None
    assert debate_meta["recommendation"]["id"] == "single_cell_analysis"

    runner = TurnRunner(intent_analyzer=analyzer)
    result = runner._handle_clarification(intent, WorkingMemory())
    assert result.mode == ExecutionMode.AWAITING_DEBATE
    assert result.agent_message.type == MessageType.DEBATE_REQUEST
