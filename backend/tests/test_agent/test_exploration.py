"""Tests for the hypothesis-driven ExplorationEngine and its routing gate."""

import json
from collections import deque
from types import SimpleNamespace

import pytest

from homomics_lab.agent.exploration import (
    ExplorationBlueprint,
    ExplorationEngine,
    Hypothesis,
)
from homomics_lab.agent.intent.models import UserIntent
from homomics_lab.agent.turn_intent_router import IntentRouter
from homomics_lab.config import settings


class MockLLMClient:
    """Deterministic LLM stub: pops queued responses in call order."""

    def __init__(self, responses, configured=True):
        self._responses = deque(responses)
        self.calls = []
        self._configured = configured

    def is_configured(self):
        return self._configured

    async def chat_completion(self, messages=None, **kwargs):
        self.calls.append({"messages": messages, "kwargs": kwargs})
        if not self._responses:
            raise RuntimeError("no more mock responses")
        return self._responses.popleft()


class MockExecutor:
    """Records executed task ids and returns a fixed branch result."""

    def __init__(self, result=None):
        self.executed = []
        self._result = (
            result
            if result is not None
            else {"status": "success", "result": {"p_value": 0.001, "log2fc": 1.2}}
        )

    async def __call__(self, task):
        self.executed.append(task.id)
        return self._result


def _blueprint_json(n=3):
    return json.dumps(
        {
            "hypotheses": [
                {
                    "statement": f"假设陈述 {i}",
                    "verification": f"验证分析 {i}",
                    "success_signal": f"支持信号 {i}",
                }
                for i in range(1, n + 1)
            ]
        },
        ensure_ascii=False,
    )


SUPPORTED_JSON = json.dumps(
    {
        "verdict": "supported",
        "confidence": 0.9,
        "reasoning": "处理组显著更高 (p<0.01)",
        "follow_up": None,
    },
    ensure_ascii=False,
)

REFUTED_JSON = json.dumps(
    {
        "verdict": "refuted",
        "confidence": 0.8,
        "reasoning": "两组无显著差异",
        "follow_up": None,
    },
    ensure_ascii=False,
)

INCONCLUSIVE_JSON = json.dumps(
    {
        "verdict": "inconclusive",
        "confidence": 0.3,
        "reasoning": "缺少关键指标",
        "follow_up": None,
    },
    ensure_ascii=False,
)

FOLLOW_UP_JSON = json.dumps(
    {
        "verdict": "supported",
        "confidence": 0.7,
        "reasoning": "初步支持，值得深挖",
        "follow_up": {
            "statement": "CD8 T 细胞是主要贡献者",
            "verification": "细分 T 细胞亚型比较比例",
            "success_signal": "CD8 比例显著升高",
        },
    },
    ensure_ascii=False,
)


def _make_engine(responses, **kwargs):
    return ExplorationEngine(llm_client=MockLLMClient(responses), **kwargs)


# ---------------------------------------------------------------------------
# Blueprint generation and parsing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_blueprint_parses_hypotheses():
    engine = _make_engine([_blueprint_json(3)])
    blueprint = await engine.generate_blueprint(
        "为什么处理组和对照组差异这么大？", data_context="sample.h5ad"
    )
    assert blueprint is not None
    assert blueprint.question == "为什么处理组和对照组差异这么大？"
    assert blueprint.data_context == "sample.h5ad"
    assert len(blueprint.hypotheses) == 3
    for idx, hypothesis in enumerate(blueprint.hypotheses, start=1):
        assert hypothesis.id == f"h{idx}"
        assert hypothesis.statement == f"假设陈述 {idx}"
        assert hypothesis.verification == f"验证分析 {idx}"
        assert hypothesis.success_signal == f"支持信号 {idx}"
        assert hypothesis.depth == 1


@pytest.mark.asyncio
async def test_generate_blueprint_caps_at_max_hypotheses():
    engine = _make_engine([_blueprint_json(6)], max_hypotheses=4)
    blueprint = await engine.generate_blueprint("探索数据有什么规律")
    assert blueprint is not None
    assert len(blueprint.hypotheses) == 4


@pytest.mark.asyncio
async def test_generate_blueprint_tolerates_code_fences():
    fenced = f"```json\n{_blueprint_json(2)}\n```"
    engine = _make_engine([fenced])
    blueprint = await engine.generate_blueprint("探索数据有什么规律")
    assert blueprint is not None
    assert len(blueprint.hypotheses) == 2


