"""Tests for LLM fallback planner."""

import json

import pytest

from homomics_lab.agent.intent_analyzer import UserIntent
from homomics_lab.agent.plan.engine import PlanEngine
from homomics_lab.agent.plan.llm_fallback import LLMFallbackPlanner
from homomics_lab.agent.plan.models import DataState
from homomics_lab.llm_client import FakeLLMClient
from homomics_lab.skills.models import SkillDefinition, SkillInputSchema
from homomics_lab.skills.registry import SkillRegistry


@pytest.fixture
def registry_with_skills():
    reg = SkillRegistry()
    reg.register(
        SkillDefinition(
            id="scanpy_qc",
            name="scanpy_qc",
            version="1.0",
            category="single_cell",
            description="Filter low quality cells and genes",
            input_schema=SkillInputSchema(),
        )
    )
    reg.register(
        SkillDefinition(
            id="scanpy_pca",
            name="scanpy_pca",
            version="1.0",
            category="single_cell",
            description="Principal component analysis",
            input_schema=SkillInputSchema(),
        )
    )
    reg.register(
        SkillDefinition(
            id="plot_umap",
            name="plot_umap",
            version="1.0",
            category="visualization",
            description="Generate UMAP plot",
            input_schema=SkillInputSchema(),
        )
    )
    return reg


@pytest.fixture
def fake_llm_response():
    return json.dumps({
        "steps": [
            {
                "skill_id": "scanpy_qc",
                "phase": "qc",
                "reason": "Remove low-quality cells first",
                "parameters": {},
            },
            {
                "skill_id": "scanpy_pca",
                "phase": "dim_reduction",
                "reason": "Compute principal components",
                "parameters": {"n_pcs": 30},
            },
        ],
        "summary": "QC followed by PCA",
    })


@pytest.mark.asyncio
async def test_fallback_triggered_for_unknown_intent(registry_with_skills, fake_llm_response):
    """Unknown intents should route through the LLM fallback planner."""
    fake_client = FakeLLMClient(response=fake_llm_response)
    planner = LLMFallbackPlanner(registry_with_skills, llm_client=fake_client)
    engine = PlanEngine(skill_registry=registry_with_skills, llm_fallback=planner)

    intent = UserIntent(
        analysis_type="unknown_type",
        complexity="single_step",
        original_message="quality control and pca for single cell data",
    )
    plan = await engine.plan(intent, DataState())

    assert plan.is_fallback is True
    assert plan.strategy_name == "llm_fallback"
    assert len(plan.phases) == 2
    assert plan.phases[0].selected_skill.id == "scanpy_qc"
    assert plan.phases[1].selected_skill.id == "scanpy_pca"
    assert plan.phases[1].parameters == {"n_pcs": 30}


@pytest.mark.asyncio
async def test_fallback_ignores_unknown_skill_ids(registry_with_skills):
    """LLM hallucinated skill IDs should be filtered out."""
    response = json.dumps({
        "steps": [
            {"skill_id": "nonexistent_skill", "phase": "qc", "reason": "bad"},
            {"skill_id": "plot_umap", "phase": "visualization", "reason": "good"},
        ],
        "summary": "mixed",
    })
    fake_client = FakeLLMClient(response=response)
    planner = LLMFallbackPlanner(registry_with_skills, llm_client=fake_client)

    intent = UserIntent(
        analysis_type="unknown_type",
        complexity="single_step",
        original_message="make a plot",
    )
    plan = await planner.generate_plan(intent, DataState())

    assert len(plan.phases) == 1
    assert plan.phases[0].selected_skill.id == "plot_umap"


@pytest.mark.asyncio
async def test_fallback_graceful_without_api_key(registry_with_skills):
    """Without an LLM configured, fallback returns a helpful message."""
    planner = LLMFallbackPlanner(registry_with_skills, llm_client=FakeLLMClient(response=""))

    intent = UserIntent(
        analysis_type="unknown_type",
        complexity="single_step",
        original_message="do something weird",
    )
    plan = await planner.generate_plan(intent, DataState())

    assert plan.is_fallback is True
    assert not plan.phases
    assert plan.suggestion_text is not None


