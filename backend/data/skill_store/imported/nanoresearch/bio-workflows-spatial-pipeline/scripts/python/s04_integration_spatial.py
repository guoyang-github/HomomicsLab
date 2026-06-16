"""Step 4: Integration Decision — Spatial Transcriptomics Pipeline (Python)

Reference: scanpy 1.10+, harmonypy (optional)

Input State:  [Normalized] + [HVG]
Output State: [Integrated] (if needed) or [Normalized] (if skipped)
"""

import numpy as np
import scanpy as sc
from sklearn.metrics import silhouette_score

from llm_report import generate_llm_report


def propose_integration(adata: sc.AnnData, sample_col: str = "sample_id") -> dict:
    """Diagnose batch effects and propose integration strategy."""
    if sample_col not in adata.obs.columns:
        return {
            "recommendation": {"integrate": False, "method": None,
                               "reason": f"No '{sample_col}' column found. Single-sample analysis."},
            "diagnostics": {"n_samples": 1},
            "justification": "Single sample detected.",
        }

    samples = adata.obs[sample_col].unique()
    n_samples = len(samples)

    if n_samples <= 1:
        return {
            "recommendation": {"integrate": False, "method": None,
                               "reason": "Only one sample detected. Integration not needed."},
            "diagnostics": {"n_samples": n_samples},
            "justification": "Single sample. Proceed directly to clustering.",
        }

    # Quick PCA for diagnostic
    adata_tmp = adata.copy()
    adata_tmp = adata_tmp[:, adata_tmp.var["highly_variable"]]
    sc.pp.scale(adata_tmp, max_value=10)
    sc.tl.pca(adata_tmp, n_comps=30)
    sc.pp.neighbors(adata_tmp, n_neighbors=15, n_pcs=20)
    sc.tl.umap(adata_tmp)

    try:
        sample_labels = adata_tmp.obs[sample_col].astype("category").cat.codes
        embeddings = adata_tmp.obsm["X_umap"]
        sil_score = silhouette_score(embeddings, sample_labels)
        batch_score = (sil_score + 1) / 2
    except Exception:
        batch_score = 0.5

    if batch_score < 0.3:
        integrate = False
        reason = f"Batch mixing score = {batch_score:.2f} (<0.3). Samples well-mixed."
        method = None
    elif batch_score < 0.6:
        integrate = True
        reason = f"Batch mixing score = {batch_score:.2f} (0.3-0.6). Moderate batch effect."
        method = "harmony"
    else:
        integrate = True
        reason = f"Batch mixing score = {batch_score:.2f} (>0.6). Strong batch effect."
        method = "harmony"

    return {
        "recommendation": {
            "integrate": integrate,
            "method": method,
            "sample_col": sample_col,
            "reason": reason,
        },
        "diagnostics": {
            "n_samples": n_samples,
            "n_spots": adata.n_obs,
            "batch_mixing_score": round(batch_score, 3),
        },
        "justification": reason,
        "alternatives": {
            "harmony": "Fast, works for most cases (2-5 samples).",
            "scanorama": "Good for many samples with different gene sets.",
        },
    }


# ---------------------------------------------------------------------------
# PHASE 1.5: EVALUATE — Guardrail layer
# ---------------------------------------------------------------------------

def evaluate_integration_proposal(proposal: dict, adata: sc.AnnData) -> dict:
    """Evaluate spatial integration proposal before execution.

    Guardrails:
      - Single sample / integrate=False -> PROCEED (skip)
      - batch_mixing_score < 0.1 -> BLOCK (force skip)
      - batch_mixing_score > 0.9 -> CAUTION
    """
    rec = proposal["recommendation"]

    if not rec["integrate"]:
        return {
            "verdict": "PROCEED",
            "adjusted": False,
            "reason": "Single sample or integration not recommended. Skipping execution.",
        }

    score = proposal["diagnostics"].get("batch_mixing_score")

    if score is not None and score < 0.1:
        return {
            "verdict": "BLOCK",
            "adjusted": True,
            "reason": (
                f"Batch mixing score = {score:.3f} (<0.1). Already perfectly mixed. "
                "Integration may remove biological signal. Forcing skip."
            ),
            "adjusted_recommendation": {"integrate": False, "method": None},
        }

    if score is not None and score > 0.9:
        return {
            "verdict": "CAUTION",
            "adjusted": False,
            "reason": (
                f"Batch mixing score = {score:.3f} (>0.9). Extremely strong batch effect. "
                "Verify samples are comparable."
            ),
        }

    return {"verdict": "PROCEED", "adjusted": False}


# ---------------------------------------------------------------------------
# PHASE 2: EXECUTE
# ---------------------------------------------------------------------------

