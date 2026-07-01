"""Tests for AnalysisTemplate storage and PlanEngine integration."""

import pytest

from homomics_lab.agent.intent_analyzer import UserIntent
from homomics_lab.agent.plan.engine import PlanEngine
from homomics_lab.agent.plan.models import DataState
from homomics_lab.agent.plan.strategies import AnalysisStrategy, Phase, StrategyLibrary
from homomics_lab.agent.plan.template import AnalysisTemplate
from homomics_lab.agent.plan.template_store import AnalysisTemplateStore
from homomics_lab.skills.models import SkillDefinition, SkillInputSchema
from homomics_lab.skills.registry import SkillRegistry


@pytest.fixture
def template_store(tmp_path):
    store = AnalysisTemplateStore(data_dir=tmp_path)
    return store


class TestAnalysisTemplateStore:
    def test_import_builtin_templates(self, template_store):
        count = template_store.import_builtin_templates()
        assert count >= 1
        templates = template_store.list_templates()
        ids = {t.template_id for t in templates}
        assert "10x_scrnaseq_v1" in ids

    def test_save_and_get(self, template_store):
        template = AnalysisTemplate(
            template_id="test_bulk",
            name="Test Bulk RNA-seq",
            domain="bulk_rnaseq",
            preferred_skills={"qc": "rnaseq-qc"},
            phase_defaults={"qc": {"min_q30": 85}},
        )
        template_store.save_template(template)
        loaded = template_store.get_template("test_bulk")
        assert loaded is not None
        assert loaded.name == "Test Bulk RNA-seq"
        assert loaded.preferred_skills["qc"] == "rnaseq-qc"

    def test_delete(self, template_store):
        template = AnalysisTemplate(template_id="to_delete", name="Delete me")
        template_store.save_template(template)
        assert template_store.delete_template("to_delete") is True
        assert template_store.get_template("to_delete") is None
        assert template_store.delete_template("to_delete") is False

    def test_roundtrip_dict(self):
        template = AnalysisTemplate(
            template_id="roundtrip",
            name="Roundtrip",
            applicable_intents=["a", "b"],
            phase_defaults={"qc": {"x": 1}},
        )
        restored = AnalysisTemplate.from_dict(template.to_dict())
        assert restored == template


@pytest.fixture
def registry_with_qc_skill():
    reg = SkillRegistry()
    reg.register(
        SkillDefinition(
            id="custom_qc",
            name="Custom QC",
            version="1.0",
            category="single_cell",
            description="Quality control for single-cell data",
            input_schema=SkillInputSchema(),
        )
    )
    reg.register(
        SkillDefinition(
            id="scanpy_normalize",
            name="Scanpy Normalize",
            version="1.0",
            category="single_cell",
            description="Normalize single-cell counts",
            input_schema=SkillInputSchema(),
        )
    )
    return reg


@pytest.fixture
def strategy_library():
    lib = StrategyLibrary()
    lib.register(
        AnalysisStrategy(
            name="single_cell_standard",
            description="Standard single-cell RNA-seq analysis pipeline",
            applicable_intents=["single_cell_analysis"],
            skeleton=[
                Phase(phase_type="qc", required=True, description="Quality control filtering single-cell RNA-seq scanpy_qc"),
                Phase(phase_type="normalization", required=True, description="Count normalization log transformation single-cell scanpy"),
                Phase(phase_type="dim_reduction", required=True, description="PCA principal component analysis dimensionality reduction single-cell scanpy"),
                Phase(phase_type="clustering", required=True, description="Cell clustering Louvain Leiden single-cell scanpy"),
            ],
            state_checks=[],
        )
    )
    return lib


