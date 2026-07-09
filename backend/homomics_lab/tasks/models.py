from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from homomics_lab.models.common import HITLCheckpoint, TaskStatus


class RetryPolicy(BaseModel):
    max_attempts: int = 3
    backoff_seconds: float = 2.0
    retry_on: List[str] = Field(default_factory=lambda: ["timeout", "transient_error"])


class TaskNode(BaseModel):
    id: str
    name: str
    description: str
    phase: str = "execution"
    status: TaskStatus = TaskStatus.PENDING
    dependencies: List[str] = Field(default_factory=list)
    agent_assignment: Optional[str] = None
    skills_required: List[str] = Field(default_factory=list)
    hitl_checkpoints: List[HITLCheckpoint] = Field(default_factory=list)
    estimated_duration_minutes: int = 10
    estimated_cost_usd: Optional[float] = None
    estimated_input_tokens: Optional[int] = None
    estimated_output_tokens: Optional[int] = None
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    success_criteria: List[Dict[str, Any]] = Field(default_factory=list)
    pre_snapshot_id: Optional[str] = None
    post_snapshot_id: Optional[str] = None
    gate_result: Optional[Dict[str, Any]] = None
    replan_attempt_count: int = 0
    max_replan_attempts: int = 2
    adaptive_replan_count: int = 0
    max_adaptive_replan_attempts: int = 2
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    attempt_count: int = 0

    # Provenance / anti-hallucination metadata.
    derivation: Optional[str] = None  # "domain-strategy" | "standalone-skill" | "llm-fallback" | "hardcoded"
    risk_level: str = "low"  # "low" | "medium" | "high"

    # Incremental execution / caching metadata
    input_hash: Optional[str] = None
    output_hash: Optional[str] = None
    cache_key: Optional[str] = None
    cache_hit: bool = False


class TaskTreeSnapshot(BaseModel):
    """Serializable snapshot of a task tree for persistence."""
    project_id: str
    session_id: str
    tasks: List[TaskNode]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
