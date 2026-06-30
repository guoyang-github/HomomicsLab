"""Tests for the execution feedback store."""

import pytest

from homomics_lab.context.feedback_store import (
    ExecutionFeedback,
    FeedbackOutcome,
    SQLiteFeedbackStore,
)


@pytest.fixture
def store(tmp_path):
    return SQLiteFeedbackStore(db_path=tmp_path / "feedback.db")


def test_record_and_get_stats(store):
    store.record(
        ExecutionFeedback(
            target_type="skill",
            target_id="scanpy-qc",
            outcome=FeedbackOutcome.SUCCESS,
            project_id="proj-1",
        )
    )
    store.record(
        ExecutionFeedback(
            target_type="skill",
            target_id="scanpy-qc",
            outcome=FeedbackOutcome.SUCCESS,
            project_id="proj-1",
        )
    )
    store.record(
        ExecutionFeedback(
            target_type="skill",
            target_id="scanpy-qc",
            outcome=FeedbackOutcome.FAILURE,
            project_id="proj-1",
        )
    )

    stats = store.get_stats("skill", "scanpy-qc", project_id="proj-1")
    assert stats.usage_count == 3
    assert stats.success_rate == pytest.approx(2 / 3, rel=1e-6)


def test_stats_default_to_neutral_when_no_feedback(store):
    stats = store.get_stats("skill", "unknown")
    assert stats.success_rate == 0.5
    assert stats.usage_count == 0


def test_list_recent_filter(store):
    store.record(
        ExecutionFeedback(
            target_type="memory",
            target_id="mem-1",
            outcome=FeedbackOutcome.SUCCESS,
            project_id="proj-1",
        )
    )
    store.record(
        ExecutionFeedback(
            target_type="skill",
            target_id="scanpy-qc",
            outcome=FeedbackOutcome.FAILURE,
            project_id="proj-2",
        )
    )

    all_recent = store.list_recent(limit=10)
    assert len(all_recent) == 2

    skill_only = store.list_recent(target_type="skill", limit=10)
    assert len(skill_only) == 1
    assert skill_only[0].target_id == "scanpy-qc"
