"""Tests for the ExecutionRouter — foundation-first dispatch."""


from homomics_lab.agent.execution_router import ExecutionMode, ExecutionRouter
from homomics_lab.agent.plan.models import Phase
from homomics_lab.agent.retrieval import (
    RetrievedDataSource,
    RetrievedSkill,
    RetrievedTool,
    RetrievalContext,
)
from homomics_lab.skills.models import SkillDefinition, SkillRuntime


def _make_skill(skill_id: str, description: str = "") -> SkillDefinition:
    return SkillDefinition(
        id=skill_id,
        name=skill_id,
        description=description,
        category="test",
        version="1.0.0",
        runtime=SkillRuntime(type="python"),
        input_schema={"type": "object", "properties": {}},
        output_schema={"type": "object", "properties": {}},
    )


def _make_retrieval_context(
    skills=None,
    tools=None,
    data_sources=None,
    intent_type="single_cell_analysis",
) -> RetrievalContext:
    return RetrievalContext(
        query="single cell qc",
        intent_type=intent_type,
        skills=skills or [],
        tools=tools or [],
        data_sources=data_sources or [],
        literature=[],
        sops=[],
        anomalies=[],
        parameter_lore=[],
    )


class TestExecutionRouter:
    def test_curated_skill_used_when_match_high(self):
        skill = _make_skill("scanpy_qc", "QC for single-cell data")
        phase = Phase(phase_type="qc", selected_skill=skill)
        ctx = _make_retrieval_context()

        router = ExecutionRouter()
        route = router.route(phase, ctx)

        assert route.mode == ExecutionMode.CURATED_SKILL
        assert route.skill == skill

    def test_curated_skill_threshold_requires_high_score(self):
        skill = _make_skill("scanpy_qc")
        rs = RetrievedSkill(skill=skill, semantic_score=0.5)
        phase = Phase(phase_type="qc")
        ctx = _make_retrieval_context(skills=[rs])

        router = ExecutionRouter(curated_skill_threshold=0.8)
        route = router.route(phase, ctx)

        # Below threshold → generate from template
        assert route.mode == ExecutionMode.GENERATED_FROM_TEMPLATE
        assert route.skill == skill

    def test_code_from_retrieval_when_tools_or_data_available(self):
        phase = Phase(phase_type="custom_analysis")
        ctx = _make_retrieval_context(
            tools=[RetrievedTool("pubmed_search", "Search PubMed", {}, "low", "builtin")],
            data_sources=[RetrievedDataSource("gtex", "data/gtex.csv", "csv", "GTEx")],
        )

        router = ExecutionRouter()
        route = router.route(phase, ctx)

        assert route.mode == ExecutionMode.CODE_FROM_RETRIEVAL
        assert "pubmed_search" in route.tools

    def test_code_from_scratch_when_nothing_available(self):
        phase = Phase(phase_type="unknown_task")
        ctx = _make_retrieval_context()

        router = ExecutionRouter()
        route = router.route(phase, ctx)

        assert route.mode == ExecutionMode.CODE_FROM_SCRATCH

    def test_tool_only_for_literature_phase(self):
        phase = Phase(phase_type="literature_review")
        ctx = _make_retrieval_context(
            tools=[RetrievedTool("pubmed_search", "Search PubMed", {}, "low", "builtin")],
        )

        router = ExecutionRouter()
        route = router.route(phase, ctx)

        assert route.mode == ExecutionMode.TOOL_ONLY

    def test_user_preference_code_first(self):
        skill = _make_skill("scanpy_qc")
        phase = Phase(phase_type="qc", selected_skill=skill)
        ctx = _make_retrieval_context()

        router = ExecutionRouter()
        route = router.route(phase, ctx, user_preference="code_first")

        assert route.mode == ExecutionMode.GENERATED_FROM_TEMPLATE

    def test_user_preference_curated_only_falls_back(self):
        phase = Phase(phase_type="qc")
        ctx = _make_retrieval_context()

        router = ExecutionRouter()
        route = router.route(phase, ctx, user_preference="curated_only")

        assert route.mode == ExecutionMode.CODE_FROM_SCRATCH
        assert "No curated skill available" in route.fallback_message
