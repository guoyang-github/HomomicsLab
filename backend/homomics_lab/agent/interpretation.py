"""InterpretationEngine — active result interpretation and recommendation.

Operates at the phase level (not every step) to avoid verbosity:
  1. Phase-complete: interpret results when a phase finishes
  2. Anomaly-triggered: interpret when anomalies are detected
  3. HITL checkpoint: interpret when human input is needed
  4. On-demand: interpret when user explicitly requests it

Core workflow:
  1. Assess data quality from skill output
  2. Generate human-readable interpretation (via LLM or templates)
  3. Compare with historical patterns from SemanticMemory
  4. Generate next-step recommendations via SkillDAG
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from homomics_lab.agent.plan.models import DataState, Phase
from homomics_lab.agent.plan.replanning import ReplanningTrigger
from homomics_lab.models.common import PlotAttachment
from homomics_lab.plots import extract_plot_attachments
from homomics_lab.skills.skill_dag import SkillDAG


@dataclass
class QualityAssessment:
    """Quantitative assessment of a phase's output quality."""

    overall: str  # "good" | "acceptable" | "poor"
    metrics: Dict[str, Any] = field(default_factory=dict)
    flags: List[str] = field(default_factory=list)

    def has_anomaly(self) -> bool:
        return len(self.flags) > 0


@dataclass
class Interpretation:
    """Human-readable interpretation of a phase's results."""

    summary: str
    key_findings: List[str] = field(default_factory=list)
    quality_assessment: Optional[QualityAssessment] = None
    recommendations: List["Recommendation"] = field(default_factory=list)
    plots: List[PlotAttachment] = field(default_factory=list)
    confidence: float = 0.8


@dataclass
class Recommendation:
    """A recommended next step or action."""

    type: str  # "next_step" | "caution" | "learned_pattern" | "alternative"
    skill_id: Optional[str] = None
    description: str = ""
    reason: str = ""
    confidence: float = 0.5