@pytest.mark.asyncio
async def test_fallback_plan_result_structure(registry_with_skills, fake_llm_response):
    """Fallback PlanResult should carry reproducibility context."""
    fake_client = FakeLLMClient(response=fake_llm_response)
    planner = LLMFallbackPlanner(registry_with_skills, llm_client=fake_client)

    intent = UserIntent(
        analysis_type="unknown_type",
        complexity="single_step",
        original_message="quality control and pca for single cell data",
    )
    plan = await planner.generate_plan(intent, DataState())

    assert plan.is_fallback is True
    assert plan.suggestion_text is not None
    assert "candidate_skills" in plan.reproducibility_context
    assert "llm_selected_skills" in plan.reproducibility_context


@pytest.mark.asyncio
async def test_task_decomposer_uses_fallback_plan(registry_with_skills, fake_llm_response):
    """TaskDecomposer should route unknown intents through PlanEngine and convert phases to tasks."""
    from homomics_lab.agent.task_decomposer import TaskDecomposer

    fake_client = FakeLLMClient(response=fake_llm_response)
    planner = LLMFallbackPlanner(registry_with_skills, llm_client=fake_client)
    engine = PlanEngine(skill_registry=registry_with_skills, llm_fallback=planner)
    decomposer = TaskDecomposer(plan_engine=engine, skill_registry=registry_with_skills)

    intent = UserIntent(
        analysis_type="unknown_type",
        complexity="single_step",
        original_message="quality control and pca for single cell data",
    )
    tree = await decomposer.decompose(intent, context={"project_id": "proj_1"})

    assert len(tree.tasks) == 2
    assert tree.tasks[0].skills_required == ["scanpy_qc"]
    assert tree.tasks[1].skills_required == ["scanpy_pca"]
    # Fallback plans get HITL checkpoints for safety.
    assert tree.tasks[0].hitl_checkpoints


@pytest.fixture
def registry_with_code_act():
    reg = SkillRegistry()
    reg.register(
        SkillDefinition(
            id="core_code_act",
            name="core_code_act",
            version="0.1.0",
            category="agent_core",
            description="Generate and execute code actions for a concrete sub-task",
            input_schema=SkillInputSchema(),
        )
    )
    return reg


@pytest.mark.asyncio
async def test_fallback_to_core_code_act(registry_with_code_act):
    """When no bio skill matches a code/data request, fallback uses core_code_act."""
    response = json.dumps({
        "steps": [
            {
                "skill_id": "core_code_act",
                "phase": "utility",
                "reason": "Generate a script to filter CSV rows",
                "parameters": {
                    "request": "filter CSV rows",
                    "generated_code": "import pandas as pd\ndf = pd.read_csv('data.csv')",
                },
            },
        ],
        "summary": "Generate a CSV filter script",
    })
    fake_client = FakeLLMClient(response=response)
    planner = LLMFallbackPlanner(registry_with_code_act, llm_client=fake_client)

    intent = UserIntent(
        analysis_type="unknown_type",
        complexity="single_step",
        original_message="帮我写个脚本过滤 CSV 行",
    )
    plan = await planner.generate_plan(intent, DataState())

    assert len(plan.phases) == 1
    assert plan.phases[0].selected_skill.id == "core_code_act"
    assert plan.phases[0].readonly is True
    assert "generated_code" in plan.phases[0].parameters


@pytest.mark.asyncio
async def test_graceful_plan_hints_code_act(registry_with_code_act):
    """Without an LLM, code/data requests get a more helpful suggestion."""
    planner = LLMFallbackPlanner(
        registry_with_code_act,
        llm_client=FakeLLMClient(response=""),
        allow_code_fallback=True,
    )

    intent = UserIntent(
        analysis_type="unknown_type",
        complexity="single_step",
        original_message="rename sample files in batch",
    )
    plan = await planner.generate_plan(intent, DataState())

    assert plan.is_fallback is True
    assert not plan.phases
    assert "general coding" in plan.suggestion_text or "write a script" in plan.suggestion_text
