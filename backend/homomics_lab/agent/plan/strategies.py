"""Analysis strategy templates — domain knowledge for plan generation."""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from homomics_lab.agent.plan.models import DataState, Phase


@dataclass
class StateCheck:
    """A conditional check on data state that may modify the plan."""

    condition: Callable[[DataState], bool]
    action: str  # "insert" | "skip" | "modify_param"
    target: str  # phase_type or param name
    value: Any = None  # new phase or param value
    after: Optional[str] = None  # for insert: phase to insert after


@dataclass
class AnalysisStrategy:
    """A reusable analysis strategy (domain knowledge template).

    Strategies define the standard skeleton for a type of analysis.
    The PlanEngine adapts the skeleton based on the current DataState.
    """

    name: str
    description: str
    applicable_intents: List[str]  # intent patterns this strategy matches
    skeleton: List[Phase]
    state_checks: List[StateCheck] = field(default_factory=list)

    def generate_skeleton(self, data_state: DataState) -> List[Phase]:
        """Generate the base skeleton, applying state-based modifications."""
        phases = [Phase(phase_type=p.phase_type, required=p.required) for p in self.skeleton]

        for check in self.state_checks:
            if check.condition(data_state):
                if check.action == "insert":
                    self._insert_phase(phases, check)
                elif check.action == "skip":
                    self._skip_phase(phases, check.target)
                elif check.action == "modify_param":
                    self._modify_param(phases, check)

        return phases

    @staticmethod
    def _insert_phase(phases: List[Phase], check: StateCheck) -> None:
        """Insert a new phase after a specific phase type."""
        new_phase = Phase(phase_type=check.target, required=True)
        for i, phase in enumerate(phases):
            if phase.phase_type == check.after:
                phases.insert(i + 1, new_phase)
                return
        # If anchor not found, append
        phases.append(new_phase)

    @staticmethod
    def _skip_phase(phases: List[Phase], phase_type: str) -> None:
        """Mark a phase as skipped."""
        for phase in phases:
            if phase.phase_type == phase_type:
                phase.required = False

    @staticmethod
    def _modify_param(phases: List[Phase], check: StateCheck) -> None:
        """Modify parameters of a specific phase."""
        for phase in phases:
            if phase.phase_type == check.target:
                phase.parameters[check.target] = check.value


class StrategyLibrary:
    """Library of built-in analysis strategies."""

    def __init__(self):
        self._strategies: Dict[str, AnalysisStrategy] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        """Register default strategies."""
        self.register(SINGLE_CELL_STANDARD)
        self.register(SPATIAL_TRANSCRIPTOMICS)
        self.register(QC_ONLY)
        # Load strategies from domain declarations
        self._load_domain_strategies()

    def _load_domain_strategies(self) -> None:
        """Load strategies from domain.yaml declarations.

        Scans the domains/ directory for domain.yaml files and registers
        their strategies automatically.
        """
        from pathlib import Path
        from homomics_lab.domain.loader import DomainLoader
        from homomics_lab.skills.registry import get_default_registry

        domains_dir = Path(__file__).parent.parent.parent / "domains"
        if not domains_dir.exists():
            return

        skill_registry = get_default_registry()
        domain_loader = DomainLoader(skill_registry, self)

        for domain_yaml in domains_dir.rglob("domain.yaml"):
            try:
                domain_loader.load(domain_yaml)
            except Exception:
                # Silently skip invalid domains during default loading
                pass

    def register(self, strategy: AnalysisStrategy) -> None:
        self._strategies[strategy.name] = strategy

    def select(self, intent_analysis_type: str) -> AnalysisStrategy:
        """Select the best strategy for a given intent type."""
        for strategy in self._strategies.values():
            if intent_analysis_type in strategy.applicable_intents:
                return strategy

        # Fallback to generic strategy
        return GENERIC_ANALYSIS

    def get(self, name: str) -> Optional[AnalysisStrategy]:
        return self._strategies.get(name)

    def list_all(self) -> List[AnalysisStrategy]:
        return list(self._strategies.values())


# ─────────────────────────────────────────
# Default strategies
# ─────────────────────────────────────────

SINGLE_CELL_STANDARD = AnalysisStrategy(
    name="single_cell_standard",
    description="Standard single-cell RNA-seq analysis pipeline",
    applicable_intents=["single_cell_analysis", "scRNA", "single cell", "scanpy"],
    skeleton=[
        Phase(phase_type="qc", required=True, description="Quality control filtering"),
        Phase(phase_type="normalization", required=True, description="Count normalization"),
        Phase(phase_type="dim_reduction", required=True, description="PCA dimensionality reduction"),
        Phase(phase_type="clustering", required=True, description="Cell clustering (Louvain/Leiden)"),
        Phase(phase_type="annotation", required=False, description="Cell type annotation"),
        Phase(phase_type="differential_expression", required=False, description="Differential expression analysis"),
        Phase(phase_type="visualization", required=False, description="Generate UMAP and other plots"),
    ],
    state_checks=[
        StateCheck(
            condition=lambda ds: ds.get("batch_detected", default=False),
            action="insert",
            target="batch_correction",
            after="qc",
        ),
        StateCheck(
            condition=lambda ds: ds.get("low_quality", default=False),
            action="insert",
            target="qc_advanced",
            after="qc",
        ),
        StateCheck(
            condition=lambda ds: ds.get("large_scale", default=False),
            action="modify_param",
            target="dim_reduction",
            value={"n_pcs": 50, "method": "incremental_pca"},
        ),
        StateCheck(
            condition=lambda ds: ds.get("has_qc", default=False),
            action="skip",
            target="qc",
        ),
    ],
)

SPATIAL_TRANSCRIPTOMICS = AnalysisStrategy(
    name="spatial_transcriptomics",
    description="Spatial transcriptomics analysis pipeline",
    applicable_intents=["spatial_analysis", "spatial", "visium", "xenium"],
    skeleton=[
        Phase(phase_type="spatial_qc", required=True),
        Phase(phase_type="spatial_preprocessing", required=True),
        Phase(phase_type="spatial_clustering", required=True),
        Phase(phase_type="spatial_deconvolution", required=False),
        Phase(phase_type="visualization", required=False),
    ],
    state_checks=[
        StateCheck(
            condition=lambda ds: ds.get("n_cells") is not None and ds.get("n_cells") < 1000,
            action="skip",
            target="spatial_deconvolution",
        ),
    ],
)

QC_ONLY = AnalysisStrategy(
    name="qc_only",
    description="Run quality control only",
    applicable_intents=["file_conversion", "qc", "quality control"],
    skeleton=[
        Phase(phase_type="qc", required=True),
    ],
    state_checks=[],
)

GENERIC_ANALYSIS = AnalysisStrategy(
    name="generic",
    description="Generic flexible analysis",
    applicable_intents=["general", "analysis"],
    skeleton=[
        Phase(phase_type="data_loading", required=True),
        Phase(phase_type="exploratory", required=False),
        Phase(phase_type="analysis", required=False),
        Phase(phase_type="visualization", required=False),
    ],
    state_checks=[],
)
