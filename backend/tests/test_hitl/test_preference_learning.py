"""Tests for HITL preference learning and auto-resolution."""

import pytest

from homomics_lab.hitl.detector import HITLDetector
from homomics_lab.hitl.preference_resolver import HITLPreferenceResolver
from homomics_lab.preferences.store import UserPreferenceStore
from homomics_lab.tasks.models import TaskNode


@pytest.fixture
def preference_store(tmp_path):
    store = UserPreferenceStore(db_path=str(tmp_path / "prefs.db"))
    return store


@pytest.fixture
def resolver(preference_store):
    return HITLPreferenceResolver(preference_store)


def test_record_and_resolve(resolver):
    checkpoint = {
        "id": "cp1",
        "trigger_reason": "high_cost",
        "context_summary": "Task QC is estimated to take 150 minutes.",
        "options": [
            {"id": "proceed", "label": "Proceed"},
            {"id": "cancel", "label": "Cancel"},
        ],
        "metadata": {"scope_type": "task", "scope_id": "qc_task"},
    }
    resolver.record_resolution(
        project_id="proj_1",
        checkpoint=checkpoint,
        choice="proceed",
        remember=True,
    )

    resolved = resolver.try_resolve("proj_1", checkpoint)
    assert resolved is not None
    assert resolved["choice"] == "proceed"
    assert resolved["source"] == "exact"


def test_auto_resolve_sets_default_option(preference_store):
    resolver = HITLPreferenceResolver(preference_store)
    checkpoint = {
        "id": "cp1",
        "trigger_reason": "high_cost",
        "context_summary": "Task QC is estimated to take 150 minutes.",
        "options": [
            {"id": "proceed", "label": "Proceed"},
            {"id": "cancel", "label": "Cancel"},
        ],
        "metadata": {"scope_type": "task", "scope_id": "qc_task"},
    }
    resolver.record_resolution(
        project_id="proj_1",
        checkpoint=checkpoint,
        choice="cancel",
        remember=True,
    )

    detector = HITLDetector(preference_resolver=resolver)
    task = TaskNode(
        id="qc_task",
        name="QC",
        description="Quality control task",
        estimated_duration_minutes=150,
    )
    cp = detector.check(task, {}, project_id="proj_1")
    assert cp is not None
    assert cp.default_option is not None
    assert cp.default_option.id == "cancel"
    assert cp.metadata.get("auto_resolved") is True
