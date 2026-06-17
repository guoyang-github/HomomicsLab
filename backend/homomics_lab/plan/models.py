"""Pydantic models for persisted execution plans."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from homomics_lab.agent.plan.models import PlanResult
from homomics_lab.context.working_memory import WorkingMemory
from homomics_lab.models.common import utc_now
from homomics_lab.tasks.task_tree import TaskTree


class PlanStatus:
    """Lifecycle states of a persisted plan."""

    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"


class Plan(BaseModel):
    """A persisted execution plan that links a PlanResult to a TaskTree."""

    plan_id: str
    session_id: str
    project_id: str
    status: str = PlanStatus.PENDING_APPROVAL
    is_fallback: bool = False
    intent_analysis_type: str
    intent_complexity: Optional[str] = None
    plan_result: PlanResult
    task_tree: TaskTree
    working_memory: Optional[WorkingMemory] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    parent_plan_id: Optional[str] = None
    version: int = 1
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    model_config = ConfigDict(arbitrary_types_allowed=True)


class PlanModification(BaseModel):
    """A single user modification to a plan phase."""

    phase_type: str
    action: str = "update"  # "update" | "remove" | "add" | "update_dependency"
    parameter: Optional[str] = None
    old_value: Optional[Any] = None
    new_value: Optional[Any] = None

    # Structural modification fields.
    after: Optional[str] = None      # insert new phase after this phase
    before: Optional[str] = None     # insert new phase before this phase
    description: Optional[str] = None
    required: Optional[bool] = None
    skill_id: Optional[str] = None
    dependencies: Optional[List[str]] = None  # for add / update_dependency


class PlanApprovalRequest(BaseModel):
    """User decision on a pending plan."""

    approved: bool = True
    modifications: List[PlanModification] = Field(default_factory=list)


class PlanApprovalResponse(BaseModel):
    """Response after approving or rejecting a plan."""

    plan_id: str
    status: str
    job_id: Optional[str] = None


class PlanDetailResponse(BaseModel):
    """Full plan payload returned by the API."""

    plan_id: str
    session_id: str
    project_id: str
    status: str
    is_fallback: bool
    intent_analysis_type: str
    intent_complexity: Optional[str]
    plan: Dict[str, Any]
    approved_by: Optional[str]
    approved_at: Optional[datetime]
    parent_plan_id: Optional[str]
    version: int
    created_at: datetime
    updated_at: datetime
