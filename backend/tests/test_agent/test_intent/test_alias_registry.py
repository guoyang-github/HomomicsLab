
from homomics_lab.agent.intent.alias_registry import AliasRegistry
from homomics_lab.domain.models import DomainDefinition, DomainIntent, DomainPhase
from homomics_lab.skills.models import SkillDefinition, SkillInputSchema


def _single_cell_domain() -> DomainDefinition:
    return DomainDefinition(
        domain="single-cell-transcriptomics",
        description="scRNA-seq domain",
        phases=[
            DomainPhase(id="data_io", required=True, description="Load data", skills=[]),
            DomainPhase(id="qc", required=True, description="Quality control", skills=[]),
            DomainPhase(
                id="normalization",
                required=True,
                description="Normalize counts",
                skills=[],
            ),
            DomainPhase(
                id="dim_reduction",
                required=True,
                description="PCA/UMAP",
                skills=[],
            ),
            DomainPhase(
                id="clustering",
                required=True,
                description="Louvain/Leiden clustering",
                skills=[],
            ),
        ],
        intents=[
            DomainIntent(
                analysis_type="single_cell_analysis",
                keywords=["单细胞", "scRNA-seq", "single cell"],
            ),
            DomainIntent(
                analysis_type="descriptive_statistics",
                keywords=["描述性统计", "数据概览"],
            ),
        ],
    )


def _celltypist_skill() -> SkillDefinition:
    return SkillDefinition(
        id="bio-single-cell-annotation-celltypist",
        name="CellTypist Annotation",
        version="1.0",
        category="single-cell-transcriptomics",
        description="CellTypist cell type annotation",
        input_schema=SkillInputSchema(),
        metadata={
            "keywords": ["celltypist", "immune annotation"],
            "tags": ["celltypist", "annotation"],
            "aliases": ["cell typist"],
        },
    )


def test_resolve_phase_from_common_alias():
    registry = AliasRegistry.build()
    assert registry.resolve_phase("pca") == "dim_reduction"
    assert registry.resolve_phase("Louvain") == "clustering"
    assert registry.resolve_phase("质控") == "qc"


def test_resolve_phase_from_domain_intent_keyword():
    domain = _single_cell_domain()
    registry = AliasRegistry.build(domains=[domain])
    # Keyword "描述性统计" maps to the descriptive_statistics phase.
    assert registry.resolve_phase("描述性统计") == "descriptive_statistics"
    # Keyword for domain-level intent has no phase mapping.
    assert registry.resolve_phase("单细胞") is None


def test_match_phases_prefers_longer_aliases():
    domain = _single_cell_domain()
    registry = AliasRegistry.build(domains=[domain])
    matches = registry.match_phases("run cell type annotation")
    assert "annotation" in matches
    assert "cell type annotation" in matches["annotation"]


def test_resolve_skill_alias():
    skill = _celltypist_skill()
    registry = AliasRegistry.build(skills=[skill])
    assert registry.resolve_skill("celltypist") == skill.id
    assert registry.resolve_skill("Cell Typist") == skill.id
    assert registry.resolve_skill("immune annotation") == skill.id
    assert registry.resolve_skill("unknown_tool") is None


def test_match_skills_excludes_generic_tokens():
    skill = _celltypist_skill()
    # Give the skill a generic tag that should not trigger a match.
    skill.metadata["tags"].append("h5ad")
    registry = AliasRegistry.build(skills=[skill])
    matches = registry.match_skills("analyze my h5ad file")
    assert skill.id not in matches


def test_match_skills_allows_distinctive_keyword_with_domain_signal():
    skill = _celltypist_skill()
    registry = AliasRegistry.build(skills=[skill])
    matches = registry.match_skills("use CellTypist for immune annotation")
    assert skill.id in matches
    assert "celltypist" in matches[skill.id]


def test_domain_alias_resolution():
    domain = _single_cell_domain()
    registry = AliasRegistry.build(domains=[domain])
    assert registry.resolve_domain("single-cell-transcriptomics") == domain.domain
    assert registry.resolve_domain("single cell transcriptomics") == domain.domain


def test_get_domain_keywords():
    domain = _single_cell_domain()
    registry = AliasRegistry.build(domains=[domain])
    keywords = registry.get_domain_keywords("single-cell-transcriptomics")
    assert "单细胞" in keywords
    assert "single-cell" in keywords
