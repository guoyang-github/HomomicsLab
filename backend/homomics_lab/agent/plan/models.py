"""Models for PlanEngine."""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from homomics_lab.skills.models import SkillDefinition


@dataclass
class DataState:
    """Current state of the data being analyzed — domain-extensible.

    PlanEngine uses this to decide whether to insert, skip, or modify steps.

    Universal fields (all domains):
      - current_phase: current execution phase
      - has_qc: whether QC has been completed
      - low_quality: whether data quality is flagged
      - n_samples: number of samples

    Domain-specific fields are stored in domain_state[<domain>][<field>].
    This avoids DataState field proliferation when adding new domains.

    Access patterns:
      ds.has_qc                    # universal field (direct attribute)
      ds.get("n_cells")           # tries direct attr, then all domain namespaces
      ds.get("host_contamination", domain="metagenomics")  # specific namespace
      ds.set("n_asvs", 5000, domain="metagenomics")        # set in namespace
    """

    # ── Universal fields (all domains) ──
    current_phase: Optional[str] = None
    has_qc: bool = False
    low_quality: bool = False
    n_samples: Optional[int] = None
    data_type: Optional[str] = None  # e.g. "10x", "smart-seq2", "bulk-rnaseq"

    # ── Legacy single-cell fields (for backward compatibility) ──
    # These will be deprecated in favor of domain_state["single_cell"]
    has_normalization: bool = False
    has_pca: bool = False
    has_clustering: bool = False
    has_annotation: bool = False
    n_cells: Optional[int] = None
    n_genes: Optional[int] = None
    n_batches: Optional[int] = None
    batch_detected: bool = False
    large_scale: bool = False

    # ── Domain-specific state storage ──
    domain_state: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def get(self, key: str, domain: Optional[str] = None, default: Any = None) -> Any:
        """Get a state value with flexible lookup.

        Lookup order:
        1. If domain specified: check domain_state[domain][key]
        2. Check direct attribute on self
        3. Search all domain namespaces for key
        4. Return default
        """
        # 1. Specific domain namespace
        if domain is not None:
            if domain in self.domain_state and key in self.domain_state[domain]:
                return self.domain_state[domain][key]
            return default

        # 2. Direct attribute
        if hasattr(self, key):
            val = getattr(self, key)
            if val is not None:
                return val

        # 3. Search all domain namespaces
        for ns_values in self.domain_state.values():
            if key in ns_values:
                return ns_values[key]

        # 4. Default
        return default

    def set(self, key: str, value: Any, domain: Optional[str] = None) -> None:
        """Set a state value.

        If domain is specified, stores in domain_state[domain][key].
        Otherwise, tries to set as direct attribute (for universal fields).
        """
        if domain is not None:
            if domain not in self.domain_state:
                self.domain_state[domain] = {}
            self.domain_state[domain][key] = value
        elif hasattr(self, key) and key != "domain_state":
            setattr(self, key, value)
        else:
            # Fallback: store in a "_general" namespace
            if "_general" not in self.domain_state:
                self.domain_state["_general"] = {}
            self.domain_state["_general"][key] = value

    def to_context(self) -> str:
        """Generate a human-readable description of the data state."""
        parts = []
        if self.has_qc:
            parts.append("QC completed")
        if self.low_quality:
            parts.append("low data quality")
        if self.n_samples is not None:
            parts.append(f"{self.n_samples} samples")

        # Single-cell context
        if self.has_normalization:
            parts.append("normalized")
        if self.has_pca:
            parts.append("PCA computed")
        if self.has_clustering:
            parts.append("clusters identified")
        if self.has_annotation:
            parts.append("cell types annotated")
        if self.batch_detected:
            parts.append("multiple batches detected")
        if self.large_scale:
            parts.append("large dataset")

        # Domain-specific context
        for domain, fields in self.domain_state.items():
            if domain.startswith("_"):
                continue
            for field_name, value in fields.items():
                if isinstance(value, bool) and value:
                    parts.append(f"{domain}.{field_name}")
                elif value is not None and not isinstance(value, bool):
                    parts.append(f"{domain}.{field_name}={value}")

        return ", ".join(parts) if parts else "raw data"

    def has_field(self, key: str) -> bool:
        """Check if a field exists (has non-None value)."""
        return self.get(key) is not None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DataState":
        """Deserialize from a plain dict."""
        return cls(**data)


