"""LLM fallback planner for unknown domains.

When no domain strategy matches the user's intent, this planner retrieves
relevant skills via semantic search and asks an LLM to assemble them into an
executable plan. The resulting plan is marked as a fallback so the execution
layer can add extra safeguards (e.g., HITL confirmation) before running it.
"""

import json
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ValidationError

from homomics_lab.agent.intent.models import intent_strategy_key
from homomics_lab.agent.intent_analyzer import UserIntent
from homomics_lab.agent.plan.estimator import default_tracker, estimate_phase
from homomics_lab.agent.plan.models import DataState, Phase, PlanResult
from homomics_lab.llm_client import LLMClient
from homomics_lab.skills.models import SkillDefinition
from homomics_lab.skills.registry import SkillRegistry


class FallbackPlanStep(BaseModel):
    """A single step in the LLM fallback plan output."""

    skill_id: str
    phase: str = "analysis"
    reason: str = ""
    parameters: Dict[str, Any] = {}
    estimated_duration_seconds: Optional[float] = None
    estimated_cost_usd: Optional[float] = None


class FallbackPlanOutput(BaseModel):
    """Structured JSON output expected from the fallback planner LLM."""

    steps: List[FallbackPlanStep]
    summary: str = ""


class LLMFallbackPlanner:
    """Generates executable plans for unknown intents using LLM reasoning.

    The planner never invents skill IDs: it only selects from the skills
    returned by ``SkillRegistry.semantic_search``. If the LLM is unavailable,
    it returns a graceful suggestion instead of crashing.
    """


    def __init__(
        self,
        skill_registry: SkillRegistry,
        llm_client: Optional[LLMClient] = None,
        top_k: int = 10,
        allow_code_fallback: bool = True,
        deterministic_fallback: bool = False,
        tracker: Optional[Any] = None,
    ):
        self.skill_registry = skill_registry
        self.llm_client = llm_client
        self.top_k = top_k
        self.allow_code_fallback = allow_code_fallback
        self.deterministic_fallback = deterministic_fallback
        self.tracker = tracker or default_tracker()

    async def generate_plan(
        self,
        intent: UserIntent,
        data_state: Optional[DataState] = None,
    ) -> PlanResult:
        """Generate an executable fallback plan for an unknown intent."""
        data_state = data_state or DataState()
        user_message = getattr(intent, "original_message", None) or intent_strategy_key(intent)

        # 1. Retrieve candidate skills.
        candidate_skills = self._retrieve_skills(intent)
        if not candidate_skills:
            return self._graceful_plan(
                intent,
                data_state,
                "No suitable skills are registered for this request. "
                "Please install or declare a domain that covers this analysis type.",
            )

        # 2. Ask the LLM to select and order skills.
        selected = await self._ask_llm_for_plan(
            user_message,
            intent,
            data_state,
            candidate_skills,
        )

        # 3. Build executable phases from validated skill selections.
        if (
            not selected
            and candidate_skills
            and self.deterministic_fallback
            and not self._is_code_or_data_request(intent)
        ):
            # No LLM or LLM refused: fall back to a deterministic plan built from
            # the top retrieved skills. This keeps generic bioinformatics requests
            # executable while preserving the special code/data suggestion path.
            selected = self._deterministic_skill_plan(candidate_skills, intent)

        phases: List[Phase] = []
        for item in selected:
            skill_id = item.get("skill_id")
            skill = self.skill_registry.get(skill_id)
            if skill is None:
                # LLM hallucinated a skill ID — skip it.
                continue

            is_code_act_skill = skill.id == "core_code_act"
            phase = Phase(
                phase_type=item.get("phase", skill.category or "analysis"),
                required=True,
                description=item.get("reason", f"Run {skill.name}"),
                selected_skill=skill,
                parameters=item.get("parameters", {}),
                readonly=is_code_act_skill,
                estimated_duration_seconds=item.get("estimated_duration_seconds"),
                estimated_cost_usd=item.get("estimated_cost_usd"),
                derivation="llm-fallback",
                risk_level="high",
            )
            estimate_phase(phase, self.tracker)
            phases.append(phase)

        if not phases:
            if (
                self.allow_code_fallback
                and self._is_code_or_data_request(intent)
                and self.skill_registry.get("core_code_act") is not None
            ):
                return self._graceful_plan(
                    intent,
                    data_state,
                    "This looks like a general coding or data-processing task. "
                    "I can write a script for you using core_code_act. "
                    "Please provide more details or confirm you'd like me to generate code.",
                )
            return self._graceful_plan(
                intent,
                data_state,
                "The available skills do not cover the requested analysis. "
                "Please install a domain or add skills for this workflow.",
            )

        # 4. Build the plan with fallback metadata.
        suggestion_text = self._format_suggestion(user_message, phases)
        return PlanResult(
            phases=phases,
            strategy_name="llm_fallback",
            data_state=data_state,
            gaps=[],
            reproducibility_context={
                "plan_engine_version": "0.4.1",
                "strategy": "llm_fallback",
                "intent": intent_strategy_key(intent),
                "data_state": data_state.to_context(),
                "candidate_skills": [s.id for s in candidate_skills],
                "llm_selected_skills": [p.selected_skill.id for p in phases if p.selected_skill],
            },
            is_fallback=True,
            suggestion_text=suggestion_text,
            derivation="llm-fallback",
            risk_level="high",
            approval_required=True,
        )

    def _is_code_or_data_request(self, intent: UserIntent) -> bool:
        """Return True if the intent indicates a general code/data task."""
        structured = getattr(intent, "structured_intent", None)
        if structured is not None:
            return structured.intent_type == "general_help"
        return False

    def _deterministic_skill_plan(
        self,
        candidate_skills: List[SkillDefinition],
        intent: UserIntent,
    ) -> List[Dict[str, Any]]:
        """Build a simple linear plan from retrieved skills when no LLM is available.

        The plan deduplicates by skill category and preserves the retrieval order.
        """
        seen_categories: set[str] = set()
        plan: List[Dict[str, Any]] = []
        for skill in candidate_skills:
            category = skill.category or "analysis"
            if category in seen_categories:
                continue
            seen_categories.add(category)
            plan.append(
                {
                    "skill_id": skill.id,
                    "phase": category,
                    "reason": f"Run {skill.name} for {intent_strategy_key(intent)}",
                    "parameters": {},
                }
            )
            if len(plan) >= 4:
                break
        return plan

    def _retrieve_skills(self, intent: UserIntent) -> List[SkillDefinition]:
        """Retrieve candidate skills via semantic search.

        Falls back to keyword search, then to all registered skills,
        and finally to the general code assistant for code/data tasks,
        so the LLM always has something to reason about.
        """
        query = intent.original_message or intent_strategy_key(intent)
        results = self.skill_registry.semantic_search(query, top_k=self.top_k)
        if not results:
            results = [(skill, 0.0) for skill in self.skill_registry.search(query)]
        if not results:
            results = [(skill, 0.0) for skill in self.skill_registry.list_all()]
        if not results and self.allow_code_fallback and self._is_code_or_data_request(intent):
            code_skill = self.skill_registry.get("core_code_act")
            if code_skill is not None:
                results = [(code_skill, 0.0)]
        return [skill for skill, _ in results[: self.top_k]]

    async def _ask_llm_for_plan(
        self,
        user_message: str,
        intent: UserIntent,
        data_state: DataState,
        candidate_skills: List[SkillDefinition],
    ) -> List[Dict[str, Any]]:
        """Ask the LLM to select and order skills from the candidate list."""
        if self.deterministic_fallback and self.llm_client is None:
            # Deterministic mode never needs the LLM; skip client construction
            # so tests and offline runs are not blocked by secret-store state.
            return []

        if self.llm_client is None:
            self.llm_client = LLMClient()

        if not self.llm_client.is_configured():
            return []

        skill_descriptions = [
            {
                "id": skill.id,
                "name": skill.name,
                "description": skill.description,
                "category": skill.category,
                "input_schema": skill.input_schema.model_dump() if skill.input_schema else {},
                "output_schema": skill.output_schema.model_dump() if skill.output_schema else {},
            }
            for skill in candidate_skills
        ]

        system_prompt = """You are a bioinformatics workflow planner. Your job is to build a short, executable analysis plan by selecting skills from the provided list.

Rules:
1. Only use skill IDs from the "available_skills" list. Do not invent new skills.
2. Order skills in a logical execution sequence.
3. For each selected skill, provide a brief reason and any required input parameters.
4. If no bioinformatics skill matches the request, but the request is a general coding or data-processing task (e.g., filtering CSVs, renaming files), you MAY select "core_code_act" and include a "generated_code" parameter with the code snippet.
5. If no skill matches the request at all, return an empty `steps` array.
6. Prefer fewer steps when possible; avoid redundant analysis.
7. Optionally provide per-step execution estimates (`estimated_duration_seconds` and `estimated_cost_usd`) when you can infer them.

Respond with a single JSON object in this exact format (no markdown fences):
{
  "steps": [
    {
      "skill_id": "registered_skill_id",
      "phase": "qc|normalization|analysis|visualization|utility|...",
      "reason": "why this skill is needed",
      "parameters": {"param_name": "value", "generated_code": "optional code snippet"},
      "estimated_duration_seconds": 120,
      "estimated_cost_usd": 0.01
    }
  ],
  "summary": "one-sentence description of the overall plan"
}"""

        user_prompt = f"""User request: {user_message}
Intent type: {intent.intent_type or intent_strategy_key(intent)}
Interaction mode: {intent.interaction_mode}
Scope: {intent.scope}
Data state: {data_state.to_context()}

Available skills:
{json.dumps(skill_descriptions, ensure_ascii=False, indent=2)}

Generate the JSON plan now."""

        try:
            raw = await self.llm_client.chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            parsed = FallbackPlanOutput.model_validate_json(raw)
            return [step.model_dump() for step in parsed.steps]
        except (json.JSONDecodeError, ValidationError):
            # Swallow parse/validation errors and fall back to empty selection.
            pass
        except Exception:
            # Swallow LLM errors and fall back to empty selection.
            pass

        return []

    def _graceful_plan(
        self,
        intent: UserIntent,
        data_state: DataState,
        message: str,
    ) -> PlanResult:
        """Return a non-executable fallback plan with a helpful message."""
        user_message = getattr(intent, "original_message", "") or ""
        if self.allow_code_fallback and self._is_code_or_data_request(user_message):
            message = (
                "I don't have a registered bioinformatics skill for this request, "
                "but it looks like a general coding/data task. "
                "You can either ask me to 'write a script' (direct response) "
                "or install a domain that covers this workflow."
            )
        return PlanResult(
            phases=[],
            strategy_name="llm_fallback",
            data_state=data_state,
            gaps=[],
            reproducibility_context={
                "plan_engine_version": "0.4.1",
                "strategy": "llm_fallback",
                "intent": intent_strategy_key(intent),
                "data_state": data_state.to_context(),
            },
            is_fallback=True,
            suggestion_text=message,
            derivation="llm-fallback",
            risk_level="high",
            approval_required=True,
        )

    @staticmethod
    def _format_suggestion(user_message: str, phases: List[Phase]) -> str:
        """Format the fallback plan as a human-readable suggestion."""
        lines = [f"I don't have a predefined workflow for '{user_message}', but I can propose a plan using available skills:"]
        for i, phase in enumerate(phases, 1):
            skill_name = phase.selected_skill.name if phase.selected_skill else "unknown"
            lines.append(f"{i}. {skill_name} — {phase.description}")
        lines.append("\nThis plan was generated by an LLM fallback. Please review before executing.")
        return "\n".join(lines)
