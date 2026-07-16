"""Tests for capability-first routing assembler."""

from typing import Any, List, Optional

import pytest

from homomics_lab.agent.intent import UserIntent
from homomics_lab.agent.plan.capability_assembler import CapabilityAssembler
from homomics_lab.agent.plan.template import AnalysisTemplate
from homomics_lab.skills.capability_index import CapabilityCandidate, CapabilityType
from homomics_lab.skills.models import SkillDefinition
from homomics_lab.skills.registry import SkillRegistry


class FakeCapabilityIndex:
    """In-memory capability index for deterministic tests."""

    def __init__(
        self,
        templates: List[CapabilityCandidate] = None,
        skills: List[CapabilityCandidate] = None,
    ):
        self._templates = templates or []
        self._skills = skills or []

    async def search_by_intent(
        self,
        intent: UserIntent,
        data_state: Optional[Any] = None,
        item_types: Optional[List[CapabilityType]] = None,
        top_k: int = 10,
    ) -> List[CapabilityCandidate]:
        if item_types == [CapabilityType.TEMPLATE]:
            return self._templates[:top_k]
        if item_types == [CapabilityType.SKILL]:
            return self._skills[:top_k]
        return []


def _make_skill(
    skill_id: str, description: str = "", domains: List[str] = None
) -> SkillDefinition:
    return SkillDefinition(
        id=skill_id,
        name=skill_id,
        version="1.0",
        category="general",
        description=description,
        domains=domains or [],
    )


@pytest.fixture
def skill_registry() -> SkillRegistry:
    reg = SkillRegistry()
    reg.register(_make_skill("file_converter", "Convert files between formats"))
    reg.register(_make_skill("text_summarizer", "Summarize long articles"))
    reg.register(_make_skill("bio_qa", "Answer biology questions", domains=["biology"]))
    return reg


@pytest.mark.asyncio
async def test_assemble_routes_cross_domain_when_multiple_domains_detected(
    skill_registry,
):
    intent = UserIntent(
        analysis_type="single_cell_analysis",
        complexity="complex",
        domain="single-cell-transcriptomics",
        original_message="先做单细胞聚类，再用空间转录组做反卷积",
        sub_intents=[
            UserIntent(
                analysis_type="spatial_deconvolution",
                complexity="single_step",
                domain="spatial-transcriptomics",
            ),
        ],
    )
    assembler = CapabilityAssembler(skill_registry=skill_registry)
    assembly = await assembler.assemble(intent)

    assert assembly.route == "cross_domain"
    assert "single-cell-transcriptomics" in assembly.domains
    assert "spatial-transcriptomics" in assembly.domains
    assert "Multiple domains detected" in assembly.reason


@pytest.mark.asyncio
async def test_assemble_routes_domain_template_when_coverage_high(skill_registry):
    template = AnalysisTemplate(
        template_id="sc_10x",
        name="10x scRNA-seq",
        domain="single-cell-transcriptomics",
        applicable_intents=["single_cell_analysis", "10x scrna-seq"],
    )
    candidate = CapabilityCandidate(
        id="sc_10x",
        type=CapabilityType.TEMPLATE,
        name=template.name,
        description="",
        category="template",
        score=0.9,
        payload=template.to_dict(),
    )
    index = FakeCapabilityIndex(templates=[candidate])
    assembler = CapabilityAssembler(
        capability_index=index, skill_registry=skill_registry
    )

    intent = UserIntent(
        analysis_type="single_cell_analysis",
        complexity="complex",
        original_message="10x scrna-seq analysis",
    )
    assembly = await assembler.assemble(intent)

    assert assembly.route == "domain_template"
    assert assembly.template is not None
    assert assembly.template.template_id == "sc_10x"
    assert assembly.coverage >= 0.7


@pytest.mark.asyncio
async def test_assemble_routes_standalone_skill_when_score_high(skill_registry):
    candidate = CapabilityCandidate(
        id="text_summarizer",
        type=CapabilityType.SKILL,
        name="Text Summarizer",
        description="Summarize long articles",
        category="nlp",
        score=0.8,
        payload={},
    )
    index = FakeCapabilityIndex(skills=[candidate])
    assembler = CapabilityAssembler(
        capability_index=index, skill_registry=skill_registry
    )

    intent = UserIntent(
        analysis_type="general",
        complexity="single_step",
        original_message="summarize this article",
    )
    assembly = await assembler.assemble(intent)

    assert assembly.route == "standalone_skill"
    assert len(assembly.prebuilt_skills) == 1
    assert assembly.prebuilt_skills[0].id == "text_summarizer"
    assert assembly.score >= 0.65


