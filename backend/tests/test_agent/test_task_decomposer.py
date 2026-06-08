import pytest
from homomics_lab.agent.task_decomposer import TaskDecomposer
from homomics_lab.agent.intent_analyzer import UserIntent


@pytest.fixture
def decomposer():
    return TaskDecomposer()


@pytest.mark.asyncio
async def test_decompose_single_cell_pipeline(decomposer):
    intent = UserIntent(
        analysis_type="single_cell_analysis",
        complexity="complex",
    )

    tree = await decomposer.decompose(intent, context={"sample_count": 1})

    task_names = [t.name for t in tree.tasks]
    assert "quality_control" in task_names
    assert "dimensionality_reduction" in task_names
    assert "clustering" in task_names
    assert "cell_annotation" in task_names


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
async def test_task_dependencies(decomposer):
    intent = UserIntent(
        analysis_type="single_cell_analysis",
        complexity="complex",
    )

    tree = await decomposer.decompose(intent, context={})

    # Clustering should depend on dimensionality_reduction
    cluster_task = next(t for t in tree.tasks if t.name == "clustering")
    dr_task = next(t for t in tree.tasks if t.name == "dimensionality_reduction")
    assert dr_task.id in cluster_task.dependencies
