import pytest

from homomics_lab.agent.intent.models import UserIntent
from homomics_lab.agent.sla import SLAEngine
from homomics_lab.config import settings
from homomics_lab.skills.models import SkillDefinition
from homomics_lab.skills.registry import SkillRegistry


def _empty_registry():
    return SkillRegistry()


def _registry_with(*skill_ids):
    reg = SkillRegistry()
    for sid in skill_ids:
        reg.register(
            SkillDefinition(
                id=sid,
                name=sid,
                version="1.0",
                category="test",
                runtime={"type": "python"},
            )
        )
    return reg


@pytest.fixture
def engine(monkeypatch):
    monkeypatch.setattr(settings, "force_sandbox", True)
    return SLAEngine(skill_registry=None)


def test_direct_response_sla(engine):
    intent = UserIntent(analysis_type="qa", complexity="direct_response")
    sla = engine.assess(intent)
    assert sla.execution_mode == "direct_response"
    assert sla.confidence > 0.9


def test_single_cell_with_template(engine):
    intent = UserIntent(analysis_type="single_cell_analysis", complexity="workflow")
    sla = engine.assess(intent)
    assert sla.execution_mode == "auto"
    assert "scanpy_qc" in sla.required_skills
    assert sla.estimated_compute_cost_usd > 0


def test_known_domain_missing_skills_human_required():
    engine = SLAEngine(skill_registry=_empty_registry())
    intent = UserIntent(analysis_type="spatial_analysis", complexity="workflow")
    sla = engine.assess(intent)
    assert sla.execution_mode == "human_required"
    assert "spatial_qc" in sla.missing_skills


def test_known_domain_skills_present_auto():
    engine = SLAEngine(skill_registry=_registry_with("scanpy_qc", "scanpy_normalize", "scanpy_cluster"))
    intent = UserIntent(analysis_type="single_cell_analysis", complexity="workflow")
    sla = engine.assess(intent)
    assert sla.execution_mode == "auto"
    assert not sla.missing_skills
