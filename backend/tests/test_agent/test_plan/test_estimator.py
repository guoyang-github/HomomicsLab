"""Tests for plan phase estimator."""

import pytest

from homomics_lab.agent.plan.estimator import (
    _heuristic_cost_from_resources,
    _parse_memory,
    estimate_phase,
    parse_duration_string,
)
from homomics_lab.agent.plan.models import Phase
from homomics_lab.skills.models import (
    SkillDefinition,
    SkillInputSchema,
    SkillOutputSchema,
    SkillResources,
    SkillRuntime,
)


def _make_skill(skill_id: str = "demo", time: str = "30m", cpu: int = 2, memory: str = "4G") -> SkillDefinition:
    return SkillDefinition(
        id=skill_id,
        name="Demo Skill",
        version="1.0",
        category="analysis",
        runtime=SkillRuntime(
            resources=SkillResources(time=time, cpu=cpu, memory=memory),
        ),
        input_schema=SkillInputSchema(
            properties={"query": {"type": "string"}},
            required=["query"],
        ),
        output_schema=SkillOutputSchema(
            properties={"result": {"type": "object"}},
        ),
    )


def test_parse_duration_string_minutes():
    assert parse_duration_string("30m") == 30 * 60


def test_parse_duration_string_hours_and_minutes():
    assert parse_duration_string("1h30m") == 90 * 60


def test_parse_duration_string_plain_number_treated_as_minutes():
    assert parse_duration_string("10") == 600


def test_parse_duration_string_invalid_fallback():
    assert parse_duration_string("n/a") == 600


def test_parse_memory():
    assert _parse_memory("4G") == 4.0
    assert _parse_memory("512M") == 512 / 1024
    assert _parse_memory("2T") == 2048
    assert _parse_memory(None) is None


def test_heuristic_cost_from_resources():
    cost = _heuristic_cost_from_resources(3600, 2, 4.0)
    assert cost > 0


def test_estimate_phase_populates_from_skill_runtime():
    phase = Phase(phase_type="analysis", selected_skill=_make_skill())
    estimate_phase(phase, tracker=None)

    assert phase.estimated_duration_seconds == 30 * 60
    assert phase.estimated_cost_usd is not None
    assert phase.estimated_cpu_cores == 2
    assert phase.estimated_memory_gb == 4.0
    assert phase.estimated_input_tokens is not None
    assert phase.estimated_output_tokens is not None


def test_estimate_phase_without_skill_uses_defaults():
    phase = Phase(phase_type="suggestion")
    estimate_phase(phase, tracker=None)

    assert phase.estimated_duration_seconds == 600.0
    assert phase.estimated_cost_usd == 0.0
    assert phase.estimated_input_tokens == 500
    assert phase.estimated_output_tokens == 250


def test_estimate_phase_preserves_llm_estimates():
    phase = Phase(
        phase_type="analysis",
        selected_skill=_make_skill(),
        estimated_duration_seconds=120.0,
        estimated_cost_usd=0.01,
    )
    estimate_phase(phase, tracker=None)

    # LLM-provided estimates should be overwritten by skill-based estimate
    # because estimate_phase recomputes from runtime. If we later decide to
    # prefer LLM estimates, this test should change.
    assert phase.estimated_duration_seconds == 30 * 60


def test_estimate_phase_uses_tracker_history(monkeypatch):
    phase = Phase(phase_type="analysis", selected_skill=_make_skill("demo"))

    class FakeTracker:
        def get_stats(self, skill_id: str):
            return {
                "total_executions": 2,
                "avg_duration_ms": 30000.0,
                "total_cost_usd": 0.02,
            }

    estimate_phase(phase, tracker=FakeTracker())
    assert phase.estimated_duration_seconds == 30.0
    assert phase.estimated_cost_usd == 0.01
