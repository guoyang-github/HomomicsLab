from typing import Any, Dict, Optional
from homics_lab.models.common import HITLCheckpoint, HITLTrigger, Option
from homics_lab.tasks.models import TaskNode


class HITLDetector:
    """Detects when human input is required before task execution."""

    DEFAULT_COST_THRESHOLD_MINUTES = 120
    DEFAULT_CONFIDENCE_THRESHOLD = 0.7

    def check(self, task: TaskNode, context: Dict[str, Any]) -> Optional[HITLCheckpoint]:
        # Check explicit checkpoints
        if task.hitl_checkpoints:
            return task.hitl_checkpoints[0]

        # Check cost threshold
        cost_threshold = context.get("cost_threshold_minutes", self.DEFAULT_COST_THRESHOLD_MINUTES)
        if task.estimated_duration_minutes > cost_threshold:
            return self._create_cost_checkpoint(task)

        # Check confidence threshold (mock for MVP)
        confidence = context.get("confidence", 1.0)
        if confidence < self.DEFAULT_CONFIDENCE_THRESHOLD:
            return self._create_confidence_checkpoint(task, confidence)

        return None

    def _create_cost_checkpoint(self, task: TaskNode) -> HITLCheckpoint:
        return HITLCheckpoint(
            id=f"hitl_cost_{task.id}",
            trigger_reason=HITLTrigger.HIGH_COST,
            context_summary=(
                f"Task '{task.name}' is estimated to take "
                f"{task.estimated_duration_minutes} minutes. "
                "Please confirm before proceeding."
            ),
            options=[
                Option(id="proceed", label="Proceed", description="Run the task"),
                Option(id="cancel", label="Cancel", description="Skip this task"),
            ],
        )

    def _create_confidence_checkpoint(self, task: TaskNode, confidence: float) -> HITLCheckpoint:
        return HITLCheckpoint(
            id=f"hitl_conf_{task.id}",
            trigger_reason=HITLTrigger.LOW_CONFIDENCE,
            context_summary=(
                f"Low confidence ({confidence:.2f}) for task '{task.name}'. "
                "Please review parameters."
            ),
            options=[
                Option(id="accept", label="Accept and continue"),
                Option(id="modify", label="Modify parameters"),
            ],
        )
