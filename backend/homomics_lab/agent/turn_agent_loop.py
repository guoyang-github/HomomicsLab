"""AgentLoopHandler — LLM-driven MCP tool-calling loop for a turn.

Extracted from ``turn_runner.TurnRunner`` as a pure code move (no logic
changes). The handler holds a back-reference to the runner for per-turn
mutable state (``_session_id``, ``_project_id``, ``_turn_request_id``,
``_event_callback``) and lazily-initialized services (``_llm_client``).
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any, List, Optional

from homomics_lab.agent.agent_loop import AgentLoop, TurnBudget
from homomics_lab.models.common import (
    ChatMessage,
    HITLCheckpoint,
    HITLTrigger,
    MessageType,
    Option,
)

if TYPE_CHECKING:
    from homomics_lab.agent.intent_analyzer import UserIntent
    from homomics_lab.agent.turn_runner import TurnResult, TurnRunner
    from homomics_lab.context.working_memory import WorkingMemory

logger = logging.getLogger(__name__)


class AgentLoopHandler:
    """Run the LLM-driven tool-calling loop and its approval/follow-up flow."""

    def __init__(self, runner: "TurnRunner"):
        self._runner = runner

    async def handle(
        self,
        user_message: str,
        working_memory: "WorkingMemory",
        allowed_tools: Optional[List[str]] = None,
        intent: Optional["UserIntent"] = None,
    ) -> "TurnResult":
        """Run the LLM-driven tool-calling loop for MCP tool intents."""
        from homomics_lab.agent.turn_runner import ExecutionMode, TurnResult

        runner = self._runner
        if runner._llm_client is None or runner._tool_registry is None:
            raise RuntimeError("AgentLoop requires both llm_client and tool_registry")

        history = runner._working_memory_to_history(working_memory)
        loop = AgentLoop(
            llm_client=runner._llm_client,
            tool_registry=runner._tool_registry,
            session_id=getattr(runner, "_session_id", None),
            project_id=getattr(runner, "_project_id", None),
            request_id=getattr(runner, "_turn_request_id", None),
            max_rounds=3,
            budget=TurnBudget(max_llm_calls=5, max_tool_calls=10),
            event_callback=getattr(runner, "_event_callback", None),
        )
        result = await loop.run(
            user_message=user_message,
            history=history,
            allowed_tools=allowed_tools,
        )

        if result.awaiting_approval and result.approval_request:
            tool_name = result.approval_request.get("tool_name", "")
            risk_level = result.approval_request.get("risk_level", "high")
            if runner._permission_registry.can_auto_approve_tool(
                role_id=None,
                domain=intent.domain if intent else None,
                tool_name=tool_name,
                risk_level=risk_level,
            ):
                return await runner.respond_to_tool_approval(
                    call_id=result.approval_request["call_id"],
                    approved=True,
                    working_memory=working_memory,
                    project_id=getattr(runner, "_project_id", "default"),
                )
            return await self.create_tool_approval_hitl(
                result, working_memory, user_message
            )

        response_text = result.response_text
        if not response_text or not str(response_text).strip():
            response_text = "工具调用已完成，但没有生成可读的回复。"

        agent_msg = ChatMessage(
            id=f"msg_{len(working_memory.messages)}",
            type=MessageType.TEXT,
            content=response_text,
            sender="agent",
        )
        working_memory.add_message(agent_msg)

        # Preserve a structured preview if any tool calls were made.
        if result.tool_calls:
            preview_msg = ChatMessage(
                id=f"msg_{len(working_memory.messages)}",
                type=MessageType.RESULT_PREVIEW,
                content={
                    "tool_calls": [
                        {
                            "tool_name": tc.tool_name,
                            "inputs": tc.inputs,
                            "success": tc.success,
                            "output_summary": tc.output_summary,
                        }
                        for tc in result.tool_calls
                    ],
                    "response_text": response_text,
                },
                sender="agent",
            )
            working_memory.add_message(preview_msg)

        # Suggest follow-up questions for direct text/tool answers.
        suggestions = await self.generate_followup_suggestions(
            user_message=user_message,
            response_text=response_text,
        )
        if suggestions:
            follow_up_msg = ChatMessage(
                id=f"msg_{len(working_memory.messages)}",
                type=MessageType.FOLLOW_UP,
                content={"suggestions": suggestions},
                sender="agent",
            )
            working_memory.add_message(follow_up_msg)

        return TurnResult(
            mode=ExecutionMode.DIRECT_RESPONSE,
            response_text=response_text,
            agent_message=agent_msg,
        )

    async def generate_followup_suggestions(
        self,
        user_message: str,
        response_text: str,
        max_suggestions: int = 3,
    ) -> List[str]:
        """Generate concise follow-up question suggestions using the LLM."""
        runner = self._runner
        if (
            runner._llm_client is None
            or not getattr(runner._llm_client, "is_configured", lambda: False)()
        ):
            return []

        prompt = (
            f"User question: {user_message}\n"
            f"Agent answer: {response_text}\n\n"
            f"Generate up to {max_suggestions} concise follow-up questions the user might ask next. "
            "Respond with a JSON array of strings only, no markdown."
        )
        try:
            raw = await runner._llm_client.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that suggests follow-up questions.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=200,
                response_format={"type": "json_object"},
            )
            parsed = json.loads(raw)
            suggestions = (
                parsed.get("suggestions", parsed)
                if isinstance(parsed, dict)
                else parsed
            )
            if isinstance(suggestions, list):
                return [str(s) for s in suggestions[:max_suggestions]]
        except Exception:
            logger.debug("Follow-up suggestion generation failed", exc_info=True)
        return []

    async def create_tool_approval_hitl(
        self,
        loop_result: Any,
        working_memory: "WorkingMemory",
        user_message: str,
    ) -> "TurnResult":
        """Create a HITL request when the agent loop pauses for tool approval."""
        from homomics_lab.agent.turn_runner import ExecutionMode, TurnResult

        req = loop_result.approval_request
        call_id = req["call_id"]
        tool_name = req["tool_name"]
        arguments = req["arguments"]

        checkpoint = HITLCheckpoint(
            id=f"tool_approval_{call_id}",
            trigger_reason=HITLTrigger.HIGH_RISK,
            context_summary=(
                f"Agent wants to run high-risk tool `{tool_name}` "
                f"with arguments {arguments}. Please approve or decline."
            ),
            options=[
                Option(
                    id="approve", label="授权执行", description="允许执行该高风险工具"
                ),
                Option(id="decline", label="拒绝", description="跳过该工具调用"),
            ],
            metadata={
                "tool_approval_call_id": call_id,
                "tool_name": tool_name,
                "arguments": arguments,
            },
        )

        hitl_msg = ChatMessage(
            id=f"msg_{len(working_memory.messages)}",
            type=MessageType.HITL_REQUEST,
            content={
                "checkpoint": checkpoint.model_dump(),
                "task_id": call_id,
            },
            sender="agent",
        )
        working_memory.add_message(hitl_msg)

        return TurnResult(
            mode=ExecutionMode.AWAITING_HITL,
            response_text=loop_result.response_text,
            agent_message=hitl_msg,
            hitl_task_id=call_id,
            hitl_checkpoint=checkpoint.model_dump(),
        )
