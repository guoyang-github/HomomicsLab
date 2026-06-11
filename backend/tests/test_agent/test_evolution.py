"""Tests for AgentEvolutionEngine."""

import pytest

from homomics_lab.agent.core.registry import RoleRegistry
from homomics_lab.agent.core.role import RoleDefinition
from homomics_lab.agent.evolution import (
    AgentEvolutionEngine,
    RoleDelta,
)
from homomics_lab.agent.plan.engine import PlanEngine
from homomics_lab.knowledge.cbkb import CBKB, ExperimentNode, LabSOP, ParameterLoreEntry
from homomics_lab.skills.models import SkillDefinition, SkillInputSchema
from homomics_lab.skills.registry import SkillRegistry


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def cbkb(tmp_path):
    return CBKB(base_dir=tmp_path)


@pytest.fixture
def role_registry():
    reg = RoleRegistry()
    reg.register(
        RoleDefinition(
            role_id="bioinfo_analyst",
            name="Bioinformatics Analyst",
            allowed_skills=["scanpy_qc", "scanpy_cluster"],
            priority=50,
        )
    )
    reg.register(
        RoleDefinition(
            role_id="viz_specialist",
            name="Visualization Specialist",
            allowed_skills=["plot_umap", "plot_violin"],
            priority=100,
        )
    )
    return reg


@pytest.fixture
def plan_engine():
    skill_reg = SkillRegistry()
    skill_reg.register(
        SkillDefinition(
            id="scanpy_qc",
            name="scanpy_qc",
            version="1.0",
            category="single_cell",
            description="QC",
            input_schema=SkillInputSchema(),
        )
    )
    return PlanEngine(skill_registry=skill_reg)


@pytest.fixture
def engine(cbkb, role_registry, plan_engine):
    return AgentEvolutionEngine(
        cbkb=cbkb,
        role_registry=role_registry,
        plan_engine=plan_engine,
    )


# ------------------------------------------------------------------
# evolve_roles
# ------------------------------------------------------------------


class TestEvolveRoles:
    def test_proposes_metadata_update_for_dominant_parameter(self, engine, cbkb):
        """When one parameter value dominates >70 % with best outcome,
        a metadata delta is proposed."""
        # 8 samples: 7 good for 0.8, 1 mediocre for 0.6
        for i in range(7):
            cbkb.add_parameter_lore(
                ParameterLoreEntry(
                    id=f"pl_good_{i}",
                    skill_id="scanpy_cluster",
                    param_name="resolution",
                    param_value="0.8",
                    outcome_metric="silhouette",
                    outcome_value=0.85,
                    project_id="p1",
                    context="",
                    created_at="2024-01-01T00:00:00+00:00",
                )
            )
        cbkb.add_parameter_lore(
            ParameterLoreEntry(
                id="pl_bad",
                skill_id="scanpy_cluster",
                param_name="resolution",
                param_value="0.6",
                outcome_metric="silhouette",
                outcome_value=0.55,
                project_id="p1",
                context="",
                created_at="2024-01-01T00:00:00+00:00",
            )
        )

        deltas = engine.evolve_roles()
        meta_deltas = [d for d in deltas if d.field_changed == "metadata"]
        assert len(meta_deltas) == 1
        assert meta_deltas[0].role_id == "bioinfo_analyst"
        assert meta_deltas[0].new_value.get("preferred_param_scanpy_cluster_resolution") == "0.8"
        assert meta_deltas[0].confidence > 0.70

    def test_proposes_priority_drop_and_block_for_failing_skill(self, engine, cbkb):
        """Very low average outcome triggers priority reduction and blocking."""
        for i in range(5):
            cbkb.add_parameter_lore(
                ParameterLoreEntry(
                    id=f"pl_fail_{i}",
                    skill_id="scanpy_cluster",
                    param_name="resolution",
                    param_value="0.8",
                    outcome_metric="silhouette",
                    outcome_value=0.05,
                    project_id="p1",
                    context="",
                    created_at="2024-01-01T00:00:00+00:00",
                )
            )

        deltas = engine.evolve_roles()
        priority_deltas = [d for d in deltas if d.field_changed == "priority"]
        block_deltas = [d for d in deltas if d.field_changed == "blocked_skills"]

        assert len(priority_deltas) == 1
        assert priority_deltas[0].new_value > priority_deltas[0].old_value
        assert len(block_deltas) == 1
        assert "scanpy_cluster" in block_deltas[0].new_value

    def test_no_delta_when_samples_below_threshold(self, engine, cbkb):
        """With fewer than 3 lore entries, the engine stays silent."""
        for i in range(2):
            cbkb.add_parameter_lore(
                ParameterLoreEntry(
                    id=f"pl_{i}",
                    skill_id="scanpy_cluster",
                    param_name="resolution",
                    param_value="0.8",
                    outcome_metric="silhouette",
                    outcome_value=0.9,
                    project_id="p1",
                    context="",
                    created_at="2024-01-01T00:00:00+00:00",
                )
            )

        deltas = engine.evolve_roles()
        assert deltas == []


