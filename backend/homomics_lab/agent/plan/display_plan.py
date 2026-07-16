"""Display plan: user-facing representation of what the agent will do.

The execution plan (``TaskTree`` / ``PlanResult.phases``) is optimised for the
runtime: it contains dependencies, skill bindings, parameters, and may collapse
multiple user-level goals into a single task.  The display plan is optimised for
humans: each step maps to a clear user-intent fragment ("annotate cells",
"compare with all_celltype") and has its own status for the TODO checklist.

Keeping the two separate means:
* The TODO list is stable even when the runtime reorders or merges tasks.
* A single runtime task can surface several semantic sub-steps.
* Future UIs (timeline, workflow, report) can consume the display plan without
  parsing execution-task parameters.
"""

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class DisplayStepStatus(str, Enum):
    """Lifecycle of a display step."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class DisplayStep:
    """A single user-facing step in the display plan."""

    id: str
    description: str
    status: DisplayStepStatus = DisplayStepStatus.PENDING
    # Semantic category, e.g. "annotation", "label_comparison", "visualization".
    analysis_type: Optional[str] = None
    # Underlying execution phase, when known.
    phase_type: Optional[str] = None
    # Skill or source that owns this step.
    source: Optional[str] = None
    # Extra UI hints (icon, colour, estimated duration, etc.).
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DisplayStep":
        data = dict(data)
        status = data.get("status", DisplayStepStatus.PENDING.value)
        data["status"] = DisplayStepStatus(status)
        return cls(**data)


@dataclass
class DisplayPlan:
    """A collection of user-facing steps derived from an execution plan."""

    steps: List[DisplayStep] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {"steps": [s.to_dict() for s in self.steps]}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DisplayPlan":
        return cls(steps=[DisplayStep.from_dict(s) for s in data.get("steps", [])])

    def is_empty(self) -> bool:
        return not self.steps
