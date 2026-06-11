"""Refactored PlanEngine models with domain-extensible DataState.

This is the v2 replacement for models.py, introducing domain_state namespace
to avoid field proliferation when adding new domains.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from homomics_lab.skills.models import SkillDefinition


@dataclass
class DataState:
    """Current state of the data being analyzed — domain-extensible.

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


@dataclass
class Phase:
    """A single phase in an analysis plan."""

    phase_type: str
    required: bool = True
    description: str = ""
    selected_skill: Optional[SkillDefinition] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    agent_code: Optional[str] = None  # Agent-generated bridging code

    def __post_init__(self):
        if not self.description:
            self.description = f"{self.phase_type} analysis step"


@dataclass
class PlanResult:
    """Result of plan generation."""

    phases: List[Phase]
    strategy_name: str
    data_state: DataState
    gaps: List[PlannedGap] = field(default_factory=list)
    reproducibility_context: Dict[str, Any] = field(default_factory=dict)

    @property
    def skill_sequence(self) -> List[str]:
        """Extract the sequence of selected skill IDs."""
        return [
            p.selected_skill.id
            for p in self.phases
            if p.selected_skill is not None
        ]
