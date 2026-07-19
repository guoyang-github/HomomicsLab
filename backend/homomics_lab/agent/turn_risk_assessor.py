"""RiskAssessor — prompt building and score parsing for turn risk evaluation.

Extracted from ``turn_runner.TurnRunner`` as a pure code move (no logic
changes).
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from homomics_lab.agent.intent_analyzer import UserIntent
    from homomics_lab.agent.turn_runner import TurnRunner
    from homomics_lab.context.working_memory import WorkingMemory


class RiskAssessor:
    """Build risk-evaluation prompts and parse/heuristically derive risk scores."""

    def __init__(self, runner: "TurnRunner"):
        self._runner = runner

    @staticmethod
    def build_risk_prompt(
        intent: "UserIntent",
        user_message: str,
        working_memory: "WorkingMemory",
        project_id: Optional[str] = None,
    ) -> str:
        return (
            "Evaluate the risk that executing this user request will lead to "
            "data loss, destruction, or unintended modification of project state.\n\n"
            f"User message: {user_message}\n"
            f"Intent: {intent.intent_type} (mode={intent.interaction_mode}, scope={intent.scope})\n"
            f"Intent confidence: {intent.confidence:.2f}\n"
            f"Project ID: {project_id or 'unknown'}\n\n"
            'Respond with a JSON object: {"risk_score": 0.0} where the score is '
            "a float between 0.0 (no risk) and 1.0 (very high risk)."
        )

    @staticmethod
    def parse_risk_score(response: Any) -> float:
        """Parse a risk score from an LLM response."""
        text = ""
        if isinstance(response, str):
            text = response
        elif isinstance(response, dict):
            if "risk_score" in response:
                return float(response["risk_score"])
            text = str(response.get("content", response))
        else:
            text = str(response)

        # Try to extract JSON from the text.
        try:
            match = re.search(r"\{[^}]*\"risk_score\"[^}]*\}", text)
            if match:
                data = json.loads(match.group(0))
                return float(data["risk_score"])
        except Exception:
            pass

        # Fall back to a plain float in the response.
        try:
            return float(text.strip())
        except Exception:
            pass

        return 0.0

    @staticmethod
    def heuristic_risk_score(
        user_message: str,
        intent: "UserIntent",
        low_risk_keywords: set,
        high_risk_keywords: set,
    ) -> float:
        message_lower = user_message.lower()
        score = 0.0
        if any(kw in message_lower for kw in high_risk_keywords):
            score += 0.7
        if any(kw in message_lower for kw in low_risk_keywords):
            score -= 0.3
        if intent.interaction_mode == "answer" or intent.target == "convert_file":
            score -= 0.2
        return max(0.0, min(1.0, score))
