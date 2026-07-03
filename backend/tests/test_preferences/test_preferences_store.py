"""Tests for the user preference store."""

import pytest

from homomics_lab.preferences.store import UserPreferenceStore


@pytest.fixture
def store(tmp_path):
    return UserPreferenceStore(db_path=str(tmp_path / "preferences.db"))


def test_record_and_get_preference(store):
    store.record(
        project_id="proj-1",
        scope_type="skill",
        scope_id="qc",
        key="trim_adapter",
        value="trimmomatic",
    )
    rows = store.get(project_id="proj-1", scope_type="skill", scope_id="qc")
    assert len(rows) == 1
    assert store.get_default(
        project_id="proj-1", scope_type="skill", scope_id="qc", key="trim_adapter"
    ) == "trimmomatic"


def test_record_updates_existing_preference(store):
    """Regression test: ON CONFLICT DO UPDATE requires a UNIQUE constraint."""
    store.record(
        project_id="proj-1",
        scope_type="skill",
        scope_id="qc",
        key="trim_adapter",
        value="trimmomatic",
    )
    store.record(
        project_id="proj-1",
        scope_type="skill",
        scope_id="qc",
        key="trim_adapter",
        value="cutadapt",
    )
    rows = store.get(project_id="proj-1", scope_type="skill", scope_id="qc")
    assert len(rows) == 1
    assert store.get_default(
        project_id="proj-1", scope_type="skill", scope_id="qc", key="trim_adapter"
    ) == "cutadapt"


def test_get_filters_by_project(store):
    store.record(project_id="proj-a", scope_type="generic", scope_id=None, key=None, value="x")
    store.record(project_id="proj-b", scope_type="generic", scope_id=None, key=None, value="y")
    assert len(store.get(project_id="proj-a")) == 1
    assert len(store.get(project_id="proj-b")) == 1
