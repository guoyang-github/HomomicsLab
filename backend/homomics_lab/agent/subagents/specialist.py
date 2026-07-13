"""Domain specialist sub-agent."""

import json
import logging
from typing import Any, Dict, List, Optional

from homomics_lab.agent.agent_loop import AgentLoop, AgentLoopResult
from homomics_lab.agent.subagents.filter import filter_tools_by_role
from homomics_lab.agent.subagents.models import SubAgentResult

logger = logging.getLogger(__name__)


class SpecialistAgent:
    """A domain-focused sub-agent that reviews/refines a plan before execution.

    It is constrained to the skills and tools allowed by its domain role.
    """

    def __init__(
        self,
        llm_client: Any,
        tool_registry: Any,
        role: Any = None,
        domain: Optional[str] = None,
        loop_factory: Any = None,
    ) -> None:
        self.llm_client = llm_client
        self.tool_registry = tool_registry
        self.role = role
        self.domain = domain
        self.loop_factory = loop_factory or AgentLoop

    def _system_prompt(self) -> str:
        role_name = getattr(self.role, "name", "Domain specialist") if self.role else "Domain specialist"
        domain = self.domain or "the relevant scientific domain"
        return (
            f"You are {role_name} in {domain}. Your job is to act as a planning specialist.\n"
            "Given a user request and a proposed analysis plan, do one of the following:\n"
            "  - Confirm the plan is sound and note any critical parameters.\n"
            "  - Suggest concrete refinements (better tools, parameter choices, validation steps).\n"
            "You may use read-only research tools to check facts, but you cannot execute code or write files.\n"
            "Respond in concise, actionable bullets."
        )

    async def review_plan(
        self,
        request: str,
        plan: Any,
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> SubAgentResult:
        allowed_tools = filter_tools_by_role(self.tool_registry, self.role, read_only=False)
        plan_text = self._plan_text(plan)
        user_message = (
            f"User request: {request}\n\n"
            f"Proposed plan:\n{plan_text}\n\n"
            "Please review the plan as a domain specialist and suggest any refinements."
        )
        loop = self.loop_factory(
            llm_client=self.llm_client,
            tool_registry=self.tool_registry,
            max_rounds=1,
            system_prompt=self._system_prompt(),
        )
        result: AgentLoopResult = await loop.run(
            user_message=user_message,
            history=history or [],
            allowed_tools=allowed_tools,
        )
        return SubAgentResult(
            response_text=result.response_text or "No specialist review produced.",
            tool_calls=[],
            cost_usd=getattr(result, "cost_usd", None),
            metadata={"role": getattr(self.role, "role_id", None) if self.role else None},
        )

    def _plan_text(self, plan: Any) -> str:
        if plan is None:
            return "(no plan provided)"
        if hasattr(plan, "model_dump"):
            return json.dumps(plan.model_dump(), ensure_ascii=False, indent=2)
        if isinstance(plan, dict):
            return json.dumps(plan, ensure_ascii=False, indent=2)
        return str(plan)
