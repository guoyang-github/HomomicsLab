"""Unified execution state model for all schedulers."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class ExecutionState:
    """Common progress/state abstraction for local, SLURM, and Nextflow jobs."""

    job_id: str
    status: str  # PENDING | RUNNING | COMPLETED | FAILED | CANCELLED
    current_phase: Optional[str] = None
    progress_pct: float = 0.0
    started_at: Optional[datetime] = None
    estimated_completion: Optional[datetime] = None
    resource_usage: Dict[str, Any] = field(default_factory=dict)
    logs: List[str] = field(default_factory=list)
    error_message: Optional[str] = None
    scheduler_type: str = "unknown"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutionState":
        started_at = data.get("started_at")
        estimated_completion = data.get("estimated_completion")
        return cls(
            job_id=data["job_id"],
            status=data["status"],
            current_phase=data.get("current_phase"),
            progress_pct=data.get("progress_pct", 0.0),
            started_at=datetime.fromisoformat(started_at) if started_at else None,
            estimated_completion=datetime.fromisoformat(estimated_completion)
            if estimated_completion
            else None,
            resource_usage=data.get("resource_usage", {}),
            logs=data.get("logs", []),
            error_message=data.get("error_message"),
            scheduler_type=data.get("scheduler_type", "unknown"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-friendly dict."""
        return {
            "job_id": self.job_id,
            "status": self.status,
            "current_phase": self.current_phase,
            "progress_pct": self.progress_pct,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "estimated_completion": (
                self.estimated_completion.isoformat()
                if self.estimated_completion
                else None
            ),
            "resource_usage": self.resource_usage,
            "logs": self.logs,
            "error_message": self.error_message,
            "scheduler_type": self.scheduler_type,
        }
