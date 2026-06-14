"""Pydantic models for background jobs."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field

from homomics_lab.context.working_memory import WorkingMemory
from homomics_lab.tasks.task_tree import TaskTree

from .constants import JobMode, JobStatus


class Job(BaseModel):
    """A background execution job."""

    job_id: str = Field(default_factory=lambda: _new_job_id())
    session_id: str
    project_id: str
    status: JobStatus
    mode: JobMode
    task_tree: Optional[TaskTree] = None
    working_memory: Optional[WorkingMemory] = None
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    resume_task_id: Optional[str] = None
    resume_choice: Optional[str] = None
    resume_parameters: Optional[Dict[str, Any]] = None
    plan_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(arbitrary_types_allowed=True)


def _new_job_id() -> str:
    import uuid

    return f"job_{uuid.uuid4().hex[:12]}"