@pytest.mark.asyncio
async def test_generate_blueprint_returns_none_on_invalid_json():
    engine = _make_engine(["这不是 JSON"])
    assert await engine.generate_blueprint("探索数据有什么规律") is None


@pytest.mark.asyncio
async def test_generate_blueprint_returns_none_on_empty_hypotheses():
    engine = _make_engine([json.dumps({"hypotheses": []})])
    assert await engine.generate_blueprint("探索数据有什么规律") is None


@pytest.mark.asyncio
async def test_generate_blueprint_returns_none_without_llm():
    engine = ExplorationEngine(llm_client=MockLLMClient([], configured=False))
    assert await engine.generate_blueprint("探索数据有什么规律") is None
    engine_no_client = ExplorationEngine(llm_client=None)
    assert await engine_no_client.generate_blueprint("探索数据有什么规律") is None


# ---------------------------------------------------------------------------
# Blueprint -> TaskTree conversion
# ---------------------------------------------------------------------------


def _make_blueprint(n=3, file_paths=None):
    return ExplorationBlueprint(
        question="为什么处理组和对照组差异这么大？",
        hypotheses=[
            Hypothesis(
                id=f"h{i}",
                statement=f"假设陈述 {i}",
                verification=f"验证分析 {i}",
                success_signal=f"支持信号 {i}",
            )
            for i in range(1, n + 1)
        ],
        data_context="sample.h5ad",
        file_paths=list(file_paths or []),
    )


def test_blueprint_to_task_tree_builds_independent_branches():
    engine = _make_engine([])
    tree = engine.blueprint_to_task_tree(
        _make_blueprint(3, file_paths=["/data/sample.h5ad"])
    )
    assert len(tree.tasks) == 3
    for idx, task in enumerate(tree.tasks, start=1):
        assert task.id == f"explore_h{idx}"
        assert task.dependencies == []  # independent branches
        assert task.phase == "exploration"
        assert task.derivation == "exploration"
        # No pre-bound skill: verification runs through the CodeAct base.
        assert task.skills_required == []
        assert task.parameters["exploration_hypothesis_id"] == f"h{idx}"
        assert task.parameters["hypothesis"] == f"假设陈述 {idx}"
        assert task.parameters["verification"] == f"验证分析 {idx}"
        assert "为什么处理组和对照组差异这么大？" in task.parameters["user_request"]
    assert tree.tasks[0].parameters["input_file_1"] == "/data/sample.h5ad"


def test_blueprint_to_task_tree_display_steps_are_milestones():
    engine = _make_engine([])
    tree = engine.blueprint_to_task_tree(_make_blueprint(2))
    assert len(tree.display_steps) == 2
    assert "假设 1 验证" in tree.display_steps[0].description
    assert "假设 2 验证" in tree.display_steps[1].description
    assert "假设陈述 1" in tree.display_steps[0].description


# ---------------------------------------------------------------------------
# Critique branches
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_critique_supported():
    engine = _make_engine([SUPPORTED_JSON])
    hypothesis = Hypothesis(id="h1", statement="s", verification="v")
    critique = await engine.critique_result(hypothesis, {"result": {"p": 0.001}})
    assert critique.verdict == "supported"
    assert critique.confidence == pytest.approx(0.9)
    assert "显著" in critique.reasoning
    assert critique.follow_up is None


@pytest.mark.asyncio
async def test_critique_refuted():
    engine = _make_engine([REFUTED_JSON])
    hypothesis = Hypothesis(id="h1", statement="s", verification="v")
    critique = await engine.critique_result(hypothesis, {"result": {"p": 0.9}})
    assert critique.verdict == "refuted"
    assert critique.confidence == pytest.approx(0.8)


@pytest.mark.asyncio
async def test_critique_inconclusive():
    engine = _make_engine([INCONCLUSIVE_JSON])
    hypothesis = Hypothesis(id="h1", statement="s", verification="v")
    critique = await engine.critique_result(hypothesis, {"result": {}})
    assert critique.verdict == "inconclusive"
    assert critique.confidence == pytest.approx(0.3)


@pytest.mark.asyncio
async def test_critique_unknown_verdict_degrades_to_inconclusive():
    engine = _make_engine(
        [json.dumps({"verdict": "maybe", "confidence": 5.0, "reasoning": "?"})]
    )
    hypothesis = Hypothesis(id="h1", statement="s", verification="v")
    critique = await engine.critique_result(hypothesis, {"result": {}})
    assert critique.verdict == "inconclusive"
    assert critique.confidence == 1.0  # clamped into [0, 1]


