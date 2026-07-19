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
    system should respond*.

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


# Map between the plan-layer intent vocabulary (domain.yaml intent ids such as
# ``single_cell_analysis``) and v2 domain tags.  The analyzer uses the forward
# direction to tag keyword-matched intents with their domain; the reverse
# direction lets :func:`intent_strategy_key` recover the plan-layer key of a
# domain-level intent from its v2 domain tag.
ANALYSIS_KEY_TO_DOMAIN: Dict[str, str] = {
    "single_cell_analysis": "single-cell-transcriptomics",
    "spatial_analysis": "spatial-transcriptomics",
    "metagenomics_analysis": "metagenomics",
    "genomics_analysis": "genomics",
    "proteomics_analysis": "proteomics",
    "transcriptomics_analysis": "transcriptomics",
    "epigenomics_analysis": "epigenomics",
    "descriptive_statistics": "single-cell-transcriptomics",
}
DOMAIN_TO_ANALYSIS_KEY: Dict[str, str] = {
    domain: key
    for key, domain in ANALYSIS_KEY_TO_DOMAIN.items()
    if key.endswith("_analysis")
}

# Intent types that are answered directly without skill execution.
DIRECT_INTENT_TYPES = {"qa", "information_request", "general_help", "greeting", "clarification"}


def intent_strategy_key(intent: "UserIntent") -> str:
    """Derive the plan-layer intent key from the v2 intent fields.

    The plan layer (domain strategies, analysis templates, curated Nextflow
    templates, nf-core mappings, CBKB anomaly categories) is keyed on the
    domain.yaml intent vocabulary (``single_cell_analysis``, phase ids, MCP
    tool names).  That key is derived from the v2 representation:

    - ``analysis`` / ``tool_call`` intents key on their concrete ``target``
      (phase id, tool name, action id), falling back to the domain-level key
      recovered from the v2 domain tag;
    - every other intent keys on its ``intent_type``.
    """
    intent_type = intent.intent_type or "general"
    if intent_type in ("analysis", "tool_call"):
        if intent.target:
            return intent.target
        if intent.domain:
            key = DOMAIN_TO_ANALYSIS_KEY.get(intent.domain)
            if key:
                return key
            return f"{intent.domain}_analysis"
    return intent_type


def intent_plan_complexity(intent: "UserIntent") -> str:
    """Derive the plan-layer complexity label from the v2 intent fields."""
    if intent.interaction_mode in ("answer", "clarify"):
        return "direct_response"
    if intent.scope == "single_step":
        return "single_step"
    return "complex"


@dataclass
class UserIntent:
    """User-facing intent object (v2 schema).

    ``intent_type``, ``interaction_mode``, ``scope``, ``domain`` and ``target``
    are the single source of truth.  When the intent came from a structured
    classifier, ``structured_intent`` carries the raw classifier output and
    its fields are applied on top of the explicitly provided values.
    """

    confidence: float = 1.0
    original_message: str = ""
    data_scale: Optional[str] = None
    urgency: str = "normal"
    domain_knowledge: List[str] = field(default_factory=list)
    sub_intents: List["UserIntent"] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Structured intent decomposition (v2, source of truth).
    intent_type: str = ""  # qa | information_request | general_help | greeting | file_conversion | analysis | tool_call | clarification | general
    interaction_mode: str = ""  # answer | execute | explore | troubleshoot | modify | approve | clarify
    domain: Optional[str] = None
    target: Optional[str] = None
    scope: str = ""  # full | partial | single_step

    # Raw classifier output, when the intent came from a structured classifier.
    structured_intent: Optional[StructuredIntent] = None

    def __post_init__(self):
        if self.structured_intent is not None:
            self._apply_structured_intent()
        self._normalize()

    def _normalize(self) -> None:
        """Fill unset v2 fields with defaults derived from the provided ones."""
        if not self.intent_type:
            if self.interaction_mode == "clarify":
                self.intent_type = "clarification"
            elif self.target or self.interaction_mode not in ("", "answer"):
                self.intent_type = "analysis"
            else:
                self.intent_type = "general"
        if not self.interaction_mode:
            if self.intent_type == "clarification":
                self.interaction_mode = "clarify"
            elif self.intent_type in DIRECT_INTENT_TYPES:
                self.interaction_mode = "answer"
            else:
                self.interaction_mode = "execute"
        if not self.scope:
            self.scope = "single_step"

    def _apply_structured_intent(self) -> None:
        """Populate v2 fields from a StructuredIntent.

        The StructuredIntent is the source of truth for the fields it
        explicitly provides.
        """
        s = self.structured_intent
        if s is None:
            return
        if s.intent_type:
            self.intent_type = s.intent_type
        if s.interaction_mode:
            self.interaction_mode = s.interaction_mode
        if s.scope:
            self.scope = s.scope
        if s.domain is not None:
            self.domain = s.domain
        if s.target is not None:
            self.target = s.target
        if s.reason:
            self.metadata.setdefault("reason", s.reason)

        # Merge entities into metadata for downstream use. Some LLMs return
        # entities as a string or a list instead of the requested object; guard
        # against that instead of crashing intent analysis.
        if s.entities and isinstance(s.entities, dict):
            self.metadata = {**s.entities, **self.metadata}
