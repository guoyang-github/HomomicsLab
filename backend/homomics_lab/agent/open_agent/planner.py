"""Open Agent Planner entry point.

Assembles capability retrieval, reasoning, tool/skill selection, and plan
validation into a single planner that returns a standard PlanResult.
"""

from typing import Any, Dict, List, Optional

from homomics_lab.agent.intent import UserIntent
from homomics_lab.agent.intent.models import intent_strategy_key
from homomics_lab.agent.open_agent.capability_retriever import CapabilityRetriever
from homomics_lab.agent.open_agent.code_generation import CodeActPlanner
from homomics_lab.agent.open_agent.models import (
    OpenAgentPhase,
    OpenAgentPlan,
    OpenAgentStepType,
)
from homomics_lab.agent.open_agent.reasoning import ReasoningEngine
from homomics_lab.agent.open_agent.skill_selection import SkillSelector
from homomics_lab.agent.open_agent.tool_selection import ToolSelector
from homomics_lab.agent.plan.models import DataState, Phase, PlanResult
from homomics_lab.agent.plan.validator import PlanValidator
from homomics_lab.llm_client import LLMClient
from homomics_lab.skills.registry import SkillRegistry, get_default_registry
from homomics_lab.tools.registry import ToolRegistry, get_default_tool_registry


