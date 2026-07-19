import pytest
import yaml
from pathlib import Path

from homomics_lab.agent.task_decomposer import TaskDecomposer
from homomics_lab.agent.intent_analyzer import UserIntent
from homomics_lab.config import settings
from homomics_lab.skills.models import SkillDefinition, SkillInputSchema
from homomics_lab.skills.registry import SkillRegistry


@pytest.fixture
def decomposer():
    return TaskDecomposer()


def _domain_skill_registry() -> SkillRegistry:
    """Build a registry containing every skill referenced by the single_cell domain."""
    registry = SkillRegistry()
    domain_file = Path(__file__).parent.parent.parent / "homomics_lab" / "domains" / "single-cell-transcriptomics" / "domain.yaml"
    with open(domain_file, "r", encoding="utf-8") as f:
        domain = yaml.safe_load(f)
    skill_ids = {
        skill_id
        for phase in domain.get("phases", [])
        for skill_id in phase.get("skills", [])
    }
    for skill_id in skill_ids:
        registry.register(
            SkillDefinition(
                id=skill_id,
                name=skill_id,
                version="1.0",
                category="single-cell-transcriptomics",
                description=f"Domain skill {skill_id}",
                input_schema=SkillInputSchema(),
            )
        )
    return registry


@pytest.fixture
def domain_decomposer(monkeypatch):
    return TaskDecomposer(skill_registry=_domain_skill_registry())


@pytest.mark.asyncio
async def test_decompose_single_cell_pipeline(domain_decomposer):
    intent = UserIntent(
        intent_type="analysis", interaction_mode="execute", domain="single-cell-transcriptomics", scope="full", )

    tree = await domain_decomposer.decompose(intent, context={"sample_count": 1})

    task_names = [t.name for t in tree.tasks]
    assert "qc" in task_names
    assert "dim_reduction" in task_names
    assert "clustering" in task_names
    assert "annotation" in task_names


@pytest.mark.asyncio
async def test_decompose_file_conversion(decomposer):
    intent = UserIntent(
        intent_type="file_conversion", interaction_mode="execute", target="convert_file", scope="single_step", )

    tree = await decomposer.decompose(intent, context={})

    assert len(tree.tasks) == 1
    assert tree.tasks[0].name == "convert_file"


@pytest.mark.asyncio
async def test_task_dependencies(domain_decomposer):
    intent = UserIntent(
        intent_type="analysis", interaction_mode="execute", domain="single-cell-transcriptomics", scope="full", )

    tree = await domain_decomposer.decompose(intent, context={})

    # Clustering should depend on dim_reduction
    cluster_task = next(t for t in tree.tasks if t.name == "clustering")
    dr_task = next(t for t in tree.tasks if t.name == "dim_reduction")
    assert dr_task.id in cluster_task.dependencies


@pytest.mark.asyncio
async def test_decompose_sub_intents(domain_decomposer):
    intent = UserIntent(
        intent_type="analysis", interaction_mode="execute", domain="single-cell-transcriptomics", scope="full",
        sub_intents=[
            UserIntent(intent_type="analysis", interaction_mode="execute", target="qc", scope="single_step"),
            UserIntent(intent_type="analysis", interaction_mode="execute", target="clustering", scope="single_step"),
        ],
    )

    tree = await domain_decomposer.decompose(intent, context={})
    task_names = [t.name for t in tree.tasks]
    assert "qc" in task_names
    assert "clustering" in task_names


@pytest.mark.asyncio
async def test_decompose_clarification(decomposer):
    intent = UserIntent(
        intent_type="clarification", interaction_mode="clarify", scope="single_step", metadata={"clarification_question": "请问您想分析什么数据？"},
    )

    tree = await decomposer.decompose(intent, context={})
    assert len(tree.tasks) == 1
    assert tree.tasks[0].phase == "clarification"
    assert "想分析什么" in tree.tasks[0].description