@pytest.mark.asyncio
async def test_assemble_falls_back_to_open_agent(skill_registry):
    assembler = CapabilityAssembler(skill_registry=skill_registry)

    intent = UserIntent(
        analysis_type="general",
        complexity="single_step",
        original_message="something completely unrelated",
    )
    assembly = await assembler.assemble(intent)

    assert assembly.route == "open_agent"


@pytest.mark.asyncio
async def test_assemble_ignores_domain_skills_for_standalone(skill_registry):
    candidate = CapabilityCandidate(
        id="bio_qa",
        type=CapabilityType.SKILL,
        name="Biology QA",
        description="Answer biology questions",
        category="qa",
        score=0.95,
        payload={},
    )
    index = FakeCapabilityIndex(skills=[candidate])
    assembler = CapabilityAssembler(
        capability_index=index, skill_registry=skill_registry
    )

    intent = UserIntent(
        analysis_type="general",
        complexity="single_step",
        original_message="biology question",
    )
    assembly = await assembler.assemble(intent)

    # bio_qa belongs to a domain, so it must not trigger standalone routing.
    assert assembly.route == "open_agent"


@pytest.mark.asyncio
async def test_assemble_returns_none_template_when_no_templates(skill_registry):
    assembler = CapabilityAssembler(skill_registry=skill_registry)
    intent = UserIntent(
        analysis_type="single_cell_analysis",
        complexity="complex",
    )
    assembly = await assembler.assemble(intent)

    # single_cell_analysis carries a domain signal, so standalone routing is
    # skipped and the request is delegated to the open agent / domain strategy.
    assert assembly.route == "open_agent"


@pytest.mark.asyncio
async def test_capability_first_routing_through_task_decomposer(monkeypatch):
    """When capability-first routing is enabled, TaskDecomposer uses the assembler."""
    from homomics_lab.agent.task_decomposer import TaskDecomposer

    reg = SkillRegistry()
    reg.register(_make_skill("text_summarizer", "Summarize long articles"))

    decomposer = TaskDecomposer(skill_registry=reg)
    intent = UserIntent(
        analysis_type="general",
        complexity="single_step",
        original_message="summarize this article",
    )

    plan, tree = await decomposer.decompose_with_plan(intent, context={})

    assert plan.derivation == "standalone-skill"
    assert len(tree.tasks) == 1
    assert tree.tasks[0].name == "text_summarizer"


@pytest.mark.asyncio
async def test_assemble_routes_explicit_target_skill(skill_registry):
    """When intent.target is a registered skill_id, route directly to that skill."""
    assembler = CapabilityAssembler(skill_registry=skill_registry)

    intent = UserIntent(
        analysis_type="single_cell_analysis",
        complexity="single_step",
        domain="single-cell-transcriptomics",
        target="bio_qa",
    )
    assembly = await assembler.assemble(intent)

    assert assembly.route == "standalone_skill"
    assert len(assembly.prebuilt_skills) == 1
    assert assembly.prebuilt_skills[0].id == "bio_qa"
    assert "Explicit skill target" in assembly.reason


@pytest.mark.asyncio
async def test_assemble_resolves_skill_name_from_message(skill_registry):
    """A skill name token in the message resolves to a single explicit skill."""
    reg = SkillRegistry()
    reg.register(
        SkillDefinition(
            id="bio-single-cell-annotation-celltypist",
            name="bio-single-cell-annotation-celltypist",
            version="1.0",
            category="single-cell-transcriptomics",
            description="CellTypist annotation",
            domains=["single-cell-transcriptomics"],
            metadata={"keywords": ["celltypist", "annotation", "immune"]},
        )
    )
    assembler = CapabilityAssembler(skill_registry=reg)

    intent = UserIntent(
        analysis_type="single_cell_analysis",
        complexity="single_step",
        domain="single-cell-transcriptomics",
        original_message="使用 CellTypist 对 h5ad 中的免疫细胞进行自动注释",
    )
    assembly = await assembler.assemble(intent)

    assert assembly.route == "standalone_skill"
    assert len(assembly.prebuilt_skills) == 1
    assert assembly.prebuilt_skills[0].id == "bio-single-cell-annotation-celltypist"
