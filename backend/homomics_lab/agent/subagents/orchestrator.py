"""Orchestrator that pairs a domain specialist with a read-only critic."""

from typing import Any, Dict, List, Optional

from homomics_lab.agent.subagents.critic import CriticAgent
from homomics_lab.agent.subagents.models import CriticReview
from homomics_lab.agent.subagents.specialist import SpecialistAgent


class SpecialistCriticOrchestrator:
    """Run a specialist review followed by a critic review for complex plans."""

    def __init__(
        self,
        llm_client: Any,
        tool_registry: Any,
        role: Any = None,
        domain: Optional[str] = None,
    ) -> None:
        self.specialist = SpecialistAgent(llm_client, tool_registry, role=role, domain=domain)
        self.critic = CriticAgent(llm_client, tool_registry)

    async def review(
        self,
        request: str,
        plan: Any,
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> CriticReview:
        specialist_output = await self.specialist.review_plan(request, plan, history)
        return await self.critic.review(
            specialist_output=specialist_output,
            plan=plan,
            request=request,
            history=history,
        )