@pytest.mark.asyncio
async def test_decompose_single_cell_uses_domain_template(domain_decomposer):
    """When domain skills are present, the single-cell-transcriptomics domain.yaml drives execution."""
    intent = UserIntent(
        intent_type="analysis", interaction_mode="execute", domain="single-cell-transcriptomics", scope="full", )

    plan, tree = await domain_decomposer.decompose_with_plan(intent, context={})

    assert plan.strategy_name == "single-cell-transcriptomics"
    task_names = [t.name for t in tree.tasks]
    # Core single-cell pipeline driven by the new domain template.
    # data_io is optional and only included when the input state triggers it.
    assert "qc" in task_names
    assert "normalization" in task_names
    assert "dim_reduction" in task_names
    assert "clustering" in task_names
    assert "annotation" in task_names

    # Dependencies should come from phase_transitions, not a linear fallback.
    cluster_task = next(t for t in tree.tasks if t.name == "clustering")
    dr_task = next(t for t in tree.tasks if t.name == "dim_reduction")
    assert dr_task.id in cluster_task.dependencies


@pytest.mark.asyncio
async def test_decompose_sub_intents_uses_domain_template(domain_decomposer):
    """Sub-intents filter the domain DAG to the requested phases + prerequisites."""
    intent = UserIntent(
        intent_type="analysis", interaction_mode="execute", domain="single-cell-transcriptomics", scope="full",
        sub_intents=[
            UserIntent(intent_type="analysis", interaction_mode="execute", target="clustering", scope="single_step"),
        ],
    )

    plan, tree = await domain_decomposer.decompose_with_plan(intent, context={})

    assert plan.strategy_name == "single-cell-transcriptomics"
    task_names = set(t.name for t in tree.tasks)
    assert "clustering" in task_names
    assert "dim_reduction" in task_names
    assert "normalization" in task_names
    assert "qc" in task_names
    # Optional downstream phases should be omitted.
    assert "annotation" not in task_names
    assert "differential_expression" not in task_names


@pytest.mark.asyncio
async def test_decompose_derives_sub_intents_from_message(domain_decomposer):
    """When no sub-intents are provided but the message names a phase, the plan is narrowed."""
    intent = UserIntent(
        intent_type="analysis", interaction_mode="execute", domain="single-cell-transcriptomics", scope="full", original_message="对 PA12_sc.h5ad 做单细胞 Louvain 聚类分析",
    )

    plan, tree = await domain_decomposer.decompose_with_plan(intent, context={})

    assert plan.strategy_name == "single-cell-transcriptomics"
    task_names = set(t.name for t in tree.tasks)
    assert "clustering" in task_names
    assert "dim_reduction" in task_names
    assert "normalization" in task_names
    assert "qc" in task_names
    # data_io is optional and only included when explicitly triggered by input state.
    assert "annotation" not in task_names


@pytest.mark.asyncio
async def test_decompose_derives_sub_intents_when_classifier_returns_broad_intent(domain_decomposer):
    """If the classifier returns a broad sub-intent like 'single_cell_analysis',
    explicit phase keywords in the message still narrow the plan."""
    intent = UserIntent(
        intent_type="builtin_analysis", interaction_mode="execute", scope="single_step", original_message="对 PA12_sc.h5ad 做单细胞 Louvain 聚类分析",
        sub_intents=[
            UserIntent(intent_type="analysis", interaction_mode="execute", domain="single-cell-transcriptomics", scope="single_step"),
        ],
    )

    plan, tree = await domain_decomposer.decompose_with_plan(intent, context={})

    assert plan.strategy_name == "single-cell-transcriptomics"
    task_names = set(t.name for t in tree.tasks)
    assert "clustering" in task_names
    assert "dim_reduction" in task_names
    assert "annotation" not in task_names


@pytest.fixture
def standalone_decomposer():
    """Decomposer backed by a registry with standalone skills."""
    registry = SkillRegistry()
    registry.register(
        SkillDefinition(
            id="text_summarizer",
            name="Text Summarizer",
            version="1.0",
            category="nlp",
            description="Summarize text passages",
            input_schema=SkillInputSchema(),
        )
    )
    registry.register(
        SkillDefinition(
            id="single_cell_qc",
            name="Single Cell QC",
            version="1.0",
            category="single-cell-transcriptomics",
            description="QC for single-cell data",
            domains=["single-cell-transcriptomics"],
            input_schema=SkillInputSchema(),
        )
    )
    return TaskDecomposer(skill_registry=registry)