@dataclass
class PlannedGap:
    """A gap detected between two planned phases."""

    from_phase: str
    to_phase: str
    from_skill: Optional[str]
    to_skill: Optional[str]
    gap_type: str  # "field_missing" | "format_conversion" | "parameter_mapping" | "none"
    estimated_complexity: str = "simple"  # "simple" | "moderate" | "complex"
    requires_hitl: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlannedGap":
        """Deserialize from a plain dict."""
        return cls(**data)


@dataclass
class StrategyTrace:
    """Auditable trace of how a plan's strategy and template were chosen."""

    intent_analysis_type: str
    selected_strategy_name: str
    intent_confidence: Optional[float] = None
    intent_reason: Optional[str] = None
    intent_alternatives: List[Dict[str, Any]] = field(default_factory=list)
    strategy_candidates: List[Dict[str, Any]] = field(default_factory=list)
    applied_template_id: Optional[str] = None
    applied_template_name: Optional[str] = None
    data_state_snapshot: Dict[str, Any] = field(default_factory=dict)
    state_checks_triggered: List[Dict[str, Any]] = field(default_factory=list)
    quality_score: Optional[float] = None
    is_fallback: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StrategyTrace":
        """Deserialize from a plain dict."""
        return cls(**data)


@dataclass
class SuccessCriterion:
    """A single success criterion for a phase gate."""

    metric: str  # e.g. "result.qc.pass_rate" or "data_state.n_cells"
    operator: str  # >, <, ==, >=, <=, in, not_in, contains
    threshold: Any
    on_failure: str = "hitl"  # "hitl" | "replan"
    message: str = ""
    replan_context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Phase:
    """A single phase in an analysis plan."""

    phase_type: str  # "qc" | "normalization" | "dim_reduction" | "clustering" | ...
    required: bool = True
    description: str = ""
    selected_skill: Optional[SkillDefinition] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    candidate_skills: List[str] = field(default_factory=list)
    default_skill: Optional[str] = None
    parameter_recommendations: Dict[str, str] = field(default_factory=dict)
    parameter_sources: Dict[str, str] = field(default_factory=dict)
    agent_code: Optional[str] = None  # Agent-generated bridging code
    readonly: bool = False  # True for suggestion-only phases (e.g., LLM-generated code)
    success_criteria: List[SuccessCriterion] = field(default_factory=list)
    snapshot_policy: str = "auto"  # "auto" | "always" | "never"

    # Provenance / anti-hallucination metadata.
    derivation: Optional[str] = None  # e.g. "domain-strategy", "standalone-skill", "llm-fallback"
    risk_level: str = "low"  # "low" | "medium" | "high"

    # Cross-domain composition metadata.
    merged_from_domains: List[str] = field(default_factory=list)

    # Execution estimates (best-effort; populated by the plan engine).
    estimated_cost_usd: Optional[float] = None
    estimated_duration_seconds: Optional[float] = None
    estimated_input_tokens: Optional[int] = None
    estimated_output_tokens: Optional[int] = None
    estimated_cpu_cores: int = 2
    estimated_memory_gb: Optional[float] = None

    def __post_init__(self):
        if not self.description:
            self.description = f"{self.phase_type} analysis step"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize phase to a plain dict."""
        data = asdict(self)
        if self.selected_skill is not None:
            data["selected_skill"] = self.selected_skill.model_dump(mode="json")
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Phase":
        """Deserialize phase from a plain dict."""
        data = dict(data)
        skill_data = data.get("selected_skill")
        if skill_data is not None:
            data["selected_skill"] = SkillDefinition.model_validate(skill_data)
        criteria_data = data.get("success_criteria")
        if criteria_data is not None:
            data["success_criteria"] = [
                SuccessCriterion(**c) for c in criteria_data
            ]
        return cls(**data)


@dataclass
class PlanResult:
    """Result of plan generation."""

    phases: List[Phase]
    strategy_name: str
    data_state: DataState
    gaps: List[PlannedGap] = field(default_factory=list)
    reproducibility_context: Dict[str, Any] = field(default_factory=dict)
    is_fallback: bool = False
    is_information_request: bool = False
    suggestion_text: Optional[str] = None
    phase_transitions: List[Dict[str, str]] = field(default_factory=list)
    risks: List[Dict[str, Any]] = field(default_factory=list)
    strategy_trace: Optional[StrategyTrace] = None

    # Anti-hallucination / governance fields.
    derivation: Optional[str] = None  # highest-level provenance label
    risk_level: str = "low"  # aggregated from phases; "low" | "medium" | "high"
    approval_required: bool = False  # when True, execution must be explicitly approved

    # Plan-level execution mode: "auto" | "fixed_pipeline" | "codeact".
    # "auto" (default) defers per-phase routing to the ExecutionRouter;
    # "fixed_pipeline" runs curated skills as-is; "codeact" generates code.
    # Filled by ModeSelector in PlanEngine when left at the default.
    execution_mode: str = "auto"

    @property
    def skill_sequence(self) -> List[str]:
        """Extract the sequence of selected skill IDs."""
        return [
            p.selected_skill.id
            for p in self.phases
            if p.selected_skill is not None
        ]

    @property
    def total_estimated_cost_usd(self) -> Optional[float]:
        """Sum per-phase cost estimates when all phases have one."""
        costs = [p.estimated_cost_usd for p in self.phases if p.estimated_cost_usd is not None]
        return sum(costs) if costs else None

    @property
    def total_estimated_duration_seconds(self) -> Optional[float]:
        """Sum per-phase duration estimates when all phases have one."""
        durations = [p.estimated_duration_seconds for p in self.phases if p.estimated_duration_seconds is not None]
        return sum(durations) if durations else None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize plan result to a plain dict."""
        result = {
            "phases": [p.to_dict() for p in self.phases],
            "strategy_name": self.strategy_name,
            "data_state": self.data_state.to_dict(),
            "gaps": [g.to_dict() for g in self.gaps],
            "reproducibility_context": self.reproducibility_context,
            "is_fallback": self.is_fallback,
            "is_information_request": self.is_information_request,
            "suggestion_text": self.suggestion_text,
            "phase_transitions": self.phase_transitions,
            "risks": self.risks,
            "total_estimated_cost_usd": self.total_estimated_cost_usd,
            "total_estimated_duration_seconds": self.total_estimated_duration_seconds,
            "derivation": self.derivation,
            "risk_level": self.risk_level,
            "approval_required": self.approval_required,
            "execution_mode": self.execution_mode,
        }
        if self.strategy_trace is not None:
            result["strategy_trace"] = self.strategy_trace.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlanResult":
        """Deserialize plan result from a plain dict."""
        trace_data = data.get("strategy_trace")
        return cls(
            phases=[Phase.from_dict(p) for p in data.get("phases", [])],
            strategy_name=data.get("strategy_name", "unknown"),
            data_state=DataState.from_dict(data.get("data_state", {})),
            gaps=[PlannedGap.from_dict(g) for g in data.get("gaps", [])],
            reproducibility_context=data.get("reproducibility_context", {}),
            is_fallback=data.get("is_fallback", False),
            is_information_request=data.get("is_information_request", False),
            suggestion_text=data.get("suggestion_text"),
            phase_transitions=data.get("phase_transitions", []),
            risks=data.get("risks", []),
            strategy_trace=StrategyTrace.from_dict(trace_data) if trace_data else None,
            derivation=data.get("derivation"),
            risk_level=data.get("risk_level", "low"),
            approval_required=data.get("approval_required", False),
            execution_mode=data.get("execution_mode", "auto"),
        )
