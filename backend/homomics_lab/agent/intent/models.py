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
    ``scope`` are now the source of truth.  The legacy ``analysis_type`` and
    ``complexity`` fields are kept for compatibility but are always derived
    from the v2 fields after normalization.  Call sites that still construct
    UserIntent with only ``analysis_type``/``complexity`` will continue to
    work because the v2 fields are back-filled from the legacy values.
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
        # Normalize sub-intents first so parent derivation can see them.
        for sub in self.sub_intents:
            sub._normalize()
        if self.structured_intent is not None:
            self._apply_structured_intent()
        self._normalize()

    def _normalize(self) -> None:
        """Normalize intent fields with v2 fields as the single source of truth.

        ``interaction_mode``, ``scope``, ``domain`` and ``target`` are the
        canonical representation.  ``analysis_type`` and ``complexity`` are
        derived read-only projections kept for transitional call sites and will
        be removed in a follow-up cleanup.

        Back-fill order:
          1. v2 fields already provided explicitly or via ``structured_intent``.
          2. Legacy fields when v2 fields are still missing (transitional).
          3. Default derivations.
        """
        # 1. Back-fill missing v2 fields from legacy values (transitional).
        if not self.interaction_mode:
            self.interaction_mode = self._derive_interaction_mode()
        if not self.scope:
            self.scope = self._derive_scope()
        if self.domain is None:
            self.domain = self._derive_domain()
        if self.target is None:
            self.target = self._derive_target()

        # 2. Enforce legacy projections consistent with v2 truth.
        self.complexity = self._derive_complexity()
        self.analysis_type = self._derive_analysis_type()

    def _apply_structured_intent(self) -> None:
        """Populate v2 fields from a StructuredIntent.

        The StructuredIntent is the source of truth for the fields it
        explicitly provides.  Legacy ``analysis_type``/``complexity`` are
        derived from the v2 fields in :meth:`_normalize`, but when the
        structured intent is concrete we let it update the legacy projection
        directly so the canonical v2 decision is reflected downstream.
        """
        s = self.structured_intent
        if s is None:
            return
        if s.interaction_mode:
            self.interaction_mode = s.interaction_mode
        if s.scope:
            self.scope = s.scope
        if s.domain is not None:
            self.domain = s.domain
        if s.target is not None:
            self.target = s.target
        if s.intent_type:
            self.metadata["intent_type"] = s.intent_type
        if s.reason:
            self.metadata.setdefault("reason", s.reason)

        # When the structured intent is concrete, mirror its semantic type to
        # the legacy projection so existing routers/plans keep working while
        # the v2 representation becomes the single source of truth.
        structured_analysis = self._intent_type_to_analysis_type(s.intent_type, s.target)
        is_structured_concrete = (
            s.target is not None
            or s.intent_type
            in {
                "qa",
                "information_request",
                "general_help",
                "greeting",
                "clarification",
                "file_conversion",
                "tool_call",
            }
        )
        if is_structured_concrete or not self.analysis_type or self.analysis_type in {"", "general", "unknown", "builtin_analysis"}:
            if structured_analysis:
                self.analysis_type = structured_analysis

        # Merge entities into metadata for downstream use. Some LLMs return
        # entities as a string or a list instead of the requested object; guard
        # against that instead of crashing intent analysis.
        if s.entities and isinstance(s.entities, dict):
            self.metadata = {**s.entities, **self.metadata}

    @staticmethod
    def _intent_type_to_analysis_type(intent_type: str, target: Optional[str]) -> Optional[str]:
        """Map a canonical v2 intent_type to the legacy analysis_type projection."""
        mapping = {
            "qa": "qa",
            "information_request": "information_request",
            "general_help": "general_help",
            "greeting": "greeting",
            "clarification": "clarification",
            "file_conversion": "file_conversion",
            "tool_call": target or "tool_call",
        }
        return mapping.get(intent_type)

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

    def _derive_complexity(self) -> str:
        """Derive legacy complexity from v2 fields."""
        if self.interaction_mode in ("answer", "clarify"):
            return "direct_response"
        if self.scope == "single_step":
            return "single_step"
        if self.scope in ("partial", "full"):
            return "complex"
        if self.complexity:
            return self.complexity
        return "single_step"

    def _derive_analysis_type(self) -> str:
        """Derive legacy analysis_type from v2 fields.

        Preserves an explicitly provided concrete legacy value.  Falls back to
        target, then v2 intent_type, then domain, then the existing value.
        """
        if self.analysis_type and self.analysis_type not in {"", "general", "unknown"}:
            return self.analysis_type
        if self.target:
            return self.target
        intent_type = self.metadata.get("intent_type")
        if intent_type == "qa":
            return "qa"
        if intent_type == "information_request":
            return "information_request"
        if intent_type == "general_help":
            return "general_help"
        if intent_type == "greeting":
            return "greeting"
        if intent_type == "clarification":
            return "clarification"
        if intent_type == "file_conversion":
            return "file_conversion"
        if intent_type == "tool_call":
            return self.metadata.get("tool_name") or "tool_call"
        if self.domain:
            return f"{self.domain}_analysis"
        return self.analysis_type or "general"

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
            "descriptive_statistics": "single-cell-transcriptomics",
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