@pytest.mark.asyncio
async def test_decompose_routes_to_standalone_planner(standalone_decomposer):
    """A generic request with no domain signal should use standalone skills."""
    intent = UserIntent(
        intent_type="general", interaction_mode="execute", scope="single_step", original_message="summarize this text",
    )

    plan, tree = await standalone_decomposer.decompose_with_plan(intent, context={})

    assert plan.derivation == "standalone-skill"
    assert plan.risk_level == "low"
    assert len(tree.tasks) == 1
    assert tree.tasks[0].name == "text_summarizer"
    assert tree.tasks[0].derivation == "standalone-skill"


@pytest.mark.asyncio
async def test_decompose_does_not_route_domain_request_to_standalone(standalone_decomposer):
    """A request carrying a domain signal should not be hijacked by standalone skills."""
    intent = UserIntent(
        intent_type="analysis", interaction_mode="execute", scope="full", domain="single-cell-transcriptomics",
        original_message="run single cell qc",
    )

    plan, tree = await standalone_decomposer.decompose_with_plan(intent, context={})

    # No domain strategy is loaded in this fixture, so PlanEngine will fallback.
    # The key assertion is that the standalone planner was not used.
    assert plan.derivation != "standalone-skill"
    task_names = {t.name for t in tree.tasks}
    assert "text_summarizer" not in task_names


@pytest.mark.asyncio
async def test_decompose_explicit_skill_target_avoids_full_pipeline(monkeypatch):
    """When the user names a concrete skill, the plan contains only that skill."""
    registry = SkillRegistry()
    registry.register(
        SkillDefinition(
            id="bio-single-cell-annotation-celltypist",
            name="bio-single-cell-annotation-celltypist",
            version="1.0",
            category="single-cell-transcriptomics",
            description="CellTypist cell type annotation",
            domains=["single-cell-transcriptomics"],
            input_schema=SkillInputSchema(),
        )
    )
    registry.register(
        SkillDefinition(
            id="text_summarizer",
            name="Text Summarizer",
            version="1.0",
            category="nlp",
            description="Summarize text passages",
            input_schema=SkillInputSchema(),
        )
    )

    decomposer = TaskDecomposer(skill_registry=registry)
    intent = UserIntent(
        intent_type="analysis", interaction_mode="execute", scope="single_step", domain="single-cell-transcriptomics",
        target="bio-single-cell-annotation-celltypist",
        original_message="使用 CellTypist 对 PA12_sc.h5ad 中的免疫细胞进行自动注释",
    )

    plan, tree = await decomposer.decompose_with_plan(intent, context={})

    assert plan.derivation == "standalone-skill"
    assert len(tree.tasks) == 1
    assert tree.tasks[0].name == "bio-single-cell-annotation-celltypist"
    task_names = {t.name for t in tree.tasks}
    assert "qc" not in task_names
    assert "clustering" not in task_names
    assert "normalization" not in task_names


def test_attach_uploaded_files_to_tree():
    """Bare filenames in the message are resolved to uploaded project files."""
    from homomics_lab.agent.turn_runner import TurnRunner
    from homomics_lab.tasks.models import TaskNode
    from homomics_lab.tasks.task_tree import TaskTree

    project_id = "test_attach"
    raw_dir = settings.data_dir / "raw" / project_id
    raw_dir.mkdir(parents=True, exist_ok=True)
    uploaded = raw_dir / "sample.h5ad"
    uploaded.write_text("fake")

    runner = TurnRunner()
    tree = TaskTree(
        [
            TaskNode(
                id="t1",
                name="annotation",
                description="annotate",
                phase="annotation",
                skills_required=["bio-single-cell-annotation-celltypist"],
                parameters={},
            )
        ]
    )
    runner._attach_uploaded_files_to_tree(
        tree,
        "使用 CellTypist 对 sample.h5ad 进行注释",
        project_id,
    )

    assert tree.tasks[0].parameters["input_file"] == str(uploaded.resolve())
    assert tree.tasks[0].parameters["uploaded_files"] == [
        {"filename": "sample.h5ad", "path": str(uploaded.resolve())}
    ]


