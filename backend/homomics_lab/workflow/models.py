"""Models for the Workflow execution layer."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from homomics_lab.tasks.task_tree import TaskTree


@dataclass
class WorkflowArtifact:
    """An artifact produced by a workflow execution."""

    path: str
    artifact_type: str  # "data" | "intermediate" | "output" | "log"
    task_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowResult:
    """Result of executing a Plan through the WorkflowExecutionService."""

    success: bool
    backend: str  # "local" | "nextflow" | "slurm"
    task_tree: TaskTree
    artifacts: List[WorkflowArtifact] = field(default_factory=list)
    error_message: Optional[str] = None
    logs: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
