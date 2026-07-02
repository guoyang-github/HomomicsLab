"""Convert persisted plans into user-facing payloads."""

import json
from typing import Any, Dict, List, Optional

from .models import Plan


class PlanPresenter:
    """Build human-readable plan previews for the frontend."""

    _SUMMARY_TEMPLATES = {
        "zh": {
            "fallback": "LLM 生成的分析计划，包含 {phase_count} 个步骤，需要您确认。",
            "standard": "分析计划包含 {phase_count} 个步骤。",
        },
        "en": {
            "fallback": "LLM-generated analysis plan with {phase_count} step(s); please review.",
            "standard": "Analysis plan with {phase_count} step(s).",
        },
    }

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
                    "parameters": phase.parameters,
                    "parameter_recommendations": phase.parameter_recommendations,
                    "parameter_sources": phase.parameter_sources,
                    "estimated_cost_usd": phase.estimated_cost_usd,
                    "estimated_duration_seconds": phase.estimated_duration_seconds,
                    "estimated_input_tokens": phase.estimated_input_tokens,
                    "estimated_output_tokens": phase.estimated_output_tokens,
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

        transitions = [
            {
                "from": t.get("from"),
                "to": t.get("to"),
                "type": t.get("type"),
            }
            for t in plan.plan_result.phase_transitions
        ]

        trace = plan.plan_result.strategy_trace
        template_id = None
        template_name = None
        strategy_candidates = []
        quality_score = None
        rationale_summary = ""
        if trace is not None:
            template_id = trace.applied_template_id
            template_name = trace.applied_template_name
            strategy_candidates = trace.strategy_candidates
            quality_score = trace.quality_score
            rationale_summary = PlanPresenter._build_rationale_summary(plan, trace)

        return {
            "plan_id": plan.plan_id,
            "status": plan.status,
            "is_fallback": plan.is_fallback,
            "intent_analysis_type": plan.intent_analysis_type,
            "strategy_name": plan.plan_result.strategy_name,
            "template_id": template_id,
            "template_name": template_name,
            "rationale_summary": rationale_summary,
            "strategy_candidates": strategy_candidates,
            "quality_score": quality_score,
            "phases": phases,
            "transitions": transitions,
            "gaps": gaps,
            "suggestion_text": plan.plan_result.suggestion_text,
            "created_at": plan.created_at.isoformat() if plan.created_at else None,
            "version": plan.version,
            "total_estimated_cost_usd": plan.plan_result.total_estimated_cost_usd,
            "total_estimated_duration_seconds": plan.plan_result.total_estimated_duration_seconds,
        }

    @staticmethod
    def _build_rationale_summary(plan: Plan, trace) -> str:
        """Build a short human-readable rationale for why this plan was chosen."""
        phase_count = len(plan.plan_result.phases)
        candidate_names = ", ".join(
            f"{c['name']}({c['score']})" for c in trace.strategy_candidates[:3]
        )
        if plan.plan_result.is_fallback:
            return (
                f"未找到完全匹配的策略，已使用 fallback 计划（{phase_count} 个步骤）。"
                f"候选策略：{candidate_names}。"
            )
        template_part = ""
        if trace.applied_template_id:
            template_name = trace.applied_template_name or trace.applied_template_id
            template_part = f"并应用了模板 '{template_name}'。"
        return (
            f"根据意图 '{trace.intent_analysis_type}' 选择了策略 '{trace.selected_strategy_name}'，"
            f"包含 {phase_count} 个步骤。{template_part}"
            f"候选策略：{candidate_names}。"
        )

    @classmethod
    async def to_summary(
        cls,
        plan: Plan,
        language: str = "zh",
        llm_client: Optional[Any] = None,
    ) -> str:
        """Return a one-sentence summary of a plan.

        If an ``llm_client`` is provided, the summary is generated dynamically
        from plan metadata and localized to ``language`` (``en`` or ``zh``).
        Otherwise a localized template fallback is returned.
        """
        phase_count = len(plan.plan_result.phases)

        if (
            llm_client is None
            or not getattr(llm_client, "is_configured", lambda: False)()
        ):
            return cls._fallback_summary(plan, language, phase_count)

        plan_metadata = {
            "intent": plan.intent_analysis_type,
            "is_fallback": plan.is_fallback,
            "phase_count": phase_count,
            "phases": [
                {
                    "type": p.phase_type,
                    "description": p.description,
                    "skill": p.selected_skill.id if p.selected_skill else None,
                }
                for p in plan.plan_result.phases
            ],
        }

        system_prompt = (
            f"You are a bioinformatics plan summarizer. Produce a concise, "
            f"one-sentence summary of the following analysis plan in {language}. "
            f"Respond with only the summary sentence, no markdown."
        )
        user_prompt = f"Plan metadata: {json.dumps(plan_metadata, ensure_ascii=False)}"

        try:
            summary = await llm_client.chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=200,
            )
            return summary.strip() or cls._fallback_summary(plan, language, phase_count)
        except Exception:
            return cls._fallback_summary(plan, language, phase_count)

    @classmethod
    def _fallback_summary(cls, plan: Plan, language: str, phase_count: int) -> str:
        """Localized template fallback when LLM is unavailable."""
        templates = cls._SUMMARY_TEMPLATES.get(language, cls._SUMMARY_TEMPLATES["en"])
        key = "fallback" if plan.is_fallback else "standard"
        return templates[key].format(phase_count=phase_count)
