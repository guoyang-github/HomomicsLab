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
class StructuredIntent:
    """Best-practice v2 intent schema produced by the LLM-first classifier.

    This decomposition separates *what the user wants to do* from *how the
    system should respond*, which is the key difference from the legacy
    ``analysis_type`` + ``complexity`` pair.

    Attributes:
        intent_type: High-level semantic category of the request.
            - ``qa``: asking for a definition or explanation.
            - ``information_request``: asking what the system/an analysis can do
              ("有哪些分析内容", "包括哪些步骤").
            - ``general_help``: asking for code, scripts, examples, or general
              programming/bioinformatics help.
            - ``greeting``: greeting/self-introduction.
            - ``file_conversion``: format conversion.
            - ``analysis``: domain-specific bioinformatics analysis.
            - ``tool_call``: explicit request for an MCP/external tool.
            - ``clarification``: the system needs more information.
            - ``general``: catch-all / small talk.
        interaction_mode: How the system should handle the turn.
            - ``answer``: respond directly without skill execution.
            - ``execute``: run skills / workflows.
            - ``explore``: browse/retrieve information (PubMed, GEO, UniProt).
            - ``troubleshoot``: diagnose a failure or unexpected result.
            - ``modify``: change an existing plan or result.
            - ``approve``: user is confirming/rejecting a plan.
            - ``clarify``: ask the user a follow-up question.
        domain: Optional domain tag (e.g. ``single-cell-transcriptomics``, ``spatial-transcriptomics``).
        target: Concrete skill id, phase id, or tool name when known.
        scope: ``single_step`` | ``partial`` | ``full``.
        entities: Key-value entities extracted from the message.
        confidence: Classifier confidence in [0, 1].
        reason: Short provenance string for observability.
    """

    intent_type: str = "general"
    interaction_mode: str = "answer"
    domain: Optional[str] = None
    target: Optional[str] = None
    scope: str = "single_step"
    entities: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    reason: str = ""

    def to_legacy_analysis_type(self) -> str:
        """Return a backward-compatible ``analysis_type`` value."""
        if self.intent_type in ("qa", "information_request"):
            return "qa"
        if self.intent_type == "general_help":
            return "general_help"
        if self.intent_type == "greeting":
            return "greeting"
        if self.intent_type == "clarification":
            return "clarification"
        if self.intent_type == "file_conversion":
            return "file_conversion"
        if self.target:
            return self.target
        if self.domain:
            return f"{self.domain}_analysis"
        return "general"

    def to_legacy_complexity(self) -> str:
        """Return a backward-compatible ``complexity`` value."""
        if self.intent_type in ("qa", "information_request", "general_help", "greeting", "clarification"):
            return "direct_response"
        if self.scope == "single_step":
            return "single_step"
        if self.scope in ("partial", "full"):
            return "complex"
        return "single_step"


@dataclass
class IntentMatch:
    """A single intent match with provenance."""

    analysis_type: str
    confidence: float
    source: str  # "keyword" | "embedding" | "llm" | "fallback"
    reason: str = ""
    weight: float = 1.0
    # v2 structured decomposition, when available.
    structured: Optional[StructuredIntent] = None


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

    # New v2 schema reference, when the intent came from a structured classifier.
    structured_intent: Optional[StructuredIntent] = None

    def __post_init__(self):
        if self.structured_intent is not None:
            self._apply_structured_intent()
        if not self.interaction_mode:
            self.interaction_mode = self._derive_interaction_mode()
        if not self.scope:
            self.scope = self._derive_scope()
        if self.domain is None:
            self.domain = self._derive_domain()
        if self.target is None:
            self.target = self._derive_target()

    def _apply_structured_intent(self) -> None:
        """Populate legacy/structured fields from a StructuredIntent."""
        s = self.structured_intent
        if s is None:
            return
        # Do not overwrite explicitly provided values; otherwise mirror v2.
        if not self.analysis_type or self.analysis_type == "general":
            self.analysis_type = s.to_legacy_analysis_type()
        if not self.complexity or self.complexity == "single_step":
            self.complexity = s.to_legacy_complexity()
        if not self.interaction_mode:
            self.interaction_mode = s.interaction_mode
        if not self.scope:
            self.scope = s.scope
        if self.domain is None:
            self.domain = s.domain
        if self.target is None:
            self.target = s.target
        # Merge entities into metadata for downstream use. Some LLMs return
        # entities as a string or a list instead of the requested object; guard
        # against that instead of crashing intent analysis.
        if s.entities and isinstance(s.entities, dict):
            self.metadata = {**s.entities, **self.metadata}

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
        if self.complexity == "direct_response":
            return "single_step"
        if self.sub_intents:
            return "partial"
        if self.complexity == "complex":
            return "full"
        return "full"

    def _derive_domain(self) -> Optional[str]:
        if self.structured_intent and self.structured_intent.domain:
            return self.structured_intent.domain
        mapping = {
            "single_cell_analysis": "single-cell-transcriptomics",
            "spatial_analysis": "spatial-transcriptomics",
            "metagenomics_analysis": "metagenomics",
            "genomics_analysis": "genomics",
            "proteomics_analysis": "proteomics",
            "transcriptomics_analysis": "transcriptomics",
            "epigenomics_analysis": "epigenomics",
        }
        return mapping.get(self.analysis_type)

    def _derive_target(self) -> Optional[str]:
        if self.structured_intent and self.structured_intent.target:
            return self.structured_intent.target
        if self.analysis_type == "file_conversion":
            return "convert_file"
        if self.analysis_type in ("qa", "information_request"):
            return "answer_question"
        if self.analysis_type == "general_help":
            return "generate_code"
        if self.sub_intents:
            return self.sub_intents[0].analysis_type
        return None
