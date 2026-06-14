"""Data models for the intent recognition subsystem."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class IntentDefinition:
    """Declarative description of an intent that the system can recognize."""

    analysis_type: str
    keywords: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)
    complexity_indicators: List[str] = field(default_factory=list)
    data_scale_patterns: List[str] = field(default_factory=list)
    domain: Optional[str] = None


@dataclass
class IntentMatch:
    """A single intent match with provenance."""

    analysis_type: str
    confidence: float
    source: str  # "keyword" | "embedding" | "llm" | "fallback"
    reason: str = ""
    weight: float = 1.0


@dataclass
class IntentClassificationResult:
    """Combined output of the cascade classifiers."""

    primary: IntentMatch
    alternatives: List[IntentMatch] = field(default_factory=list)
    sub_intents: List[IntentMatch] = field(default_factory=list)
    needs_clarification: bool = False
    clarification_question: Optional[str] = None


@dataclass
class UserIntent:
    """User-facing intent object (backward compatible with v1)."""

    analysis_type: str
    complexity: str  # direct_response | single_step | complex
    confidence: float = 1.0
    original_message: str = ""
    data_scale: Optional[str] = None
    urgency: str = "normal"
    domain_knowledge: List[str] = field(default_factory=list)
    sub_intents: List["UserIntent"] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
