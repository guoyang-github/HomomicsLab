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
