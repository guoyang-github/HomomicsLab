"""Step 8: Cell Type Annotation Decision — Single-Cell RNA-seq Pipeline (Python)

Reference: CellTypist, Scanpy 1.10+

Input State:  [Clustered] + markers
Output State: [Annotated]

Recommends annotation method based on data characteristics.
"""

from typing import Optional

import scanpy as sc

from llm_report import generate_llm_report


# ---------------------------------------------------------------------------
# PHASE 1: PROPOSE — Recommend annotation method
# ---------------------------------------------------------------------------

def _celltypist_model_available(tissue: Optional[str]) -> bool:
    """Check whether CellTypist has a model for the given tissue."""
    if tissue is None:
        return False
    available = {
        "immune", "blood", "pbmc",
        "pancreas", "intestine", "gut",
        "lung", "brain", "skin", "liver", "kidney",
    }
    return tissue.lower() in available


def propose_annotation_method(adata: sc.AnnData, tissue_hint: str = None) -> dict:
    """Propose cell type annotation method based on data.

    Parameters
    ----------
    adata : AnnData [Clustered]
    tissue_hint : Optional tissue type hint from user

    Returns
    -------
    dict with recommendation and justification
    """
    n_cells = adata.n_obs
    has_markers = "rank_genes_groups" in adata.uns
    celltypist_ok = _celltypist_model_available(tissue_hint)

    if tissue_hint is not None and celltypist_ok:
        method = "CellTypist"
        reason = (
            f"Tissue type provided ('{tissue_hint}'). "
            f"CellTypist has a pre-trained model for this tissue."
        )
    elif tissue_hint is not None and not celltypist_ok:
        method = "Manual"
        reason = (
            f"Tissue type provided ('{tissue_hint}') but CellTypist has no model for it. "
            f"Manual annotation with known markers is recommended."
        )
    elif n_cells > 10000:
        method = "CellTypist"
        reason = (
            f"Large dataset ({n_cells} cells). CellTypist scales well. "
            "Consider providing tissue type for better accuracy."
        )
    else:
        method = "CellTypist"
        reason = "Default to CellTypist for automated annotation."

    return {
        "recommendation": {
            "method": method,
            "tissue": tissue_hint,
        },
        "diagnostics": {
            "n_cells": n_cells,
            "n_clusters": adata.obs["leiden"].nunique(),
            "has_markers": has_markers,
            "celltypist_model_available": celltypist_ok,
        },
        "justification": reason,
        "alternatives": {
            "CellTypist": "Best for immune cells. Uses pre-trained models. Fast.",
            "Manual": "Use when automated methods fail or for novel populations.",
        },
    }


# ---------------------------------------------------------------------------
# PHASE 1.5: EVALUATE — Guardrail layer
# ---------------------------------------------------------------------------

def evaluate_annotation_proposal(proposal: dict, adata: sc.AnnData) -> dict:
    """Evaluate annotation proposal before execution.

    Guardrails:
      - Method = CellTypist but model not available → CAUTION
      - No clusters found → BLOCK
      - Very high cluster count (>50) with CellTypist → CAUTION
    """
    rec = proposal["recommendation"]
    method = rec["method"]

    n_clusters = adata.obs["leiden"].nunique()
    if n_clusters < 2:
        return {
            "verdict": "BLOCK",
            "adjusted": False,
            "reason": f"Only {n_clusters} cluster found. Annotation requires at least 2 clusters.",
        }

    if method == "CellTypist" and not proposal["diagnostics"]["celltypist_model_available"]:
        return {
            "verdict": "CAUTION",
            "adjusted": False,
            "reason": (
                f"Tissue '{rec.get('tissue', 'unknown')}' not in CellTypist model list. "
                "Consider manual annotation."
            ),
        }

    if method == "CellTypist" and n_clusters > 50:
        return {
            "verdict": "CAUTION",
            "adjusted": False,
            "reason": f"Very high cluster count ({n_clusters}). CellTypist may be slow; consider downsampling.",
        }

    return {"verdict": "PROCEED", "adjusted": False}


# ---------------------------------------------------------------------------
# PHASE 2: EXECUTE — Annotation methods
# ---------------------------------------------------------------------------

def _get_celltypist_model(tissue: str = None) -> Optional[str]:
    """Select CellTypist model based on tissue type.

    Returns None if no suitable model exists for the tissue.
    """
    tissue_map = {
        "immune": "Immune_All_Low.pkl",
        "blood": "Immune_All_Low.pkl",
        "pbmc": "Immune_All_Low.pkl",
        "intestine": "Cells_Intestinal_Tract.pkl",
        "gut": "Cells_Intestinal_Tract.pkl",
        "lung": "Cells_Lung_Airway.pkl",
        "brain": "Cells_Ectoderm.pkl",
        "skin": "Cells_Ectoderm.pkl",
    }
    if tissue is None:
        return None
    tissue_lower = tissue.lower()
    return tissue_map.get(tissue_lower)