@pytest.mark.asyncio
async def test_decompose_populates_routing_trace():
    """The routing decision trace is exposed in the PlanResult for observability."""
    registry = SkillRegistry()
    registry.register(
        SkillDefinition(
            id="bio-single-cell-annotation-celltypist",
            name="CellTypist Annotation",
            version="1.0",
            category="single-cell-transcriptomics",
            description="CellTypist cell type annotation",
            domains=["single-cell-transcriptomics"],
            input_schema=SkillInputSchema(),
        )
    )

    decomposer = TaskDecomposer(skill_registry=registry)
    intent = UserIntent(
        intent_type="analysis", interaction_mode="execute", scope="single_step", domain="single-cell-transcriptomics",
        target="bio-single-cell-annotation-celltypist",
        original_message="使用 CellTypist 对 PA12_sc.h5ad 中的免疫细胞进行自动注释",
    )

    plan, _ = await decomposer.decompose_with_plan(intent, context={})

    assert plan.routing_trace
    assert any(
        entry.get("route") == "standalone_skill" for entry in plan.routing_trace
    )
    assert plan.to_dict().get("routing_trace") == plan.routing_trace


@pytest.mark.asyncio
async def test_preflight_single_shot_overrides_domain_template():
    """When DataPreflight says the task is single-shot, a phase-level intent with
    an explicit skill target should still route to standalone_skill instead of
    the full domain pipeline.
    """
    registry = SkillRegistry()
    registry.register(
        SkillDefinition(
            id="bio-single-cell-annotation-celltypist",
            name="CellTypist Annotation",
            version="1.0",
            category="single-cell-transcriptomics",
            description="CellTypist cell type annotation",
            domains=["single-cell-transcriptomics"],
            input_schema=SkillInputSchema(),
        )
    )

    decomposer = TaskDecomposer(skill_registry=registry)
    intent = UserIntent(
        intent_type="analysis", interaction_mode="execute", target="annotation", scope="single_step", domain="single-cell-transcriptomics",
        original_message="使用 CellTypist 对 PA12_sc.h5ad 中的免疫细胞进行自动注释并比较 all_celltype 一致性",
    )
    context = {
        "preflight": {
            "required_steps": ["prepare input", "run annotation", "compare predictions", "summarize"],
            "skip_phases": ["qc", "doublet_removal", "dim_reduction", "clustering", "normalization"],
            "needs_qc": False,
            "needs_normalization": False,
            "needs_clustering": False,
        }
    }

    plan, tree = await decomposer.decompose_with_plan(intent, context=context)

    assert plan.derivation == "standalone-skill"
    assert len(tree.tasks) == 1
    assert tree.tasks[0].name == "bio-single-cell-annotation-celltypist"
    assert tree.tasks[0].parameters.get("use_skill_reference") is True


@pytest.mark.asyncio
async def test_no_coverage_intent_falls_through_to_plan_engine():
    """Open-ended/diagnostic intents (formerly the open-agent trigger) now go
    straight to PlanEngine's generic -> LLM fallback planner.

    With no registered skill coverage the result is the standard
    approval-gated fallback shape: ``derivation`` is never ``open-agent``,
    and executable fallback tasks carry no bound skill so the orchestrator
    runs them through CodeAct (an empty-phase fallback degrades to a
    suggestion task).
    """
    decomposer = TaskDecomposer(skill_registry=SkillRegistry())
    intent = UserIntent(
        intent_type="explore",
        interaction_mode="explore",
        scope="full",
        original_message="为什么我的实验结果和预期不一致？",
    )

    plan, tree = await decomposer.decompose_with_plan(intent, context={})

    assert plan.derivation != "open-agent"
    assert plan.strategy_name != "open-agent"
    assert plan.is_fallback
    assert tree.tasks, "fallback plan must still produce a task tree"
    for task in tree.tasks:
        assert task.derivation != "open-agent"
        # Either a suggestion task or a skill-less (CodeAct-executable) task.
        assert not task.skills_required
