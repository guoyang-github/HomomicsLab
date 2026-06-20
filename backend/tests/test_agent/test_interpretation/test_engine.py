"""Tests for InterpretationEngine."""

import pytest

from homomics_lab.agent.interpretation import InterpretationEngine
from homomics_lab.agent.plan.models import DataState, Phase
from homomics_lab.skills.models import SkillDefinition, SkillInputSchema
from homomics_lab.skills.registry import SkillRegistry
from homomics_lab.skills.skill_dag import EdgeStatus, EdgeType, SkillDAG


@pytest.fixture
def skill_dag_with_followed_by(tmp_path):
    reg = SkillRegistry()
    reg.register(
        SkillDefinition(id="scanpy_qc", name="scanpy_qc", version="1.0", category="test", input_schema=SkillInputSchema())
    )
    reg.register(
        SkillDefinition(id="scanpy_pca", name="scanpy_pca", version="1.0", category="test", input_schema=SkillInputSchema())
    )
    dag = SkillDAG(registry=reg, db_path=tmp_path / "dag.db")
    dag.propose_edge("scanpy_qc", "scanpy_pca", EdgeType.FOLLOWED_BY)
    dag.edges["scanpy_qc_followed_by_scanpy_pca"].status = EdgeStatus.CONFIRMED
    dag.edges["scanpy_qc_followed_by_scanpy_pca"].confidence = 0.85
    return dag


class TestInterpretationEngine:
    def test_qc_interpretation_normal(self, skill_dag_with_followed_by):
        engine = InterpretationEngine(skill_dag=skill_dag_with_followed_by)
        phase = Phase(phase_type="qc", selected_skill=skill_dag_with_followed_by.registry.get("scanpy_qc"))
        result = engine.interpret_phase(
            phase=phase,
            skill_output={"input_cells": 2700, "output_cells": 2531},
            data_state=DataState(),
        )

        assert "2,531" in result.summary or "2531" in result.summary
        assert "2,700" in result.summary or "2700" in result.summary
        assert result.quality_assessment.overall == "good"
        assert not result.quality_assessment.has_anomaly()
        assert len(result.recommendations) > 0

    def test_qc_interpretation_high_filtering(self, skill_dag_with_followed_by):
        engine = InterpretationEngine(skill_dag=skill_dag_with_followed_by)
        phase = Phase(phase_type="qc", selected_skill=skill_dag_with_followed_by.registry.get("scanpy_qc"))
        result = engine.interpret_phase(
            phase=phase,
            skill_output={"input_cells": 1000, "output_cells": 400},
            data_state=DataState(),
        )

        assert result.quality_assessment.overall in ("acceptable", "poor")
        assert result.quality_assessment.has_anomaly()
        assert any("filtering rate" in f.lower() for f in result.quality_assessment.flags)
        # Should have caution recommendation
        assert any(r.type == "caution" for r in result.recommendations)

    def test_clustering_interpretation(self, skill_dag_with_followed_by):
        engine = InterpretationEngine()
        phase = Phase(phase_type="clustering")
        result = engine.interpret_phase(
            phase=phase,
            skill_output={"n_clusters": 2},
            data_state=DataState(),
        )

        assert "2" in result.summary
        assert result.quality_assessment.has_anomaly()
        assert any(r.type == "alternative" for r in result.recommendations)

    def test_flow_recommendation_after_qc(self, skill_dag_with_followed_by):
        engine = InterpretationEngine(skill_dag=skill_dag_with_followed_by)
        phase = Phase(phase_type="qc", selected_skill=skill_dag_with_followed_by.registry.get("scanpy_qc"))
        result = engine.interpret_phase(
            phase=phase,
            skill_output={"input_cells": 2700, "output_cells": 2531},
            data_state=DataState(),
        )

        # Should recommend normalization (next step in flow)
        assert any("normalization" in r.description.lower() for r in result.recommendations)

    def test_skill_dag_recommendation(self, skill_dag_with_followed_by):
        engine = InterpretationEngine(skill_dag=skill_dag_with_followed_by)
        phase = Phase(phase_type="qc", selected_skill=skill_dag_with_followed_by.registry.get("scanpy_qc"))
        result = engine.interpret_phase(
            phase=phase,
            skill_output={"input_cells": 2700, "output_cells": 2531},
            data_state=DataState(),
        )

        # Should recommend scanpy_pca via SkillDAG followed_by edge
        assert any(r.skill_id == "scanpy_pca" for r in result.recommendations)

    def test_no_recommendation_when_already_done(self, skill_dag_with_followed_by):
        engine = InterpretationEngine()
        phase = Phase(phase_type="qc")
        data_state = DataState(has_normalization=True)
        result = engine.interpret_phase(
            phase=phase,
            skill_output={"input_cells": 2700, "output_cells": 2531},
            data_state=data_state,
        )

        # Should NOT recommend normalization since it's already done
        assert not any("normalization" in r.description.lower() for r in result.recommendations)

    def test_to_triggers_high_filtering_qc(self, skill_dag_with_followed_by):
        engine = InterpretationEngine(skill_dag=skill_dag_with_followed_by)
        phase = Phase(phase_type="qc", selected_skill=skill_dag_with_followed_by.registry.get("scanpy_qc"))
        result = engine.interpret_phase(
            phase=phase,
            skill_output={"input_cells": 1000, "output_cells": 300},
            data_state=DataState(),
        )

        triggers = engine.to_triggers(result, phase)

        assert any(t.trigger_type == "anomaly_detected" for t in triggers)
        anomaly = next(t for t in triggers if t.trigger_type == "anomaly_detected")
        assert anomaly.severity in ("major", "critical")

    def test_to_triggers_missing_downstream(self, skill_dag_with_followed_by):
        engine = InterpretationEngine(skill_dag=skill_dag_with_followed_by)
        phase = Phase(phase_type="qc", selected_skill=skill_dag_with_followed_by.registry.get("scanpy_qc"))
        result = engine.interpret_phase(
            phase=phase,
            skill_output={"input_cells": 2700, "output_cells": 2531},
            data_state=DataState(),
        )

        triggers = engine.to_triggers(result, phase)

        assert any(
            t.trigger_type == "data_state_changed"
            and t.context.get("change_type") == "missing_downstream"
            and t.context.get("recommended_phase_type") == "dim_reduction"
            for t in triggers
        )

    def test_to_triggers_clustering_alternative(self):
        engine = InterpretationEngine()
        phase = Phase(phase_type="clustering")
        result = engine.interpret_phase(
            phase=phase,
            skill_output={"n_clusters": 2},
            data_state=DataState(),
        )

        triggers = engine.to_triggers(result, phase)

        assert any(
            t.trigger_type == "anomaly_detected"
            and t.context.get("phase_type") == "clustering"
            for t in triggers
        )

    def test_to_triggers_normal_qc_empty(self, skill_dag_with_followed_by):
        engine = InterpretationEngine(skill_dag=skill_dag_with_followed_by)
        phase = Phase(phase_type="qc", selected_skill=skill_dag_with_followed_by.registry.get("scanpy_qc"))
        result = engine.interpret_phase(
            phase=phase,
            skill_output={"input_cells": 2700, "output_cells": 2531},
            data_state=DataState(has_normalization=True),
        )

        triggers = engine.to_triggers(result, phase)

        assert not any(t.trigger_type == "anomaly_detected" for t in triggers)