# ------------------------------------------------------------------
# mine_plan_patterns
# ------------------------------------------------------------------


class TestMinePlanPatterns:
    def test_extracts_recurring_successful_pattern(self, engine, cbkb):
        phases = ["qc", "normalization", "clustering"]
        for i in range(4):
            cbkb.add_experiment_node(
                ExperimentNode(
                    bundle_id=f"b{i}",
                    project_id="p1",
                    created_at="2024-01-01T00:00:00+00:00",
                    skills_used=["scanpy_qc", "scanpy_norm", "scanpy_cluster"],
                    phases=phases,
                    summary="",
                    metadata={
                        "strategy_type": "single_cell_standard",
                        "success": True,
                        "duration_min": 30.0 + i,
                    },
                )
            )

        patterns = engine.mine_plan_patterns()
        assert len(patterns) == 1
        p = patterns[0]
        assert p.strategy_type == "single_cell_standard"
        assert p.typical_phases == phases
        assert p.success_rate == 1.0
        assert p.extracted_from_n_bundles == 4
        assert 31.0 <= p.avg_duration_min <= 33.5

    def test_ignores_single_occurrence_sequences(self, engine, cbkb):
        cbkb.add_experiment_node(
            ExperimentNode(
                bundle_id="b1",
                project_id="p1",
                created_at="2024-01-01T00:00:00+00:00",
                skills_used=["a"],
                phases=["qc"],
                summary="",
                metadata={"strategy_type": "generic", "success": True},
            )
        )

        patterns = engine.mine_plan_patterns()
        assert patterns == []


# ------------------------------------------------------------------
# learn_parameter_preferences
# ------------------------------------------------------------------


class TestLearnParameterPreferences:
    def test_finds_best_parameter_value(self, engine, cbkb):
        # value 0.8 is clearly better than 0.6
        for _ in range(5):
            cbkb.add_parameter_lore(
                ParameterLoreEntry(
                    id=f"pl_a_{_}",
                    skill_id="scanpy_cluster",
                    param_name="resolution",
                    param_value="0.8",
                    outcome_metric="silhouette",
                    outcome_value=0.9,
                    project_id="p1",
                    context="",
                    created_at="2024-01-01T00:00:00+00:00",
                )
            )
        for _ in range(5):
            cbkb.add_parameter_lore(
                ParameterLoreEntry(
                    id=f"pl_b_{_}",
                    skill_id="scanpy_cluster",
                    param_name="resolution",
                    param_value="0.6",
                    outcome_metric="silhouette",
                    outcome_value=0.5,
                    project_id="p1",
                    context="",
                    created_at="2024-01-01T00:00:00+00:00",
                )
            )

        prefs = engine.learn_parameter_preferences()
        assert len(prefs) == 1
        assert prefs[0].skill_id == "scanpy_cluster"
        assert prefs[0].param_name == "resolution"
        assert prefs[0].preferred_value == "0.8"
        assert prefs[0].preference_strength >= 1.0
        assert prefs[0].sample_count == 5
        assert "p1" in prefs[0].project_ids

    def test_filters_by_project_id(self, engine, cbkb):
        cbkb.add_parameter_lore(
            ParameterLoreEntry(
                id="pl1",
                skill_id="scanpy_cluster",
                param_name="resolution",
                param_value="0.8",
                outcome_metric="silhouette",
                outcome_value=0.9,
                project_id="p1",
                context="",
                created_at="2024-01-01T00:00:00+00:00",
            )
        )
        cbkb.add_parameter_lore(
            ParameterLoreEntry(
                id="pl2",
                skill_id="scanpy_cluster",
                param_name="resolution",
                param_value="0.6",
                outcome_metric="silhouette",
                outcome_value=0.5,
                project_id="p2",
                context="",
                created_at="2024-01-01T00:00:00+00:00",
            )
        )

        prefs_p1 = engine.learn_parameter_preferences(project_id="p1")
        assert len(prefs_p1) == 0  # only one value per project, no comparison possible


