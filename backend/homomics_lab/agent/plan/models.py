"""Models for PlanEngine."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from homomics_lab.skills.models import SkillDefinition


@dataclass
class DataState:
    """Current state of the data being analyzed.

    PlanEngine uses this to decide whether to insert, skip, or modify steps.
    """

    current_phase: Optional[str] = None  # e.g., "qc_complete"
    has_qc: bool = False
    has_normalization: bool = False
    has_pca: bool = False
    has_clustering: bool = False
    has_annotation: bool = False

    # Data characteristics
    n_cells: Optional[int] = None
    n_genes: Optional[int] = None
    n_batches: Optional[int] = None
    batch_detected: bool = False
    low_quality: bool = False
    large_scale: bool = False  # > 100k cells

    def to_context(self) -> str:
        """Generate a human-readable description of the data state."""
        parts = []
        if self.has_qc:
            parts.append("QC completed")
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
        if self.low_quality:
            parts.append("low data quality")
        if self.large_scale:
            parts.append("large dataset")
        return ", ".join(parts) if parts else "raw data"


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

    phase_type: str  # "qc" | "normalization" | "dim_reduction" | "clustering" | ...
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