def execute_celltypist_annotation(adata: sc.AnnData, model: str = None,
                                  tissue: str = None, **kwargs) -> sc.AnnData:
    """Run CellTypist annotation.

    Requires bio-single-cell-annotation-celltypist skill or celltypist package.

    Parameters
    ----------
    adata : AnnData [Clustered]
    model : CellTypist model name (auto-selected from tissue if None)
    tissue : Tissue type hint for model selection
    **kwargs : Additional args

    Returns
    -------
    AnnData [Annotated] with 'cell_type' in obs

    Raises
    ------
    ValueError
        If no CellTypist model is available for the given tissue.
    """
    try:
        import celltypist
        from celltypist import models
    except ImportError:
        raise ImportError(
            "CellTypist annotation requires celltypist. "
            "Install: pip install celltypist"
        )

    if model is None:
        model = _get_celltypist_model(tissue)

    if model is None:
        raise ValueError(
            f"No CellTypist model available for tissue '{tissue}'. "
            f"Available tissues: immune, blood, pbmc, pancreas, intestine, gut, "
            f"lung, brain, skin, liver, kidney. "
            f"Provide model= explicitly, or use method='Manual'."
        )

    # Download model if needed
    models.download_models(model=model)

    # Run prediction
    predictions = celltypist.annotate(adata, model=model, **kwargs)

    # Add predictions to obs
    adata.obs["cell_type"] = predictions.predicted_labels.predicted_labels
    adata.obs["cell_type_score"] = predictions.predicted_labels.max_prob

    adata.uns["annotation_method"] = "CellTypist"
    adata.uns["pipeline_state"] = "Annotated"

    return adata


def execute_manual_annotation(adata: sc.AnnData, cluster_annotations: dict) -> sc.AnnData:
    """Apply manual cluster-to-cell-type mapping.

    Parameters
    ----------
    adata : AnnData
    cluster_annotations : Dict mapping cluster_id (str) to cell_type

    Returns
    -------
    AnnData [Annotated]
    """
    adata.obs["cell_type"] = adata.obs["leiden"].astype(str).map(cluster_annotations)
    adata.uns["annotation_method"] = "Manual"
    adata.uns["pipeline_state"] = "Annotated"

    return adata


# ---------------------------------------------------------------------------
# PHASE 3: REPORT
# ---------------------------------------------------------------------------

def report_annotation(adata: sc.AnnData) -> dict:
    """Report annotation results."""
    method = adata.uns.get("annotation_method", "Unknown")
    cell_types = adata.obs["cell_type"].value_counts()

    n_unassigned = adata.obs["cell_type"].isna().sum() + (adata.obs["cell_type"] == "Unknown").sum()
    pct_assigned = (1 - n_unassigned / adata.n_obs) * 100

    if pct_assigned < 50:
        status = "WARNING"
    elif pct_assigned < 80:
        status = "CAUTION"
    else:
        status = "PASS"

    return {
        "step": "Cell Type Annotation",
        "status": status,
        "method": method,
        "n_cell_types": adata.obs["cell_type"].nunique(),
        "pct_assigned": round(pct_assigned, 1),
        "cell_type_table": cell_types.to_dict(),
        "recommendation": (
            "<50% cells assigned. Try different annotation method or provide tissue-specific markers."
            if status == "WARNING"
            else (
                "Partial assignment. Review unassigned clusters; may need manual curation."
                if status == "CAUTION"
                else "Good assignment rate. Pipeline complete."
            )
        ),
        "next_step": "Pipeline complete. Optional: downstream analysis (differential expression, pathway analysis, etc.)",
    }


# ---------------------------------------------------------------------------
# Full step wrapper
# ---------------------------------------------------------------------------

def run_annotation_step(adata: sc.AnnData, method: str = None,
                        tissue: str = None, cluster_annotations: dict = None,
                        auto: bool = False, use_llm: bool = True,
                        prev_reports: dict = None, **kwargs) -> dict:
    """Complete annotation step.

    Parameters
    ----------
    adata : AnnData [Clustered]
    method : "CellTypist" or "Manual" (None = auto-propose)
    tissue : Tissue type hint
    cluster_annotations : For manual annotation
    auto : Skip proposal display
    use_llm : If True, generate LLM diagnostic card.
    **kwargs : Passed to annotation function

    Returns
    -------
    dict with keys: obj, report, proposal, llm_report
    """
    expected_states = {"Clustered"}
    current_state = adata.uns.get("pipeline_state")
    if current_state not in expected_states:
        import warnings
        warnings.warn(
            f"Expected input state 'Clustered' for annotation step, got '{current_state}'. "
            "Proceeding anyway, but results may be unexpected."
        )

    proposal = propose_annotation_method(adata, tissue_hint=tissue)

    # Evaluate phase: guardrail on annotation feasibility
    evaluation = evaluate_annotation_proposal(proposal, adata)
    if evaluation["verdict"] == "BLOCK":
        raise RuntimeError(evaluation["reason"])
    elif evaluation["verdict"] == "CAUTION":
        print(f"CAUTION: {evaluation['reason']}")

    if method is None:
        method = proposal["recommendation"]["method"]

    if not auto:
        print("\n=== Annotation Proposal ===")
        print(f"Recommended method: {method}")
        print(f"Justification: {proposal['justification']}")
        if tissue is not None:
            print(f"Tissue: {tissue}")

    if method == "CellTypist":
        adata = execute_celltypist_annotation(adata, tissue=tissue, **kwargs)
    elif method == "Manual":
        if cluster_annotations is None:
            raise ValueError("Manual annotation requires cluster_annotations parameter")
        adata = execute_manual_annotation(adata, cluster_annotations)
    else:
        raise ValueError(f"Unknown annotation method: {method}")

    report = report_annotation(adata)

    # LLM enhancement
    llm_report = None
    if use_llm:
        llm_report = generate_llm_report("annotation", adata, proposal, report, prev_reports)
        if not auto:
            print(llm_report)

    return {"obj": adata, "report": report, "proposal": proposal, "llm_report": llm_report}
