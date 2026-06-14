"""Convert persisted plans into user-facing payloads."""

from typing import Any, Dict, List

from .models import Plan


class PlanPresenter:
    """Build human-readable plan previews for the frontend."""

    @staticmethod
    def to_user_payload(plan: Plan) -> Dict[str, Any]:
        """Return a dict suitable for the plan approval UI."""
        phases: List[Dict[str, Any]] = []
        task_lookup = {t.name: t for t in (plan.task_tree.tasks or [])}

        for phase in plan.plan_result.phases:
            skill_id = None
            if phase.selected_skill is not None:
                skill_id = phase.selected_skill.id
            else:
                # Fall back to the corresponding task's skills if available.
                task = task_lookup.get(phase.phase_type)
                if task is not None and task.skills_required:
                    skill_id = task.skills_required[0]

            phases.append(
                {
                    "phase_type": phase.phase_type,
                    "description": phase.description,
                    "required": phase.required,
                    "skill_id": skill_id,
                    "readonly": phase.readonly,
                }
            )

        gaps = [
            {
                "from_phase": gap.from_phase,
                "to_phase": gap.to_phase,
                "gap_type": gap.gap_type,
                "estimated_complexity": gap.estimated_complexity,
                "requires_hitl": gap.requires_hitl,
            }
            for gap in plan.plan_result.gaps
        ]

        return {
            "plan_id": plan.plan_id,
            "status": plan.status,
            "is_fallback": plan.is_fallback,
            "intent_analysis_type": plan.intent_analysis_type,
            "phases": phases,
            "gaps": gaps,
            "suggestion_text": plan.plan_result.suggestion_text,
            "created_at": plan.created_at.isoformat() if plan.created_at else None,
            "version": plan.version,
        }

    @staticmethod
    def to_summary(plan: Plan) -> str:
        """Return a one-sentence summary of a plan."""
        phase_count = len(plan.plan_result.phases)
        if plan.is_fallback:
            return f"LLM 生成的分析计划，包含 {phase_count} 个步骤，需要您确认。"
        return f"分析计划包含 {phase_count} 个步骤。"
