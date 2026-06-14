"""Tests for the unified ExecutionState model."""

from datetime import datetime, timezone

from homomics_lab.hpc.state import ExecutionState


class TestExecutionState:
    def test_to_dict_serializes_all_fields(self):
        started = datetime.now(timezone.utc)
        state = ExecutionState(
            job_id="job_123",
            status="RUNNING",
            current_phase="qc",
            progress_pct=42.0,
            started_at=started,
            estimated_completion=started,
            resource_usage={"cpu": 2},
            logs=["line1"],
            error_message=None,
            scheduler_type="local",
        )
        data = state.to_dict()
        assert data["job_id"] == "job_123"
        assert data["status"] == "RUNNING"
        assert data["current_phase"] == "qc"
        assert data["progress_pct"] == 42.0
        assert data["started_at"] == started.isoformat()
        assert data["estimated_completion"] == started.isoformat()
        assert data["resource_usage"] == {"cpu": 2}
        assert data["logs"] == ["line1"]
        assert data["error_message"] is None
        assert data["scheduler_type"] == "local"
