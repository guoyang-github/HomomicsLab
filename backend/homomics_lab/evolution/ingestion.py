"""CBKB ingestion — turn execution outcomes into structured knowledge.

This module closes the first half of the self-evolution loop:
  1. Record an ExperimentNode for every completed workflow.
  2. Convert phase parameters and outcomes into ParameterLore entries.
  3. Preserve anomaly records already produced by InterpretationEngine.
"""

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from homomics_lab.agent.interpretation import Interpretation
from homomics_lab.agent.plan.models import PlanResult
from homomics_lab.knowledge.cbkb import CBKB, ExperimentNode, ParameterLoreEntry
from homomics_lab.tasks.task_tree import TaskTree


class CBKBIngestionService:
    """Archive workflow execution results into CBKB for later learning."""

    def __init__(self, cbkb: CBKB):
        self.cbkb = cbkb

    def ingest_workflow(
        self,
        project_id: str,
        task_tree: TaskTree,
        plan_result: Optional[PlanResult] = None,
        phase_results: Optional[Dict[str, Any]] = None,
        interpretations: Optional[Dict[str, Interpretation]] = None,
        duration_seconds: Optional[float] = None,
        success: bool = True,
    ) -> str:
        """Ingest a completed workflow and return the generated bundle id."""
        phase_results = phase_results or {}
        interpretations = interpretations or {}

        # Build deterministic bundle id from project + tasks + timestamp.
        tree_key = self._tree_key(task_tree, project_id)
        bundle_id = hashlib.sha256(tree_key.encode()).hexdigest()[:16]

        skills_used: List[str] = []
        phases: List[str] = []
        for task in task_tree.tasks:
            phases.append(task.name)
            skill_id = self._resolve_skill_id(task)
            if skill_id and skill_id not in skills_used:
                skills_used.append(skill_id)

        strategy_name = plan_result.strategy_name if plan_result else "unknown"
        node = ExperimentNode(
            bundle_id=bundle_id,
            project_id=project_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            skills_used=skills_used,
            phases=phases,
            summary=(
                f"Workflow {project_id}: {len(phases)} phases, "
                f"success={success}, strategy={strategy_name}"
            ),
            metadata={
                "success": success,
                "duration_seconds": duration_seconds,
                "strategy_name": strategy_name,
                "n_phases": len(phases),
            },
        )
        self.cbkb.add_experiment_node(node)

        # Parameter lore for each phase.
        for task in task_tree.tasks:
            outcome = self._compute_phase_outcome(task, phase_results, interpretations)
            skill_id = self._resolve_skill_id(task)
            if skill_id is None:
                continue
            for param_name, param_value in task.parameters.items():
                if param_name.startswith("_"):
                    continue
                str_value = self._param_to_str(param_value)
                if str_value is None:
                    continue
                entry = ParameterLoreEntry(
                    id=str(uuid.uuid4()),
                    skill_id=skill_id,
                    param_name=param_name,
                    param_value=str_value,
                    outcome_metric="phase_success",
                    outcome_value=outcome,
                    project_id=project_id,
                    context=f"phase={task.name}, task_id={task.id}, status={task.status.value}",
                    created_at=node.created_at,
                )
                self.cbkb.add_parameter_lore(entry)

        return bundle_id

    @staticmethod
    def _tree_key(task_tree: TaskTree, project_id: str) -> str:
        """Build a stable key for bundle id generation."""
        parts = [project_id]
        for task in task_tree.tasks:
            parts.append(task.id)
            parts.append(task.name)
            parts.extend(sorted(task.skills_required))
        parts.append(datetime.now(timezone.utc).isoformat())
        return "|".join(parts)

    @staticmethod
    def _resolve_skill_id(task) -> Optional[str]:
        """Pick the canonical skill id for a task."""
        if task.skills_required:
            return task.skills_required[0]
        return None

    @staticmethod
    def _param_to_str(value: Any) -> Optional[str]:
        """Serialize a parameter value for CBKB lore."""
        if value is None:
            return None
        if isinstance(value, (str, int, float, bool)):
            return str(value)
        try:
            return json.dumps(value, ensure_ascii=False, sort_keys=True)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _compute_phase_outcome(
        task,
        phase_results: Dict[str, Any],
        interpretations: Dict[str, Interpretation],
    ) -> float:
        """Map a completed task to a scalar outcome value."""
        from homomics_lab.models.common import TaskStatus

        if task.status == TaskStatus.FAILED:
            return 0.0

        interpretation = interpretations.get(task.id)
        if interpretation and interpretation.quality_assessment:
            overall = interpretation.quality_assessment.overall
            if overall == "good":
                return 1.0
            if overall == "acceptable":
                return 0.7
            if overall == "poor":
                return 0.2

        result = phase_results.get(task.id, {})
        if isinstance(result, dict):
            if result.get("status") == "failure" or result.get("error"):
                return 0.0

        if task.status == TaskStatus.COMPLETED:
            return 1.0
        return 0.5