@pytest.mark.asyncio
async def test_critique_without_result_is_inconclusive_without_llm_call():
    llm = MockLLMClient([])
    engine = ExplorationEngine(llm_client=llm)
    hypothesis = Hypothesis(id="h1", statement="s", verification="v")
    critique = await engine.critique_result(hypothesis, None)
    assert critique.verdict == "inconclusive"
    assert llm.calls == []  # no LLM round-trip wasted on an empty result


@pytest.mark.asyncio
async def test_critique_follow_up_increments_depth():
    engine = _make_engine([FOLLOW_UP_JSON])
    parent = Hypothesis(id="h2", statement="s", verification="v", depth=1)
    critique = await engine.critique_result(parent, {"result": {"p": 0.01}})
    assert critique.follow_up is not None
    assert critique.follow_up.id == "h2_f1"
    assert critique.follow_up.depth == 2
    assert critique.follow_up.parent_id == "h2"
    assert critique.follow_up.statement == "CD8 T 细胞是主要贡献者"


# ---------------------------------------------------------------------------
# Depth-limited exploration loop
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_explore_full_loop_with_follow_up():
    responses = [
        _blueprint_json(2),  # blueprint
        FOLLOW_UP_JSON,  # h1: supported + follow-up
        REFUTED_JSON,  # h2: refuted
        SUPPORTED_JSON,  # h1_f1: supported, no further follow-up
    ]
    engine = _make_engine(responses, max_depth=2)
    executor = MockExecutor()
    report = await engine.explore("探索数据有什么规律", executor=executor)

    assert report is not None
    assert executor.executed == ["explore_h1", "explore_h2", "explore_h1_f1"]
    hypotheses = report.hypotheses
    assert len(hypotheses) == 3
    assert hypotheses[0].verdict == "supported"
    assert hypotheses[1].verdict == "refuted"
    assert hypotheses[2].id == "h1_f1"
    assert hypotheses[2].depth == 2
    assert hypotheses[2].verdict == "supported"
    assert "## 探索报告" in report.markdown


@pytest.mark.asyncio
async def test_explore_respects_max_depth():
    # Every critique proposes a follow-up; with max_depth=2 the loop must stop
    # after the second layer instead of exploring forever.
    responses = [_blueprint_json(2)] + [FOLLOW_UP_JSON] * 8
    engine = _make_engine(responses, max_depth=2)
    executor = MockExecutor()
    report = await engine.explore("探索数据有什么规律", executor=executor)

    assert report is not None
    assert executor.executed == [
        "explore_h1",
        "explore_h2",
        "explore_h1_f1",
        "explore_h2_f1",
    ]
    assert max(h.depth for h in report.hypotheses) == 2


@pytest.mark.asyncio
async def test_run_blueprint_uses_precomputed_results():
    # Simulates the job-runner path: branch results already exist, so the
    # executor is only needed for follow-ups.
    engine = _make_engine([SUPPORTED_JSON, REFUTED_JSON])
    executor = MockExecutor()
    blueprint = _make_blueprint(2)
    await engine.run_blueprint(
        blueprint,
        task_results={"h1": {"result": {"p": 0.001}}, "h2": {"result": {"p": 0.9}}},
        executor=executor,
    )
    assert executor.executed == []  # nothing re-executed
    assert blueprint.hypotheses[0].verdict == "supported"
    assert blueprint.hypotheses[1].verdict == "refuted"


@pytest.mark.asyncio
async def test_explore_returns_none_without_blueprint():
    engine = _make_engine(["not json"])
    executor = MockExecutor()
    report = await engine.explore("探索数据有什么规律", executor=executor)
    assert report is None
    assert executor.executed == []


# ---------------------------------------------------------------------------
# Report synthesis
# ---------------------------------------------------------------------------