# ------------------------------------------------------------------
# auto_update_sops
# ------------------------------------------------------------------


class TestAutoUpdateSOPs:
    def test_proposes_new_sop_for_repeated_pattern(self, engine, cbkb):
        phases = ["qc", "clustering"]
        for i in range(4):
            cbkb.add_experiment_node(
                ExperimentNode(
                    bundle_id=f"b{i}",
                    project_id="p1",
                    created_at="2024-01-01T00:00:00+00:00",
                    skills_used=["scanpy_qc", "scanpy_cluster"],
                    phases=phases,
                    summary="",
                    metadata={"strategy_type": "sc", "success": True},
                )
            )

        updates = engine.auto_update_sops()
        assert len(updates) == 1
        assert updates[0].sop_id == "sop_auto_qc_clustering"
        assert updates[0].confidence == 1.0
        assert updates[0].proposed_changes["template"]["phases"] == phases
        assert updates[0].derived_from_bundles == ["b0", "b1", "b2", "b3"]

    def test_proposes_version_bump_for_existing_sop(self, engine, cbkb):
        phases = ["qc", "clustering"]
        # Pre-create an SOP that matches the phase pattern
        cbkb.create_sop(
            LabSOP(
                id="sop_qc_clustering",
                name="Existing QC Clustering",
                category="sc",
                template={"phases": phases, "min_genes": 200},
                derived_from_bundle_ids=["old_b"],
                version="1.0",
                locked=False,
            )
        )

        for i in range(4):
            cbkb.add_experiment_node(
                ExperimentNode(
                    bundle_id=f"b{i}",
                    project_id="p1",
                    created_at="2024-01-01T00:00:00+00:00",
                    skills_used=["scanpy_qc", "scanpy_cluster"],
                    phases=phases,
                    summary="",
                    metadata={"strategy_type": "sc", "success": True},
                )
            )

        updates = engine.auto_update_sops()
        assert len(updates) == 1
        assert updates[0].sop_id == "sop_qc_clustering"
        assert updates[0].proposed_changes["version"] == "2.0"
        assert "old_b" in updates[0].proposed_changes["derived_from_bundle_ids"]
        assert "b0" in updates[0].proposed_changes["derived_from_bundle_ids"]

    def test_no_proposal_when_success_count_below_three(self, engine, cbkb):
        for i in range(2):
            cbkb.add_experiment_node(
                ExperimentNode(
                    bundle_id=f"b{i}",
                    project_id="p1",
                    created_at="2024-01-01T00:00:00+00:00",
                    skills_used=["a"],
                    phases=["qc"],
                    summary="",
                    metadata={"success": True},
                )
            )

        updates = engine.auto_update_sops()
        assert updates == []


# ------------------------------------------------------------------
# apply_evolution
# ------------------------------------------------------------------


class TestApplyEvolution:
    def test_applies_metadata_delta(self, engine, role_registry):
        delta = RoleDelta(
            role_id="bioinfo_analyst",
            field_changed="metadata",
            old_value={},
            new_value={"preferred_param_scanpy_cluster_resolution": "0.8"},
            confidence=0.85,
            reason="test",
        )
        count = engine.apply_evolution([delta])
        assert count == 1
        role = role_registry.get("bioinfo_analyst")
        assert role.metadata["preferred_param_scanpy_cluster_resolution"] == "0.8"

    def test_applies_priority_delta(self, engine, role_registry):
        delta = RoleDelta(
            role_id="bioinfo_analyst",
            field_changed="priority",
            old_value=50,
            new_value=70,
            confidence=0.75,
            reason="test",
        )
        count = engine.apply_evolution([delta])
        assert count == 1
        assert role_registry.get("bioinfo_analyst").priority == 70

    def test_skips_missing_role(self, engine):
        delta = RoleDelta(
            role_id="ghost_role",
            field_changed="priority",
            old_value=50,
            new_value=70,
            confidence=0.75,
            reason="test",
        )
        count = engine.apply_evolution([delta])
        assert count == 0

    def test_skips_locked_role(self, engine, role_registry):
        # Inject a locked flag manually (engine checks via getattr)
        role = role_registry.get("viz_specialist")
        object.__setattr__(role, "locked", True)

        delta = RoleDelta(
            role_id="viz_specialist",
            field_changed="priority",
            old_value=100,
            new_value=120,
            confidence=0.75,
            reason="test",
        )
        count = engine.apply_evolution([delta])
        assert count == 0
        assert role_registry.get("viz_specialist").priority == 100
