from typing import Any, Dict, List, Optional

from homomics_lab.hitl.preference_resolver import HITLPreferenceResolver
from homomics_lab.models.common import HITLCheckpoint, HITLTrigger, Option
from homomics_lab.tasks.models import TaskNode


class HITLDetector:
    """Detects when human input is required before task execution."""

    DEFAULT_COST_THRESHOLD_MINUTES = 120
    DEFAULT_CONFIDENCE_THRESHOLD = 0.7

    def __init__(self, preference_resolver: Optional[HITLPreferenceResolver] = None):
        self.preference_resolver = preference_resolver

    def check(
        self,
        task: TaskNode,
        context: Dict[str, Any],
        project_id: Optional[str] = None,
    ) -> Optional[HITLCheckpoint]:
        # Check explicit checkpoints
        if task.hitl_checkpoints:
            checkpoint = task.hitl_checkpoints[0]
            self._apply_preference_defaults(project_id, checkpoint)
            return checkpoint

        # Check cost threshold
        cost_threshold = context.get("cost_threshold_minutes", self.DEFAULT_COST_THRESHOLD_MINUTES)
        if task.estimated_duration_minutes > cost_threshold:
            return self._create_cost_checkpoint(task, project_id=project_id)

        # Check confidence threshold (mock for MVP)
        confidence = context.get("confidence", 1.0)
        if confidence < self.DEFAULT_CONFIDENCE_THRESHOLD:
            return self._create_confidence_checkpoint(task, confidence, project_id=project_id)

        return None

    def _create_cost_checkpoint(
        self,
        task: TaskNode,
        project_id: Optional[str] = None,
    ) -> HITLCheckpoint:
        options: List[Option] = [
            Option(id="proceed", label="Proceed", description="Run the task"),
            Option(id="cancel", label="Cancel", description="Skip this task"),
        ]
        checkpoint = HITLCheckpoint(
            id=f"hitl_cost_{task.id}",
            trigger_reason=HITLTrigger.HIGH_COST,
            context_summary=(
                f"Task '{task.name}' is estimated to take "
                f"{task.estimated_duration_minutes} minutes. "
                "Please confirm before proceeding."
            ),
            options=options,
            metadata={"scope_type": "task", "scope_id": task.id, "task_name": task.name},
        )
        self._apply_preference_defaults(project_id, checkpoint)
        return checkpoint

    def _create_confidence_checkpoint(
        self,
        task: TaskNode,
        confidence: float,
        project_id: Optional[str] = None,
    ) -> HITLCheckpoint:
        options: List[Option] = [
            Option(id="accept", label="Accept and continue"),
            Option(id="modify", label="Modify parameters"),
        ]
        checkpoint = HITLCheckpoint(
            id=f"hitl_conf_{task.id}",
            trigger_reason=HITLTrigger.LOW_CONFIDENCE,
            context_summary=(
                f"Low confidence ({confidence:.2f}) for task '{task.name}'. "
                "Please review parameters."
            ),
            options=options,
            metadata={"scope_type": "task", "scope_id": task.id, "task_name": task.name},
        )
        self._apply_preference_defaults(project_id, checkpoint)
        return checkpoint

    def _apply_preference_defaults(
        self,
        project_id: Optional[str],
        checkpoint: HITLCheckpoint,
    ) -> None:
        if not project_id or self.preference_resolver is None:
            return
        resolved = self.preference_resolver.try_resolve(project_id, checkpoint.model_dump())
        if resolved:
            checkpoint.default_option = next(
                (o for o in checkpoint.options if o.id == resolved["choice"]),
                checkpoint.default_option,
            )
            checkpoint.metadata["auto_resolved"] = True
            checkpoint.metadata["resolved_choice"] = resolved["choice"]
            checkpoint.metadata["resolved_parameters"] = resolved.get("parameters", {})
