"""Read-only critic sub-agent for hallucination and safety review."""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from homomics_lab.agent.agent_loop import AgentLoop, AgentLoopResult
from homomics_lab.agent.subagents.filter import read_only_tools
from homomics_lab.agent.subagents.models import CriticReview, ReviewAction, SubAgentResult

logger = logging.getLogger(__name__)


class CriticAgent:
    """A read-only critic that reviews specialist output and proposed plans.

    It may only use low-risk, read-only tools; it can never execute code or
    modify files. Its goal is to catch hallucinations, unsupported assumptions,
    and missing validation before execution.
    """

    def __init__(
        self,
        llm_client: Any,
        tool_registry: Any,
        loop_factory: Any = None,
    ) -> None:
        self.llm_client = llm_client
        self.tool_registry = tool_registry
        self.loop_factory = loop_factory or AgentLoop

    def _system_prompt(self) -> str:
        return (
            "You are a meticulous, read-only scientific critic.\n"
            "Review the user request, the proposed analysis plan, and the specialist's review.\n"
            "Identify hallucinations, unsupported assumptions, missing validation, and safety concerns.\n"
            "Respond with a JSON object exactly in this shape:\n"
            '{"action": "approve|revise|reject|ask_user", "summary": "one-sentence verdict", '
            '"concerns": ["..."], "suggestions": ["..."]}\n'
            "Choose 'approve' only if the plan is sound and well-supported.\n"
            "Choose 'revise' if the plan can be fixed with concrete changes.\n"
            "Choose 'reject' if the plan is unsafe or fundamentally wrong.\n"
            "Choose 'ask_user' if you need clarifying information."
        )

    async def review(
        self,
        specialist_output: SubAgentResult,
        plan: Any,
        request: Optional[str] = None,
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> CriticReview:
        allowed_tools = read_only_tools(self.tool_registry)
        plan_text = self._plan_text(plan)
        user_message = (
            f"User request: {request or '(not provided)'}\n\n"
            f"Proposed plan:\n{plan_text}\n\n"
            f"Specialist review:\n{specialist_output.response_text}\n\n"
            "Please provide your critic review as the requested JSON object."
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
        return self._parse_review(result.response_text or "{}", specialist_output)

    def _plan_text(self, plan: Any) -> str:
        if plan is None:
            return "(no plan provided)"
        if hasattr(plan, "model_dump"):
            return json.dumps(plan.model_dump(), ensure_ascii=False, indent=2)
        if isinstance(plan, dict):
            return json.dumps(plan, ensure_ascii=False, indent=2)
        return str(plan)

    def _parse_review(self, text: str, specialist_output: SubAgentResult) -> CriticReview:
        json_text = self._extract_json(text)
        try:
            data = json.loads(json_text)
        except json.JSONDecodeError:
            logger.warning("Critic returned non-JSON response: %s", text[:200])
            return CriticReview(
                action="ask_user",
                summary="The critic could not produce a structured review.",
                concerns=["Critic response was not valid JSON."],
                specialist_output=specialist_output,
            )

        # If the JSON is empty or carries no review fields, treat it as unstructured.
        if not data or not any(k in data for k in ("action", "summary", "concerns", "suggestions")):
            return CriticReview(
                action="ask_user",
                summary="The critic produced an empty or unstructured review.",
                concerns=[text[:200] or "Unstructured critic response."],
                specialist_output=specialist_output,
            )

        action = self._normalize_action(data.get("action"))
        return CriticReview(
            action=action,
            summary=data.get("summary") or "No summary provided.",
            concerns=data.get("concerns") or [],
            suggestions=data.get("suggestions") or [],
            specialist_output=specialist_output,
            metadata={"raw": text},
        )

    def _extract_json(self, text: str) -> str:
        text = text.strip()
        if text.startswith("{"):
            return text
        match = re.search(r"\{.*\}", text, re.DOTALL)
        return match.group(0) if match else "{}"

    def _normalize_action(self, value: Any) -> ReviewAction:
        if not isinstance(value, str):
            return "ask_user"
        v = value.strip().lower()
        if v in ("approve", "revise", "reject", "ask_user"):
            return v
        return "ask_user"
