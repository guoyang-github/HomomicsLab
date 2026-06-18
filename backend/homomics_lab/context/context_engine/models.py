"""Data models for the ContextEngine."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class ContextSource(str, Enum):
    """Source layer of a context part."""

    SYSTEM = "system"
    PROJECT_STATE = "project_state"
    CBKB = "cbkb"
    SEMANTIC_MEMORY = "semantic_memory"
    EPISODIC_SUMMARY = "episodic_summary"
    CHAT = "chat"


class CompressionLevel(str, Enum):
    """How aggressively a context part was compressed."""

    NONE = "none"
    TRUNCATED = "truncated"
    STRUCTURED = "structured"
    SUMMARIZED = "summarized"
    DROPPED = "dropped"


@dataclass
class ContextPart:
    """A single piece of context that can be ranked, compressed, and assembled."""

    content: str
    source: ContextSource
    priority: int = 5  # 1-10; higher is more important
    tokens: int = 0
    compression_level: CompressionLevel = CompressionLevel.NONE
    is_pinned: bool = False
    is_critical: bool = False
    is_upstream_result: bool = False
    agent_importance: float = 0.5
    hours_since_created: float = 0.0
    created_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()


@dataclass
class ContextBundle:
    """Final assembled context ready to be sent to an LLM."""

    messages: List[Dict[str, str]]
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def system_content(self) -> str:
        """Convenience accessor for the assembled system-level context."""
        parts = []
        for msg in self.messages:
            if msg.get("role") in ("system", "developer"):
                parts.append(msg.get("content", ""))
        return "\n\n".join(parts)

    def to_prompt(self, user_message: str) -> List[Dict[str, str]]:
        """Append the current user message to the bundled messages."""
        return self.messages + [{"role": "user", "content": user_message}]
