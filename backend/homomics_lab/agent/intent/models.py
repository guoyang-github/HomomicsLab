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
    """User-facing intent object (backward compatible with v1).

    The structured fields ``interaction_mode``, ``domain``, ``target`` and
    ``scope`` provide a clearer separation of concerns than the legacy
    ``analysis_type`` + ``complexity`` pair. When they are not explicitly
    provided they are derived from the legacy fields so existing call sites
    keep working.
    """

    analysis_type: str
    complexity: str  # direct_response | single_step | complex
    confidence: float = 1.0
    original_message: str = ""
    data_scale: Optional[str] = None
    urgency: str = "normal"
    domain_knowledge: List[str] = field(default_factory=list)
    sub_intents: List["UserIntent"] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Structured intent decomposition (best-practice v2).
    interaction_mode: str = ""  # answer | execute | explore | troubleshoot | modify | approve | clarify
    domain: Optional[str] = None
    target: Optional[str] = None
    scope: str = ""  # full | partial | single_step

    def __post_init__(self):
        if not self.interaction_mode:
            self.interaction_mode = self._derive_interaction_mode()
        if not self.scope:
            self.scope = self._derive_scope()
        if self.domain is None:
            self.domain = self._derive_domain()
        if self.target is None:
            self.target = self._derive_target()

    def _derive_interaction_mode(self) -> str:
        if self.analysis_type == "clarification":
            return "clarify"
        if self.metadata.get("tool_name"):
            return "execute"
        if self.complexity == "direct_response":
            return "answer"
        if self.complexity == "single_step":
            return "execute"
        if self.sub_intents:
            return "execute"
        return "execute"

    def _derive_scope(self) -> str:
        if self.complexity == "single_step":
            return "single_step"
        if self.sub_intents:
            return "partial"
        if self.complexity == "complex":
            return "full"
        if self.complexity == "direct_response":
            return "single_step"
        return "full"

    def _derive_domain(self) -> Optional[str]:
        mapping = {
            "single_cell_analysis": "single_cell",
            "spatial_analysis": "spatial",
            "metagenomics_analysis": "metagenomics",
            "genomics_analysis": "genomics",
            "proteomics_analysis": "proteomics",
            "transcriptomics_analysis": "transcriptomics",
            "epigenomics_analysis": "epigenomics",
        }
        return mapping.get(self.analysis_type)

    def _derive_target(self) -> Optional[str]:
        if self.analysis_type == "file_conversion":
            return "convert_file"
        if self.analysis_type == "qa":
            return "answer_question"
        if self.analysis_type == "general_help":
            return "generate_code"
        if self.sub_intents:
            return self.sub_intents[0].analysis_type
        return None
