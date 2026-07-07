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
    monkeypatch.setattr(settings, "auto_load_domain_strategies", True)
    return TaskDecomposer(skill_registry=_domain_skill_registry())


@pytest.mark.asyncio
async def test_decompose_single_cell_pipeline(domain_decomposer):
    intent = UserIntent(
        analysis_type="single_cell_analysis",
        complexity="complex",
    )

    tree = await domain_decomposer.decompose(intent, context={"sample_count": 1})

    task_names = [t.name for t in tree.tasks]
    assert "qc" in task_names
    assert "dim_reduction" in task_names
    assert "clustering" in task_names
    assert "annotation" in task_names


@pytest.mark.asyncio
async def test_decompose_file_conversion(decomposer):
    intent = UserIntent(
        analysis_type="file_conversion",
        complexity="single_step",
    )

    tree = await decomposer.decompose(intent, context={})

    assert len(tree.tasks) == 1
    assert tree.tasks[0].name == "convert_file"


@pytest.mark.asyncio
async def test_task_dependencies(domain_decomposer):
    intent = UserIntent(
        analysis_type="single_cell_analysis",
        complexity="complex",
    )

    tree = await domain_decomposer.decompose(intent, context={})

    # Clustering should depend on dim_reduction
    cluster_task = next(t for t in tree.tasks if t.name == "clustering")
    dr_task = next(t for t in tree.tasks if t.name == "dim_reduction")
    assert dr_task.id in cluster_task.dependencies


@pytest.mark.asyncio
async def test_decompose_sub_intents(domain_decomposer):
    intent = UserIntent(
        analysis_type="single_cell_analysis",
        complexity="complex",
        sub_intents=[
            UserIntent(analysis_type="qc", complexity="single_step"),
            UserIntent(analysis_type="clustering", complexity="single_step"),
        ],
    )

    tree = await domain_decomposer.decompose(intent, context={})
    task_names = [t.name for t in tree.tasks]
    assert "qc" in task_names
    assert "clustering" in task_names


@pytest.mark.asyncio
async def test_decompose_clarification(decomposer):
    intent = UserIntent(
        analysis_type="clarification",
        complexity="direct_response",
        metadata={"clarification_question": "请问您想分析什么数据？"},
    )

    tree = await decomposer.decompose(intent, context={})
    assert len(tree.tasks) == 1
    assert tree.tasks[0].phase == "clarification"
    assert "想分析什么" in tree.tasks[0].description


@pytest.mark.asyncio
async def test_decompose_single_cell_uses_domain_template(domain_decomposer):
    """When domain skills are present, the single-cell-transcriptomics domain.yaml drives execution."""
    intent = UserIntent(
        analysis_type="single_cell_analysis",
        complexity="complex",
    )

    plan, tree = await domain_decomposer.decompose_with_plan(intent, context={})

    assert plan.strategy_name == "single-cell-transcriptomics"
    task_names = [t.name for t in tree.tasks]
    # Core single-cell pipeline driven by the new domain template.
    assert "data_io" in task_names
    assert "qc" in task_names
    assert "normalization" in task_names
    assert "dim_reduction" in task_names
    assert "clustering" in task_names
    assert "annotation" in task_names

    # Dependencies should come from phase_transitions, not a linear fallback.
    qc_task = next(t for t in tree.tasks if t.name == "qc")
    data_io_task = next(t for t in tree.tasks if t.name == "data_io")
    assert data_io_task.id in qc_task.dependencies

    cluster_task = next(t for t in tree.tasks if t.name == "clustering")
    dr_task = next(t for t in tree.tasks if t.name == "dim_reduction")
    assert dr_task.id in cluster_task.dependencies


@pytest.mark.asyncio
async def test_decompose_sub_intents_uses_domain_template(domain_decomposer):
    """Sub-intents filter the domain DAG to the requested phases + prerequisites."""
    intent = UserIntent(
        analysis_type="single_cell_analysis",
        complexity="complex",
        sub_intents=[
            UserIntent(analysis_type="clustering", complexity="single_step"),
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
        analysis_type="single_cell_analysis",
        complexity="complex",
        original_message="对 PA12_sc.h5ad 做单细胞 Louvain 聚类分析",
    )

    plan, tree = await domain_decomposer.decompose_with_plan(intent, context={})

    assert plan.strategy_name == "single-cell-transcriptomics"
    task_names = set(t.name for t in tree.tasks)
    assert "clustering" in task_names
    assert "dim_reduction" in task_names
    assert "normalization" in task_names
    assert "qc" in task_names
    assert "data_io" in task_names
    # Annotation should be omitted because the user only asked for clustering.
    assert "annotation" not in task_names


@pytest.mark.asyncio
async def test_decompose_derives_sub_intents_when_classifier_returns_broad_intent(domain_decomposer):
    """If the classifier returns a broad sub-intent like 'single_cell_analysis',
    explicit phase keywords in the message still narrow the plan."""
    intent = UserIntent(
        analysis_type="builtin_analysis",
        complexity="single_step",
        original_message="对 PA12_sc.h5ad 做单细胞 Louvain 聚类分析",
        sub_intents=[
            UserIntent(analysis_type="single_cell_analysis", complexity="single_step"),
        ],
    )

    plan, tree = await domain_decomposer.decompose_with_plan(intent, context={})

    assert plan.strategy_name == "single-cell-transcriptomics"
    task_names = set(t.name for t in tree.tasks)
    assert "clustering" in task_names
    assert "dim_reduction" in task_names
    assert "annotation" not in task_names
