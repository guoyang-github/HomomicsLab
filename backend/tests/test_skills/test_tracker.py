import pytest
from pathlib import Path

from homomics_lab.skills.tracker import SkillPerformanceTracker, ExecutionRecord


@pytest.fixture
def tracker(tmp_path):
    db = tmp_path / "test_metrics.db"
    return SkillPerformanceTracker(db_path=db)


class TestSkillPerformanceTracker:
    def test_record_execution(self, tracker):
        tracker.record(
            skill_id="test-skill",
            duration_ms=150.5,
            success=True,
            output_size=1024,
            executor_type="local",
        )

        stats = tracker.get_stats("test-skill")
        assert stats["total_executions"] == 1
        assert stats["success_rate"] == 100.0
        assert stats["avg_duration_ms"] == 150.5

    def test_record_multiple_executions(self, tracker):
        for i in range(5):
            tracker.record(
                skill_id="test-skill",
                duration_ms=100.0 + i * 10,
                success=(i < 4),  # 4 successes, 1 failure
                output_size=100 * i,
            )

        stats = tracker.get_stats("test-skill")
        assert stats["total_executions"] == 5
        assert stats["success_rate"] == 80.0
        assert stats["avg_duration_ms"] == 120.0

    def test_get_stats_empty(self, tracker):
        stats = tracker.get_stats("nonexistent")
        assert stats["total_executions"] == 0
        assert stats["success_rate"] == 0.0

    def test_get_recent_executions(self, tracker):
        tracker.record("skill-a", 100.0, True)
        tracker.record("skill-b", 200.0, False)
        tracker.record("skill-a", 150.0, True)

        recent = tracker.get_recent_executions(limit=10)
        assert len(recent) == 3

        filtered = tracker.get_recent_executions(skill_id="skill-a", limit=10)
        assert len(filtered) == 2
        assert all(r.skill_id == "skill-a" for r in filtered)

    def test_get_top_skills(self, tracker):
        tracker.record("popular", 100.0, True)
        tracker.record("popular", 110.0, True)
        tracker.record("popular", 90.0, True)
        tracker.record("rare", 200.0, True)

        top = tracker.get_top_skills(limit=2)
        assert len(top) == 2
        assert top[0]["skill_id"] == "popular"
        assert top[0]["total_executions"] == 3

    def test_compare_skills(self, tracker):
        for _ in range(5):
            tracker.record("skill-a", 100.0, True)
        for _ in range(3):
            tracker.record("skill-b", 200.0, False)

        comparison = tracker.compare_skills("skill-a", "skill-b")
        assert comparison["skill_a"]["total_executions"] == 5
        assert comparison["skill_b"]["total_executions"] == 3
        assert comparison["comparison"]["success_rate_diff"] == 100.0

    def test_record_with_error(self, tracker):
        tracker.record(
            skill_id="failing-skill",
            duration_ms=50.0,
            success=False,
            error_message="ImportError: No module named 'missing'",
        )

        recent = tracker.get_recent_executions(skill_id="failing-skill")
        assert len(recent) == 1
        assert recent[0].success is False
        assert "ImportError" in recent[0].error_message

    def test_record_with_metadata(self, tracker):
        tracker.record(
            skill_id="meta-skill",
            duration_ms=100.0,
            success=True,
            metadata={"input_rows": 1000, "output_rows": 500},
        )

        recent = tracker.get_recent_executions(skill_id="meta-skill")
        assert recent[0].metadata == {"input_rows": 1000, "output_rows": 500}
