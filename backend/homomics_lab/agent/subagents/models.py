"""Models for specialist/critic sub-agent reviews."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

ReviewAction = Literal["approve", "revise", "reject", "ask_user"]


@dataclass
class SubAgentResult:
    """Output from a specialist sub-agent."""

    response_text: str
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    cost_usd: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CriticReview:
    """Structured critique produced by a read-only critic sub-agent."""

    action: ReviewAction
    summary: str
    concerns: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    specialist_output: Optional[SubAgentResult] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "summary": self.summary,
            "concerns": self.concerns,
            "suggestions": self.suggestions,
            "metadata": self.metadata,
        }