def execute_integration(adata: sc.AnnData, method: str = "harmony",
                        sample_col: str = "sample_id", **kwargs) -> sc.AnnData:
    """Run batch integration with specified method."""
    if method == "harmony":
        try:
            # Ensure PCA exists before integration
            if "pca" not in adata.uns or "X_pca" not in adata.obsm:
                adata_hvg = adata[:, adata.var["highly_variable"]].copy()
                sc.pp.scale(adata_hvg, max_value=10)
                sc.tl.pca(adata_hvg, n_comps=50, use_highly_variable=True)
                adata.obsm["X_pca"] = adata_hvg.obsm["X_pca"]
                adata.uns["pca"] = adata_hvg.uns["pca"]
            # Backup original PCA before overwriting
            adata.obsm["X_pca_pre_harmony"] = adata.obsm["X_pca"].copy()
            sc.external.pp.harmony_integrate(adata, key=sample_col, **kwargs)
            adata.obsm["X_pca"] = adata.obsm["X_pca_harmony"]
            adata.uns["integration_reduction"] = "pca_harmony"
        except ImportError:
            raise ImportError(
                "Harmony integration requires harmonypy. Install: pip install harmonypy"
            )
    else:
        raise ValueError(f"Unknown integration method: {method}")

    adata.uns["pipeline_state"] = "Integrated"
    adata.uns["integration_method"] = method
    print(f"Integration complete: {method}")

    return adata


def skip_integration(adata: sc.AnnData) -> sc.AnnData:
    """Tag object as proceeding without integration."""
    adata.uns["pipeline_state"] = "Normalized"
    adata.uns["integration_method"] = "None"
    adata.uns["integration_reduction"] = "pca"
    return adata


def report_integration(adata: sc.AnnData, proposal: dict) -> dict:
    """Report integration results."""
    method = adata.uns.get("integration_method", "Unknown")

    if method == "None":
        return {
            "step": "Batch Integration",
            "status": "SKIPPED",
            "method": "None",
            "reason": proposal["recommendation"]["reason"],
            "recommendation": "Integration not needed. Proceed to clustering using PCA embeddings.",
            "next_step": "Step 5: Clustering + UMAP",
        }
    else:
        return {
            "step": "Batch Integration",
            "status": "PASS",
            "method": method,
            "n_samples": proposal["diagnostics"]["n_samples"],
            "recommendation": (
                f"Integration with {method} complete. "
                f"Use '{adata.uns.get('integration_reduction', 'pca')}' for downstream clustering."
            ),
            "next_step": "Step 5: Clustering + UMAP",
        }


def run_integration_step(adata: sc.AnnData, sample_col: str = "sample_id",
                         method: str = None, auto: bool = False,
                         use_llm: bool = True, prev_reports: dict = None,
                         **kwargs) -> dict:
    """Complete integration decision step."""
    expected_states = {"Normalized"}
    current_state = adata.uns.get("pipeline_state")
    if current_state not in expected_states:
        import warnings
        warnings.warn(
            f"Expected input state 'Normalized' for integration step, got '{current_state}'. "
            "Proceeding anyway, but results may be unexpected."
        )

    proposal = propose_integration(adata, sample_col=sample_col)

    # Evaluate phase: guardrail on batch mixing score
    evaluation = evaluate_integration_proposal(proposal, adata)
    if evaluation["adjusted"]:
        print(f"GUARDRAIL: {evaluation['reason']}")
        proposal["recommendation"] = evaluation["adjusted_recommendation"]
    elif evaluation["verdict"] == "CAUTION":
        print(f"CAUTION: {evaluation['reason']}")

    if not auto:
        print("\n=== Integration Proposal ===")
        print(f"Samples detected: {proposal['diagnostics']['n_samples']}")
        if "batch_mixing_score" in proposal["diagnostics"]:
            print(f"Batch mixing score: {proposal['diagnostics']['batch_mixing_score']:.3f}")
        print(f"Recommendation: {proposal['justification']}")
        if proposal["recommendation"]["integrate"]:
            print(f"Suggested method: {proposal['recommendation']['method']}")

    if method is None:
        integrate = proposal["recommendation"]["integrate"]
        method = proposal["recommendation"]["method"]
    else:
        integrate = method != "None"

    if integrate:
        adata = execute_integration(adata, method=method, sample_col=sample_col, **kwargs)
    else:
        adata = skip_integration(adata)

    report = report_integration(adata, proposal)

    llm_report = None
    if use_llm:
        llm_report = generate_llm_report("integration", adata, proposal, report, prev_reports)
        if not auto:
            print(llm_report)

    return {"obj": adata, "report": report, "proposal": proposal, "llm_report": llm_report}
