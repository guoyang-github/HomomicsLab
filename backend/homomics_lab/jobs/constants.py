"""Shared constants for the jobs subsystem (no internal imports)."""

from enum import Enum


class JobStatus(str, Enum):
    """Lifecycle status of a background job."""

    QUEUED = "queued"
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    AWAITING_HUMAN = "awaiting_human"


class JobMode(str, Enum):
    """Execution mode of the job."""

    DIRECT_RESPONSE = "direct_response"
    SINGLE_STEP = "single_step"
    WORKFLOW = "workflow"
    AWAITING_HITL = "awaiting_hitl"
    RESUME_HITL = "resume_hitl"
    CHECKPOINT_RESUME = "checkpoint_resume"
    ERROR = "error"