class OpenAgentPlanner:
    """Plan open-ended, cross-domain, exploratory, and diagnostic tasks."""

    DERIVATION = "open-agent"
    DEFAULT_RISK_LEVEL = "medium"

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        skill_registry: Optional[SkillRegistry] = None,
        tool_registry: Optional[ToolRegistry] = None,
        capability_index: Optional[Any] = None,
        retriever: Optional[CapabilityRetriever] = None,
        reasoning_engine: Optional[ReasoningEngine] = None,
        tool_selector: Optional[ToolSelector] = None,
        skill_selector: Optional[SkillSelector] = None,
        plan_validator: Optional[PlanValidator] = None,
        code_act_planner: Optional[CodeActPlanner] = None,
        top_k: int = 10,
    ):
        self.llm_client = llm_client
        self.skill_registry = skill_registry or get_default_registry()
        self.tool_registry = tool_registry or get_default_tool_registry()
        self.retriever = retriever or CapabilityRetriever(
            skill_registry=self.skill_registry,
            tool_registry=self.tool_registry,
            capability_index=capability_index,
            top_k=top_k,
        )
        self.reasoning_engine = reasoning_engine or ReasoningEngine(llm_client=llm_client)
        self.tool_selector = tool_selector or ToolSelector(tool_registry=self.tool_registry)
        self.skill_selector = skill_selector or SkillSelector(skill_registry=self.skill_registry)
        self.plan_validator = plan_validator or PlanValidator(skill_registry=self.skill_registry)
        self.code_act_planner = code_act_planner or CodeActPlanner(
            llm_client=llm_client,
            skill_registry=self.skill_registry,
            tool_registry=self.tool_registry,
        )

    async def plan(
        self,
        intent: UserIntent,
        data_state: Optional[DataState] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[PlanResult]:
        """Build an open agent plan if the intent is suitable.

        Returns:
            A PlanResult for open agent execution, or ``None`` if the request
            should be handled by another planner.
        """
        if not self._should_activate(intent, data_state):
            return None

        capabilities = await self.retriever.retrieve(intent, data_state, context)
        if not capabilities:
            return self._graceful_suggestion(
                intent,
                "未找到可用于该请求的 skill/tool。请安装相关 domain 或提供更具体的需求。",
            )

        open_plan = await self.reasoning_engine.plan_steps(intent, capabilities, data_state)

        # Sanitize intents: drop any tool/skill not in the registry.
        open_plan = self._sanitize_plan(open_plan)

        plan_result = self._to_plan_result(open_plan, intent, capabilities, data_state)

        # Validate for observability, but do not let the domain-oriented
        # validator override the open-agent planner's own risk assessment.
        # Open-agent phases are intentionally abstract (explore, reason, etc.)
        # and do not always bind a selected_skill.
        validation = self.plan_validator.validate(plan_result)

        plan_result.reproducibility_context["open_agent"] = {
            "capabilities": [c.id for c in capabilities],
            "capability_types": [c.type.value for c in capabilities],
            "reasoning_trace": [step.model_dump() for step in open_plan.reasoning_trace],
            "validation": {
                "valid": validation.valid,
                "errors": [
                    {"severity": e.severity, "phase": e.phase, "skill_id": e.skill_id, "message": e.message}
                    for e in validation.errors
                ],
                "warnings": [
                    {"severity": w.severity, "phase": w.phase, "skill_id": w.skill_id, "message": w.message}
                    for w in validation.warnings
                ],
            },
        }

        return plan_result

    def _should_activate(self, intent: UserIntent, data_state: Optional[DataState]) -> bool:
        """Return True when the request should be handled by the open agent.

        Trigger signals:
          - explicit explore/diagnose/compare/open-ended analysis types
          - interaction_mode == "explore"
          - no domain and no known standalone skill match
          - cross-domain diagnostic requests
        """
        if intent.interaction_mode == "explore":
            return True

        open_types = {
            "explore",
            "diagnose",
            "compare",
            "open_ended",
            "cross_domain_analysis",
            "general_scientific",
        }
        if intent.intent_type in open_types:
            return True

        # Diagnostic or comparative language in the original message.
        message = (intent.original_message or "").lower()
        diagnostic_keywords = [
            "为什么",
            "怎么回事",
            "诊断",
            "比较",
            "compare",
            "difference between",
            "why is",
            "diagnose",
        ]
        if any(kw in message for kw in diagnostic_keywords):
            return True

        # No domain signal and no known domain strategy: let open agent try.
        if intent.domain is None and intent.intent_type in {"general", "analysis", "unknown"}:
            return True

        return False

    def _sanitize_plan(self, plan: OpenAgentPlan) -> OpenAgentPlan:
        """Remove any tool/skill intents that are not registered.

        The LLM is instructed to only use capabilities from the provided list,
        but it may still hallucinate names or reuse capabilities that were not
        actually retrieved. This method drops anything not present in the
        registries as a safety filter.
        """
        for phase in plan.phases:
            phase.tool_intents = self.tool_selector.validate_intents(phase.tool_intents)
            phase.skill_intents = self.skill_selector.validate_intents(phase.skill_intents)
        return plan

    def _to_plan_result(
        self,
        open_plan: OpenAgentPlan,
        intent: UserIntent,
        capabilities: List[Any],
        data_state: Optional[DataState],
    ) -> PlanResult:
        """Convert an OpenAgentPlan to the canonical PlanResult."""
        phases: List[Phase] = []
        for op in open_plan.phases:
            phase = self._open_agent_phase_to_phase(op)
            phases.append(phase)

        risk_level = open_plan.risk_level or self.DEFAULT_RISK_LEVEL
        # Open-agent plans are less predictable than domain strategies:
        # require approval unless the planner explicitly marked the risk as low.
        approval_required = open_plan.needs_hitl or risk_level != "low"

        return PlanResult(
            phases=phases,
            strategy_name="open-agent",
            data_state=data_state or DataState(),
            derivation=self.DERIVATION,
            risk_level=risk_level,
            approval_required=approval_required,
            is_fallback=False,
            suggestion_text=open_plan.final_summary,
            reproducibility_context={
                "plan_engine_version": "0.5.0",
                "strategy": "open-agent",
                "intent": intent_strategy_key(intent),
                "source_capabilities": [c.id for c in capabilities],
                "open_agent_plan": open_plan.model_dump(),
            },
        )

    def _open_agent_phase_to_phase(self, op: OpenAgentPhase) -> Phase:
        """Map an OpenAgentPhase to the canonical Plan Phase model."""
        # For execute_skill phases, bind the first selected skill.
        selected_skill = None
        if op.step_type == OpenAgentStepType.EXECUTE_SKILL and op.skill_intents:
            skill_id = op.skill_intents[0].skill_id
            selected_skill = self.skill_registry.get(skill_id)

        parameters: Dict[str, Any] = {
            "open_agent_step_type": op.step_type.value,
            "tool_intents": [ti.model_dump() for ti in op.tool_intents],
            "skill_intents": [si.model_dump() for si in op.skill_intents],
            "code_task": op.code_task,
            "code_language": op.code_language,
            "success_criteria": op.success_criteria,
        }

        return Phase(
            phase_type=op.step_type.value,
            description=op.description,
            required=op.required,
            selected_skill=selected_skill,
            parameters=parameters,
            estimated_duration_seconds=op.estimated_duration_seconds,
            estimated_cost_usd=op.estimated_cost_usd,
            derivation=self.DERIVATION,
            risk_level="medium",
        )

    def _graceful_suggestion(
        self,
        intent: UserIntent,
        message: str,
    ) -> PlanResult:
        """Return a non-executable suggestion plan."""
        return PlanResult(
            phases=[
                Phase(
                    phase_type="suggestion",
                    description=message,
                    required=False,
                )
            ],
            strategy_name="open-agent-suggestion",
            data_state=DataState(),
            derivation=self.DERIVATION,
            risk_level="low",
            approval_required=False,
            is_fallback=True,
            suggestion_text=message,
            reproducibility_context={
                "intent": intent_strategy_key(intent),
                "original_message": intent.original_message,
            },
        )