def test_synthesize_report_structure():
    engine = _make_engine([])
    hypotheses = [
        Hypothesis(
            id="h1",
            statement="处理导致 T 细胞比例升高",
            verification="统计两组 T 细胞比例",
            verdict="supported",
            confidence=0.9,
            reasoning="处理组显著更高",
        ),
        Hypothesis(
            id="h2",
            statement="批次效应主导聚类",
            verification="检查 PC 与批次相关性",
            verdict="refuted",
            confidence=0.8,
            reasoning="PC1 与批次无关",
        ),
        Hypothesis(
            id="h3",
            statement="存在稀有亚群",
            verification="检查小簇标记基因",
            verdict="inconclusive",
            confidence=0.3,
            reasoning="标记基因证据不足",
        ),
    ]
    markdown = engine.synthesize("为什么处理组差异大？", hypotheses)
    assert "## 探索报告：为什么处理组差异大？" in markdown
    assert "共验证 3 个假设：1 个支持、1 个不支持、1 个无法确定。" in markdown
    assert "| 假设 | 验证分析 | 结论 | 置信度 | 依据 |" in markdown
    assert "处理导致 T 细胞比例升高" in markdown
    assert "支持" in markdown
    assert "不支持" in markdown
    assert "无法确定" in markdown
    assert "### 建议下一步" in markdown
    # Follow-up provenance is surfaced when present.
    follow_up = Hypothesis(
        id="h1_f1",
        statement="CD8 亚群驱动",
        verification="亚型细分",
        depth=2,
        parent_id="h1",
        verdict="supported",
        confidence=0.7,
        reasoning="CD8 显著升高",
    )
    markdown_with_follow_up = engine.synthesize("q", [*hypotheses, follow_up])
    assert "后续假设，源自 h1" in markdown_with_follow_up


# ---------------------------------------------------------------------------
# Routing gate
# ---------------------------------------------------------------------------


def _router():
    return IntentRouter(SimpleNamespace(_llm_client=None))


def _intent(message=""):
    return UserIntent(
        intent_type="analysis",
        interaction_mode="execute",
        scope="full",
        domain="single-cell-transcriptomics",
        original_message=message,
    )


def test_open_question_with_data_file_routes_to_exploration():
    router = _router()
    intent = _intent(message="为什么处理组和对照组的细胞比例差别这么大？")
    assert (
        router._should_route_to_exploration(
            intent,
            "为什么处理组和对照组的细胞比例差别这么大？",
            ["/data/sample.h5ad"],
            "proj1",
        )
        is True
    )


def test_open_question_with_project_data_routes_to_exploration(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    raw_dir = tmp_path / "raw" / "proj1"
    raw_dir.mkdir(parents=True)
    (raw_dir / "sample.h5ad").write_bytes(b"fake")
    router = _router()
    intent = _intent(message="探索一下这个数据有什么规律")
    assert (
        router._should_route_to_exploration(
            intent, "探索一下这个数据有什么规律", [], "proj1"
        )
        is True
    )


def test_explicit_analysis_request_not_routed():
    router = _router()
    # Carries an open-question marker AND concrete analysis verbs: the
    # conservative gate must keep it on the workflow path.
    for message in (
        "为什么聚类结果这么差？帮我重新聚类并注释细胞类型",
        "探索数据前先做质控和标准化",
        "why does the umap look weird, run clustering again",
    ):
        intent = _intent(message=message)
        assert (
            router._should_route_to_exploration(
                intent, message, ["/data/sample.h5ad"], "proj1"
            )
            is False
        ), message


def test_plain_analysis_request_not_routed():
    router = _router()
    intent = _intent(message="对我的数据做单细胞聚类分析")
    assert (
        router._should_route_to_exploration(
            intent, "对我的数据做单细胞聚类分析", ["/data/sample.h5ad"], "proj1"
        )
        is False
    )


def test_open_question_without_data_not_routed():
    router = _router()
    intent = _intent(message="为什么肿瘤会复发？")
    assert (
        router._should_route_to_exploration(intent, "为什么肿瘤会复发？", [], "")
        is False
    )


def test_non_question_with_data_not_routed():
    router = _router()
    intent = _intent(message="帮我看看 sample.h5ad 的质量怎么样")
    assert (
        router._should_route_to_exploration(
            intent, "帮我看看 sample.h5ad 的质量怎么样", [], ""
        )
        is False
    )


def test_answer_intent_not_routed():
    router = _router()
    intent = UserIntent(
        intent_type="qa", interaction_mode="answer", target="answer_question", scope="single_step", original_message="什么是批次效应？",
    )
    assert intent.interaction_mode == "answer"
    assert (
        router._should_route_to_exploration(
            intent, "什么是批次效应？", ["/data/sample.h5ad"], "proj1"
        )
        is False
    )


def test_exploration_disabled_not_routed(monkeypatch):
    monkeypatch.setattr("homomics_lab.agent.turn_intent_router.EXPLORATION_ENABLED", False)
    router = _router()
    intent = _intent(message="探索一下这个数据有什么规律")
    assert (
        router._should_route_to_exploration(
            intent, "探索一下这个数据有什么规律", ["/data/sample.h5ad"], "proj1"
        )
        is False
    )
