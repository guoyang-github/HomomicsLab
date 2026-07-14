"""ClarificationHandler — turns clarification intents and debate responses into TurnResults.

Extracted from ``turn_runner.TurnRunner`` as a pure code move (no logic
changes).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict

from homomics_lab.agent.intent.models import IntentMatch
from homomics_lab.models.common import ChatMessage, MessageType

if TYPE_CHECKING:
    from homomics_lab.agent.intent_analyzer import UserIntent
    from homomics_lab.agent.turn_runner import TurnResult, TurnRunner
    from homomics_lab.context.working_memory import WorkingMemory


class ClarificationHandler:
    """Build clarification questions and resolve debate choices into intents."""

    def __init__(self, runner: "TurnRunner"):
        self._runner = runner

    def handle_clarification(
        self,
        intent: "UserIntent",
        working_memory: "WorkingMemory",
    ) -> "TurnResult":
        """Return a clarification question or debate request to the user."""
        from homomics_lab.agent.turn_runner import ExecutionMode, TurnResult

        debate_data = intent.metadata.get("debate")
        if debate_data and debate_data.get("options"):
            agent_msg = ChatMessage(
                id=f"msg_{len(working_memory.messages)}",
                type=MessageType.DEBATE_REQUEST,
                content={
                    "debate_id": f"debate_{intent.original_message or 'clarify'}",
                    "topic": debate_data.get("topic", "请选择最符合您需求的选项"),
                    "options": debate_data.get("options", []),
                    "recommendation": debate_data.get("recommendation"),
                    "round_summaries": debate_data.get("round_summaries", []),
                },
                sender="agent",
            )
            working_memory.add_message(agent_msg)
            return TurnResult(
                mode=ExecutionMode.AWAITING_DEBATE,
                response_text=agent_msg.content["topic"],
                agent_message=agent_msg,
            )

        question = (
            intent.metadata.get("clarification_question")
            or "我不太确定您的需求，请再具体描述一下。"
        )

        agent_msg = ChatMessage(
            id=f"msg_{len(working_memory.messages)}",
            type=MessageType.TEXT,
            content=question,
            sender="agent",
        )
        working_memory.add_message(agent_msg)

        return TurnResult(
            mode=ExecutionMode.DIRECT_RESPONSE,
            response_text=question,
            agent_message=agent_msg,
        )

    def build_debate_resolved_intent(
        self,
        debate_response: Dict[str, Any],
        user_message: str,
    ) -> "UserIntent":
        """Convert a user's debate choice into a concrete intent."""
        choice_id = debate_response.get("choice_id", "")
        return self._runner.intent_analyzer._to_user_intent(
            IntentMatch(
                analysis_type=choice_id,
                confidence=1.0,
                source="debate",
                reason="user selected debate option",
            ),
            user_message,
        )