class InterpretationEngine:
    """Generates interpretations and recommendations for analysis results.

    Usage:
        interpreter = InterpretationEngine(skill_dag=skill_dag)
        result = interpreter.interpret_phase(
            phase=qc_phase,
            skill_output={"filter_rate": 0.12, "output_cells": 2531},
            data_state=data_state,
        )
        # result.summary -> "QC filtered 12% of cells (2531 remaining), within normal range"
        # result.recommendations -> ["Next: dimensionality reduction with PCA"]
    """

    def __init__(
        self,
        skill_dag: Optional[SkillDAG] = None,
    ):
        self.skill_dag = skill_dag

    def interpret_phase(
        self,
        phase: Phase,
        skill_output: Dict[str, Any],
        data_state: DataState,
        cbkb=None,
    ) -> Interpretation:
        """Interpret the results of a completed phase.

        This is the main entry point called after each phase execution.
        Args:
            cbkb: Optional CBKB instance to auto-archive anomalies.
        """
        # 1. Quantitative quality assessment
        quality = self._assess_quality(phase, skill_output)

        # 2. Generate human-readable summary
        summary = self._generate_summary(phase, skill_output, quality)

        # 3. Extract key findings
        findings = self._extract_findings(phase, skill_output, quality)

        # 4. Generate recommendations
        recommendations = self._generate_recommendations(
            phase, skill_output, quality, data_state
        )

        # 5. Extract visualization plots
        plots = self._extract_plots(phase, skill_output)

        interpretation = Interpretation(
            summary=summary,
            key_findings=findings,
            quality_assessment=quality,
            recommendations=recommendations,
            plots=plots,
            confidence=0.85 if not quality.has_anomaly() else 0.6,
        )

        # 6. Auto-archive anomalies into CBKB
        if cbkb is not None and quality.has_anomaly():
            self._archive_to_cbkb(phase, interpretation, cbkb)

        return interpretation

    def _archive_to_cbkb(self, phase, interpretation, cbkb):
        """Archive anomalies from interpretation into CBKB."""
        from homomics_lab.knowledge.cbkb import AnomalyRecord
        import uuid

        severity = "warning"
        flags = interpretation.quality_assessment.flags if interpretation.quality_assessment else []
        if any("high" in f.lower() or "critical" in f.lower() for f in flags):
            severity = "critical"

        rec = AnomalyRecord(
            id=str(uuid.uuid4()),
            project_id=getattr(phase, "project_id", "unknown"),
            phase_type=getattr(phase, "phase_type", "unknown"),
            summary=interpretation.summary,
            flags=flags,
            recommendations=[r.description for r in interpretation.recommendations],
            severity=severity,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        cbkb.archive_anomaly(rec)

    # ─────────────────────────────────────────
    # Quality assessment (phase-specific logic)
    # ─────────────────────────────────────────

    def _assess_quality(
        self,
        phase: Phase,
        skill_output: Dict[str, Any],
    ) -> QualityAssessment:
        """Assess output quality based on phase type."""
        if phase.phase_type in ("qc", "spatial_qc"):
            return self._assess_qc_quality(skill_output)
        elif phase.phase_type in ("clustering", "spatial_clustering"):
            return self._assess_clustering_quality(skill_output)
        elif phase.phase_type == "dim_reduction":
            return self._assess_dimred_quality(skill_output)
        else:
            return QualityAssessment(overall="good")

    def _assess_qc_quality(self, output: Dict[str, Any]) -> QualityAssessment:
        """Assess QC phase quality."""
        metrics = {}
        flags = []

        input_cells = output.get("input_cells")
        output_cells = output.get("output_cells")
        if input_cells and output_cells:
            filter_rate = 1.0 - (output_cells / input_cells)
            metrics["filter_rate"] = round(filter_rate, 3)
            metrics["retained_cells"] = output_cells

            if filter_rate > 0.5:
                flags.append(f"High cell filtering rate: {filter_rate:.1%} — check data quality")
            elif filter_rate > 0.3:
                flags.append(f"Elevated filtering rate: {filter_rate:.1%}")
            elif filter_rate < 0.05:
                flags.append(f"Very low filtering rate: {filter_rate:.1%} — QC may be too lenient")

        overall = "poor" if len(flags) >= 2 else "acceptable" if flags else "good"
        return QualityAssessment(overall=overall, metrics=metrics, flags=flags)

    def _assess_clustering_quality(self, output: Dict[str, Any]) -> QualityAssessment:
        """Assess clustering phase quality."""
        metrics = {}
        flags = []

        n_clusters = output.get("n_clusters")
        if n_clusters:
            metrics["n_clusters"] = n_clusters
            if n_clusters < 3:
                flags.append(f"Only {n_clusters} clusters detected — may under-resolve cell types")
            elif n_clusters > 50:
                flags.append(f"{n_clusters} clusters — may over-resolve, consider merging")

        overall = "acceptable" if flags else "good"
        return QualityAssessment(overall=overall, metrics=metrics, flags=flags)

    def _assess_dimred_quality(self, output: Dict[str, Any]) -> QualityAssessment:
        """Assess dimensionality reduction quality."""
        metrics = {}
        flags = []

        n_pcs = output.get("n_pcs")
        if n_pcs:
            metrics["n_pcs"] = n_pcs
            if n_pcs < 10:
                flags.append(f"Only {n_pcs} PCs — may lose signal")

        return QualityAssessment(overall="good" if not flags else "acceptable", metrics=metrics, flags=flags)

    # ─────────────────────────────────────────
    # Summary generation
    # ─────────────────────────────────────────

    def _generate_summary(
        self,
        phase: Phase,
        skill_output: Dict[str, Any],
        quality: QualityAssessment,
    ) -> str:
        """Generate a human-readable summary of the phase results."""
        phase_name = phase.phase_type.replace("_", " ").title()

        if phase.phase_type in ("qc", "spatial_qc"):
            return self._summarize_qc(skill_output, quality)
        elif phase.phase_type in ("clustering", "spatial_clustering"):
            return self._summarize_clustering(skill_output, quality)
        elif phase.phase_type == "dim_reduction":
            return self._summarize_dimred(skill_output, quality)
        else:
            return f"{phase_name} completed."

    def _summarize_qc(self, output: Dict[str, Any], quality: QualityAssessment) -> str:
        input_cells = output.get("input_cells")
        output_cells = output.get("output_cells")
        filter_rate = quality.metrics.get("filter_rate")

        if input_cells and output_cells and filter_rate is not None:
            if quality.overall == "good":
                return (
                    f"QC completed: {output_cells:,} of {input_cells:,} cells retained "
                    f"({filter_rate:.1%} filtered). This is within the normal range."
                )
            else:
                return (
                    f"QC completed with caution: {output_cells:,} of {input_cells:,} cells retained "
                    f"({filter_rate:.1%} filtered). {quality.flags[0]}"
                )
        return "QC filtering completed."

    def _summarize_clustering(self, output: Dict[str, Any], quality: QualityAssessment) -> str:
        n_clusters = output.get("n_clusters")
        if n_clusters:
            if quality.overall == "good":
                return f"Clustering identified {n_clusters} distinct cell clusters."
            else:
                return f"Clustering identified {n_clusters} clusters. {quality.flags[0]}"
        return "Clustering completed."

    def _summarize_dimred(self, output: Dict[str, Any], quality: QualityAssessment) -> str:
        n_pcs = output.get("n_pcs")
        if n_pcs:
            return f"Dimensionality reduction computed with {n_pcs} principal components."
        return "Dimensionality reduction completed."

    # ─────────────────────────────────────────
    # Findings extraction
    # ─────────────────────────────────────────

    def _extract_findings(
        self,
        phase: Phase,
        skill_output: Dict[str, Any],
        quality: QualityAssessment,
    ) -> List[str]:
        """Extract key findings from the output."""
        findings = []

        if phase.phase_type in ("qc", "spatial_qc"):
            input_cells = skill_output.get("input_cells")
            output_cells = skill_output.get("output_cells")
            if input_cells and output_cells:
                findings.append(f"Retained {output_cells:,} of {input_cells:,} cells")
                findings.append(f"Filtering rate: {quality.metrics.get('filter_rate', 'unknown')}")

        elif phase.phase_type in ("clustering", "spatial_clustering"):
            n_clusters = skill_output.get("n_clusters")
            if n_clusters:
                findings.append(f"Detected {n_clusters} clusters")

        return findings

    # ─────────────────────────────────────────
    # Recommendation generation
    # ─────────────────────────────────────────

    def _generate_recommendations(
        self,
        phase: Phase,
        skill_output: Dict[str, Any],
        quality: QualityAssessment,
        data_state: DataState,
    ) -> List[Recommendation]:
        """Generate recommendations for next steps."""
        recommendations = []

        # 1. Followed_by recommendations from SkillDAG
        if self.skill_dag and phase.selected_skill:
            followed = self.skill_dag.get_followed_by(phase.selected_skill.id, min_confidence=0.6)
            for skill_id, confidence in followed[:3]:
                recommendations.append(
                    Recommendation(
                        type="next_step",
                        skill_id=skill_id,
                        description=f"Continue with {skill_id}",
                        reason=f"Commonly performed after {phase.selected_skill.name}",
                        confidence=confidence,
                    )
                )

        # 2. Anomaly-based recommendations
        if quality.has_anomaly():
            for flag in quality.flags:
                if "filtering rate" in flag.lower():
                    recommendations.append(
                        Recommendation(
                            type="caution",
                            description="Review QC parameters",
                            reason=flag,
                            confidence=0.9,
                        )
                    )
                elif "clusters" in flag.lower():
                    recommendations.append(
                        Recommendation(
                            type="alternative",
                            description="Try different clustering resolution",
                            reason=flag,
                            confidence=0.7,
                        )
                    )

        # 3. Phase-specific flow recommendations (domain knowledge)
        flow_recommendations = {
            "qc": ["normalization"],
            "normalization": ["dim_reduction"],
            "dim_reduction": ["clustering"],
            "clustering": ["annotation", "differential_expression"],
        }
        next_phases = flow_recommendations.get(phase.phase_type, [])
        for next_phase in next_phases:
            if not getattr(data_state, f"has_{next_phase}", False):
                recommendations.append(
                    Recommendation(
                        type="next_step",
                        description=f"Proceed to {next_phase.replace('_', ' ')}",
                        reason="Standard analysis workflow",
                        confidence=0.95,
                    )
                )

        return recommendations

    def to_triggers(
        self,
        interpretation: Interpretation,
        phase: Phase,
    ) -> List[ReplanningTrigger]:
        """Convert an interpretation into replanning triggers.

        This bridges InterpretationEngine and DynamicReplanningEngine.  Only
        actionable triggers are emitted so that normal results do not cause
        spurious replans.
        """
        triggers: List[ReplanningTrigger] = []
        qa = interpretation.quality_assessment

        if qa is not None and qa.has_anomaly():
            severity = "major"
            if qa.overall == "poor" or any(
                "high" in f.lower() or "critical" in f.lower() for f in qa.flags
            ):
                severity = "critical"
            elif all("lenient" in f.lower() or "low" in f.lower() for f in qa.flags):
                severity = "minor"

            triggers.append(
                ReplanningTrigger(
                    trigger_type="anomaly_detected",
                    context={
                        "phase_type": phase.phase_type,
                        "flags": list(qa.flags),
                        "metrics": dict(qa.metrics),
                    },
                    severity=severity,
                )
            )

        for rec in interpretation.recommendations:
            if rec.type == "alternative" and rec.skill_id:
                triggers.append(
                    ReplanningTrigger(
                        trigger_type="data_state_changed",
                        context={
                            "change_type": "alternative_skill",
                            "phase_type": phase.phase_type,
                            "recommended_skill_id": rec.skill_id,
                            "reason": rec.reason,
                        },
                        severity="minor",
                    )
                )
            elif rec.type == "next_step" and rec.skill_id:
                next_phase = self._infer_phase_type(rec.skill_id, rec.description)
                if next_phase and next_phase != phase.phase_type:
                    triggers.append(
                        ReplanningTrigger(
                            trigger_type="data_state_changed",
                            context={
                                "change_type": "missing_downstream",
                                "phase_type": phase.phase_type,
                                "recommended_phase_type": next_phase,
                                "recommended_skill_id": rec.skill_id,
                                "reason": rec.reason,
                            },
                            severity="minor",
                        )
                    )

        return triggers

    @staticmethod
    def _infer_phase_type(
        skill_id: Optional[str], description: str = ""
    ) -> Optional[str]:
        """Map a skill id or description to a canonical phase type."""
        text = f"{skill_id or ''} {description}".lower()
        mapping = {
            "qc": ["qc", "quality control", "filter"],
            "normalization": ["normaliz", "normalize"],
            "dim_reduction": ["pca", "dim_reduction", "dimensionality"],
            "clustering": ["cluster", "leiden", "louvain"],
            "annotation": ["annotat", "marker", "cell type"],
            "differential_expression": ["de", "deg", "differential"],
            "integration": ["integrat", "batch", "harmony", "combat"],
            "visualization": ["plot", "visual", "umap", "tsne"],
        }
        for phase, keywords in mapping.items():
            if any(k in text for k in keywords):
                return phase
        return None

    def _extract_plots(
        self,
        phase: Phase,
        skill_output: Dict[str, Any],
    ) -> List[PlotAttachment]:
        """Extract visualization plots from skill output.

        Delegates to the shared helper so extraction logic stays consistent
        across InterpretationEngine, TurnRunner and the chat API.
        """
        return extract_plot_attachments(
            skill_output,
            default_plot_type=phase.phase_type,
            default_title=f"{phase.phase_type} visualization",
        )
