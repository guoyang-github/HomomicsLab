"""Unified execution state model for all schedulers."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

# Keys explicitly serialized by ``ExecutionState.to_dict`` / consumed by
# ``from_dict``.  Any additional key found during deserialization is preserved
# in ``ExecutionState.extra`` so custom payloads survive a round-trip.
_SERIALIZED_FIELDS = frozenset({
    "job_id",
    "status",
    "current_phase",
    "progress_pct",
    "started_at",
    "estimated_completion",
    "resource_usage",
    "logs",
    "error_message",
    "scheduler_type",
    "tasks",
    "active_task_id",
    "result",
    "messages",
    "actor",
    "parent_id",
    "extra",
})


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
    # Optional per-task snapshot for agent-driven workflows.
    tasks: Optional[List[Dict[str, Any]]] = None
    active_task_id: Optional[str] = None
    # Optional result summary for terminal states.
    result: Optional[Dict[str, Any]] = None
    # Optional chat messages to inject into the conversation (e.g. final result).
    messages: Optional[List[Dict[str, Any]]] = None
    # Subagent attribution (see homomics_lab.agent.progress_events). Present
    # only when this state was produced by a child execution; top-level
    # executions leave both unset and the keys are omitted from to_dict().
    actor: Optional[str] = None
    parent_id: Optional[str] = None
    # Optional extra top-level payload keys merged into to_dict() (e.g. the
    # domain workflow skeleton / phase marker events).  None for all
    # pre-existing state kinds, so their serialized shape is unchanged.
    extra: Optional[Dict[str, Any]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutionState":
        started_at = data.get("started_at")
        estimated_completion = data.get("estimated_completion")
        extra = dict(data.get("extra") or {})
        for key, value in data.items():
            if key not in _SERIALIZED_FIELDS:
                extra[key] = value
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
            tasks=data.get("tasks"),
            active_task_id=data.get("active_task_id"),
            result=data.get("result"),
            messages=data.get("messages"),
            actor=data.get("actor"),
            parent_id=data.get("parent_id"),
            extra=extra or None,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-friendly dict."""
        payload = {
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
            "tasks": self.tasks,
            "active_task_id": self.active_task_id,
            "result": self.result,
        }
        if self.messages is not None:
            payload["messages"] = self.messages
        # Top-level executions must not carry these keys at all (contract).
        if self.actor is not None and self.parent_id is not None:
            payload["actor"] = self.actor
            payload["parent_id"] = self.parent_id
        if self.extra:
            payload.update(self.extra)
        return payload