class TestPlanEngineTemplateIntegration:
    @pytest.mark.asyncio
    async def test_template_selects_preferred_skill(self, registry_with_qc_skill, strategy_library):
        engine = PlanEngine(skill_registry=registry_with_qc_skill, strategy_library=strategy_library)
        template = AnalysisTemplate(
            template_id="test_sc",
            name="Test scRNA-seq",
            domain="single_cell",
            applicable_intents=["single_cell_analysis"],
            preferred_skills={"qc": "custom_qc"},
            phase_defaults={"qc": {"min_genes": 200}},
            default_parameters={"organism": "human"},
        )
        intent = UserIntent(analysis_type="single_cell_analysis", complexity="standard")
        plan = await engine.plan(intent, DataState(), template=template)

        qc_phase = next(p for p in plan.phases if p.phase_type == "qc")
        assert qc_phase.selected_skill is not None
        assert qc_phase.selected_skill.id == "custom_qc"
        assert qc_phase.parameters["min_genes"] == 200
        assert qc_phase.parameters["organism"] == "human"

    @pytest.mark.asyncio
    async def test_template_ignored_when_preferred_skill_missing(self, registry_with_qc_skill, strategy_library):
        engine = PlanEngine(skill_registry=registry_with_qc_skill, strategy_library=strategy_library)
        template = AnalysisTemplate(
            template_id="test_sc",
            name="Test scRNA-seq",
            preferred_skills={"qc": "missing_skill"},
        )
        intent = UserIntent(analysis_type="single_cell_analysis", complexity="standard")
        plan = await engine.plan(intent, DataState(), template=template)

        qc_phase = next(p for p in plan.phases if p.phase_type == "qc")
        # Falls back to registry search because preferred skill is not installed.
        assert qc_phase.selected_skill is not None
        assert qc_phase.selected_skill.id != "missing_skill"

    @pytest.mark.asyncio
    async def test_reproducibility_context_includes_template(self, registry_with_qc_skill, strategy_library):
        engine = PlanEngine(skill_registry=registry_with_qc_skill, strategy_library=strategy_library)
        template = AnalysisTemplate(
            template_id="test_sc",
            name="Test scRNA-seq",
            preferred_skills={"qc": "custom_qc"},
        )
        intent = UserIntent(analysis_type="single_cell_analysis", complexity="standard")
        plan = await engine.plan(intent, DataState(), template=template)
        assert plan.reproducibility_context.get("template") is not None
        assert plan.reproducibility_context["template"]["template_id"] == "test_sc"


    def test_template_variant_by_data_type(self):
        """Templates can add/remove phases depending on data_state.data_type."""
        template = AnalysisTemplate(
            template_id="sc_rna",
            name="Single-cell RNA-seq",
            domain="single_cell",
            data_type_rules={
                "10x": {
                    "insert_phases": [
                        {
                            "after": "qc",
                            "phase": {
                                "phase_type": "empty_drops",
                                "description": "Remove empty droplets",
                                "parameters": {"fdr": 0.01},
                            },
                        }
                    ],
                    "phase_overrides": {
                        "qc": {"description": "10x-specific QC"},
                    },
                },
                "smart-seq2": {
                    "remove_phases": ["empty_drops"],
                },
            },
        )

        reg = SkillRegistry()
        lib = StrategyLibrary()
        lib.register(
            AnalysisStrategy(
                name="single_cell",
                description="Single-cell analysis",
                applicable_intents=["single_cell_analysis"],
                skeleton=[
                    Phase(phase_type="qc", required=True),
                    Phase(phase_type="normalize", required=True),
                ],
            )
        )
        engine = PlanEngine(skill_registry=reg, strategy_library=lib)

        # 10x adds empty_drops after qc
        phases_10x = [
            Phase(phase_type="qc", required=True),
            Phase(phase_type="normalize", required=True),
        ]
        engine._apply_template(phases_10x, template, data_state=DataState(data_type="10x"))
        types_10x = [p.phase_type for p in phases_10x]
        assert types_10x == ["qc", "empty_drops", "normalize"]
        assert phases_10x[0].description == "10x-specific QC"

        # smart-seq2 removes empty_drops if present
        phases_ss2 = [
            Phase(phase_type="qc", required=True),
            Phase(phase_type="empty_drops", required=True),
            Phase(phase_type="normalize", required=True),
        ]
        engine._apply_template(phases_ss2, template, data_state=DataState(data_type="smart-seq2"))
        types_ss2 = [p.phase_type for p in phases_ss2]
        assert "empty_drops" not in types_ss2
