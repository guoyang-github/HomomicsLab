"""Step 7: Marker Detection — Single-Cell RNA-seq Pipeline (Python)

Reference: scanpy 1.10+

Input State:  [Clustered] + [UMAP]
Output State: [Clustered] + markers
"""

import pandas as pd
import scanpy as sc

from llm_report import generate_llm_report


# ---------------------------------------------------------------------------
# PHASE 1: PROPOSE — Recommend marker detection parameters
# ---------------------------------------------------------------------------

def propose_marker_params(adata: sc.AnnData) -> dict:
    """Propose marker detection parameters."""
    n_clusters = adata.obs["leiden"].nunique()

    return {
        "recommendation": {
            "method": "wilcoxon",
            "n_genes": 200,
        },
        "diagnostics": {
            "n_clusters": n_clusters,
        },
        "justification": (
            "Wilcoxon rank-sum test (default) is robust for most datasets. "
            "Scanpy's rank_genes_groups with method='wilcoxon' is well-validated."
        ),
        "alternatives": {
            "t-test": "Faster but assumes normality; acceptable for large clusters.",
            "logreg": "Uses logistic regression; good for complex data but slower.",
        },
    }


# ---------------------------------------------------------------------------
# PHASE 1.5: EVALUATE — Guardrail layer
# ---------------------------------------------------------------------------

def evaluate_marker_proposal(proposal: dict, adata: sc.AnnData) -> dict:
    """Evaluate marker detection proposal before execution.

    Guardrails:
      - n_clusters < 2 → BLOCK (need at least 2 clusters)
      - n_clusters > 100 → CAUTION (very high, may be slow)
    """
    n_clusters = proposal["diagnostics"]["n_clusters"]

    if n_clusters < 2:
        return {
            "verdict": "BLOCK",
            "adjusted": False,
            "reason": f"Only {n_clusters} cluster found. Marker detection requires at least 2 clusters.",
        }

    if n_clusters > 100:
        return {
            "verdict": "CAUTION",
            "adjusted": False,
            "reason": f"Very high cluster count ({n_clusters}). Marker detection may be slow.",
        }

    return {"verdict": "PROCEED", "adjusted": False}


# ---------------------------------------------------------------------------
# PHASE 2: EXECUTE — rank_genes_groups
# ---------------------------------------------------------------------------

def execute_marker_detection(adata: sc.AnnData, groupby: str = "leiden",
                             method: str = "wilcoxon", **kwargs) -> sc.AnnData:
    """Run marker detection across all clusters.

    Parameters
    ----------
    adata : AnnData [Clustered]
    groupby : Column to group by
    method : Test method ('wilcoxon', 't-test', 'logreg')
    **kwargs : Additional args

    Returns
    -------
    AnnData with markers in uns['rank_genes_groups']
    """
    sc.tl.rank_genes_groups(adata, groupby=groupby, method=method, **kwargs)
    adata.uns["pipeline_state"] = "Clustered"

    n_markers = adata.uns["rank_genes_groups"]["names"].shape[0] * adata.obs[groupby].nunique()
    print(f"Marker detection complete: ~{n_markers} top markers stored")

    return adata


def export_markers(adata: sc.AnnData, output_dir: str = ".") -> dict:
    """Export markers to CSV files.

    Parameters
    ----------
    adata : AnnData with rank_genes_groups
    output_dir : Directory for output files

    Returns
    -------
    dict with all, top10, top3 DataFrames
    """
    if "rank_genes_groups" not in adata.uns:
        print("No markers found. Run execute_marker_detection first.")
        return None

    # All markers
    markers = sc.get.rank_genes_groups_df(adata, group=None)
    markers.to_csv(f"{output_dir}/all_markers.csv", index=False)

    # Top 10 per cluster
    top10 = markers.groupby("group").head(10)
    top10.to_csv(f"{output_dir}/top10_markers.csv", index=False)

    # Top 3 per cluster
    top3 = markers.groupby("group").head(3)

    print(f"Markers exported to {output_dir}/all_markers.csv")

    return {"all": markers, "top10": top10, "top3": top3}


# ---------------------------------------------------------------------------
# PHASE 3: REPORT
# ---------------------------------------------------------------------------

def report_markers(adata: sc.AnnData) -> dict:
    """Report marker detection results."""
    if "rank_genes_groups" not in adata.uns:
        return {
            "step": "Marker Detection",
            "status": "FAIL",
            "n_markers": 0,
            "recommendation": "No markers found. Check clustering resolution or filtering thresholds.",
            "next_step": "Revisit Step 6: Clustering",
        }

    markers = sc.get.rank_genes_groups_df(adata, group=None)
    n_markers = len(markers)
    n_clusters = markers["group"].nunique()
    avg_per_cluster = n_markers / n_clusters if n_clusters > 0 else 0

    status = "CAUTION" if avg_per_cluster < 10 else "PASS"

    return {
        "step": "Marker Detection",
        "status": status,
        "n_markers": n_markers,
        "n_clusters": n_clusters,
        "avg_markers_per_cluster": round(avg_per_cluster, 1),
        "recommendation": (
            "Low marker count per cluster. Consider lower log fold-change threshold or check cluster quality."
            if status == "CAUTION"
            else "Good marker yield. Proceed to cell type annotation."
        ),
        "next_step": "Step 8: Cell Type Annotation",
    }


# ---------------------------------------------------------------------------
# Full step wrapper
# ---------------------------------------------------------------------------

def run_marker_step(adata: sc.AnnData, groupby: str = "leiden",
                    auto: bool = False, use_llm: bool = True,
                    prev_reports: dict = None, **kwargs) -> dict:
    """Complete marker detection step.

    Parameters
    ----------
    adata : AnnData [Clustered]
    groupby : Column to group by for marker detection
    auto : Skip proposal display
    use_llm : If True, generate LLM diagnostic card.
    prev_reports : Previous step reports for cross-step analysis.
    **kwargs : Passed to execute_marker_detection

    Returns
    -------
    dict with keys: obj, report, proposal, llm_report
    """
    expected_states = {"Clustered"}
    current_state = adata.uns.get("pipeline_state")
    if current_state not in expected_states:
        import warnings
        warnings.warn(
            f"Expected input state 'Clustered' for marker step, got '{current_state}'. "
            "Proceeding anyway, but results may be unexpected."
        )

    proposal = propose_marker_params(adata)

    # Evaluate phase: guardrail on cluster count
    evaluation = evaluate_marker_proposal(proposal, adata)
    if evaluation["verdict"] == "BLOCK":
        raise RuntimeError(evaluation["reason"])
    elif evaluation["verdict"] == "CAUTION":
        print(f"CAUTION: {evaluation['reason']}")

    if not auto:
        print("\n=== Marker Detection Proposal ===")
        print(f"Test: {proposal['recommendation']['method']}")
        print(f"Groups: {proposal['diagnostics']['n_clusters']} clusters")

    adata = execute_marker_detection(adata, groupby=groupby,
                                     method=proposal["recommendation"]["method"],
                                     **kwargs)
    report = report_markers(adata)

    # LLM enhancement
    llm_report = None
    if use_llm:
        llm_report = generate_llm_report("markers", adata, proposal, report, prev_reports)
        if not auto:
            print(llm_report)

    return {"obj": adata, "report": report, "proposal": proposal, "llm_report": llm_report}
