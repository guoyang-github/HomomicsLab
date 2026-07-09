import json

try:
    import resource
    # 8192 MB memory limit — single-cell H5AD files decompress to multiple
    # gigabytes in memory; 2 GB is too restrictive for real datasets.
    resource.setrlimit(resource.RLIMIT_AS, (8192 * 1024 * 1024, 8192 * 1024 * 1024))
    # 3600 seconds CPU time limit — analysis skills often run for minutes.
    resource.setrlimit(resource.RLIMIT_CPU, (3600, 3600))
    # 1 GB file size limit for output artifacts.
    resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024 * 1024, 1024 * 1024 * 1024))
except Exception:
    pass

# Inject inputs
__inputs__ = json.loads('{}')
locals().update(__inputs__)

# Run skill code
import sys
sys.path.insert(0, '/mnt/c/Users/guoyang/Desktop/TEST/HomomicsLab/skills/bio-single-cell-annotation-celltypist/scripts/python')

"""CellTypist annotation entrypoint for HomomicsLab.

Reads input parameters from ``__inputs__`` (injected by the skill runtime),
loads an AnnData object, runs CellTypist annotation, compares predictions with
an existing label column, and writes outputs to the workspace.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import scanpy as sc
from sklearn.metrics import accuracy_score, adjusted_rand_score, confusion_matrix

from core_analysis import run_celltypist_annotation
from utils import export_annotations


def _get_input(key: str, default: Any = None) -> Any:
    """Fetch a value from the injected __inputs__ dict."""
    inputs = globals().get("__inputs__", {})
    if isinstance(inputs, dict):
        return inputs.get(key, default)
    return default


def _resolve_file(path: str) -> Path:
    """Resolve a file path relative to the workspace data directory."""
    p = Path(path)
    if p.is_file():
        return p
    # Common fallback locations used by HomomicsLab
    candidates = [
        Path(os.getcwd()) / path,
        Path(os.getcwd()) / "data" / path,
        Path(os.getcwd()) / "data" / "raw" / "default" / path,
        Path(os.getcwd()).parent / "data" / path,
        Path(os.getcwd()).parent / "data" / "raw" / "default" / path,
    ]
    for c in candidates:
        if c.is_file():
            return c
    raise FileNotFoundError(f"Input file not found: {path}")


def _discover_h5ad() -> Optional[Path]:
    """Auto-discover a single .h5ad file in the project data directory."""
    search_roots = [
        Path(os.getcwd()) / "data" / "raw" / "default",
        Path(os.getcwd()).parent / "data" / "raw" / "default",
        Path(os.getcwd()) / "data",
        Path(os.getcwd()).parent / "data",
    ]
    candidates: List[Path] = []
    for root in search_roots:
        if root.is_dir():
            candidates.extend(root.rglob("*.h5ad"))
    if not candidates:
        return None
    # Prefer the largest file (most likely to be the main dataset)
    return max(candidates, key=lambda p: p.stat().st_size)


def main(skill_inputs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Run CellTypist annotation and comparison."""
    if skill_inputs is None:
        skill_inputs = globals().get("__inputs__", {})

    input_file = skill_inputs.get("input_file") or skill_inputs.get("input_path") or skill_inputs.get("h5ad")
    if not input_file:
        discovered = _discover_h5ad()
        if discovered is None:
            raise ValueError("Missing required input: input_file (path to .h5ad)")
        input_file = str(discovered)
        print(f"Auto-discovered input file: {input_file}")

    model = skill_inputs.get("model", "Immune_All_Low.pkl")
    label_col = skill_inputs.get("label_column", "all_celltype")
    output_prefix = skill_inputs.get("output_prefix", "celltypist")
    majority_voting = skill_inputs.get("majority_voting", True)
    mode = skill_inputs.get("mode", "best match")
    conf_threshold = float(skill_inputs.get("conf_threshold", 0.5))

    input_path = _resolve_file(str(input_file))
    output_dir = Path(os.getcwd())
    output_h5ad = output_dir / f"{output_prefix}_annotated.h5ad"
    output_csv = output_dir / f"{output_prefix}_annotations.csv"
    output_summary = output_dir / f"{output_prefix}_summary.csv"
    output_compare = output_dir / f"{output_prefix}_comparison.csv"

    print(f"Loading {input_path} ...")
    adata = sc.read_h5ad(str(input_path))
    print(f"AnnData: {adata.n_obs} cells x {adata.n_vars} genes")

    has_existing_labels = label_col in adata.obs.columns
    if has_existing_labels:
        existing = adata.obs[label_col].astype(str).replace("nan", "Unknown")
        print(f"Existing labels '{label_col}': {existing.nunique()} unique")
    else:
        print(f"Warning: label column '{label_col}' not found; skipping comparison")

    # CellTypist requires log1p-normalized expression to 10,000 counts/cell.
    # Normalize the data to meet this expectation.
    print("Normalizing to 10,000 counts/cell and log1p-transforming for CellTypist ...")
    sc.pp.normalize_total(adata, target_sum=1e4)
    sc.pp.log1p(adata)

    print(f"Running CellTypist with model {model} ...")
    adata = run_celltypist_annotation(
        adata,
        model=model,
        majority_voting=majority_voting,
        mode=mode,
        prefix="celltypist_",
    )

    # Confidence filtering
    pred_col = "celltypist_label"
    conf_col = "celltypist_conf_score"
    if conf_col in adata.obs.columns:
        adata.obs["celltypist_label_filtered"] = np.where(
            adata.obs[conf_col].astype(float) >= conf_threshold,
            adata.obs[pred_col].astype(str),
            "Unassigned",
        )
    else:
        adata.obs["celltypist_label_filtered"] = adata.obs[pred_col].astype(str)

    # Comparison with existing labels
    comparison = {}
    if has_existing_labels:
        existing = adata.obs[label_col].astype(str)
        predicted = adata.obs[pred_col].astype(str)
        valid_mask = (existing != "nan") & (existing != "Unknown") & (existing != "")

        if valid_mask.sum() > 0:
            comparison["accuracy"] = float(accuracy_score(existing[valid_mask], predicted[valid_mask]))
            comparison["adjusted_rand_index"] = float(adjusted_rand_score(existing[valid_mask], predicted[valid_mask]))

            # Per-label agreement
            labels = sorted(existing[valid_mask].unique())
            per_label = {}
            for lbl in labels:
                mask = valid_mask & (existing == lbl)
                if mask.sum() > 0:
                    top_pred = predicted[mask].value_counts().index[0]
                    agreement = (predicted[mask] == lbl).mean()
                    per_label[lbl] = {
                        "count": int(mask.sum()),
                        "top_predicted": str(top_pred),
                        "agreement_with_label": float(agreement),
                    }
            comparison["per_label"] = per_label

            # Confusion matrix (top labels only)
            top_existing = existing[valid_mask].value_counts().head(15).index.tolist()
            top_predicted = predicted[valid_mask].value_counts().head(15).index.tolist()
            sub_mask = valid_mask & existing.isin(top_existing) & predicted.isin(top_predicted)
            if sub_mask.sum() > 0:
                cm = confusion_matrix(
                    existing[sub_mask],
                    predicted[sub_mask],
                    labels=top_existing,
                )
                comparison["confusion_matrix"] = {
                    "labels": top_existing,
                    "matrix": cm.tolist(),
                }

        # Save comparison CSV
        compare_df = pd.DataFrame({
            "barcode": adata.obs_names,
            label_col: adata.obs[label_col].astype(str),
            "celltypist_predicted": adata.obs[pred_col].astype(str),
            "celltypist_majority_voting": adata.obs.get("celltypist_majority_voting", pd.Series(index=adata.obs_names, dtype=str)),
            "celltypist_conf_score": adata.obs.get(conf_col, pd.Series(index=adata.obs_names, dtype=float)),
            "celltypist_label_filtered": adata.obs["celltypist_label_filtered"].astype(str),
        })
        compare_df.to_csv(output_compare, index=False)
        comparison["comparison_csv"] = str(output_compare)

    # Save outputs
    print(f"Writing annotated H5AD to {output_h5ad} ...")
    # Allow writing pandas nullable string arrays (common in imported datasets).
    import anndata
    anndata.settings.allow_write_nullable_strings = True
    adata.write_h5ad(str(output_h5ad))

    export_annotations(adata, output_csv, label_col=pred_col, conf_col=conf_col)

    # Summary counts
    summary = adata.obs[pred_col].value_counts().reset_index()
    summary.columns = ["cell_type", "count"]
    summary.to_csv(output_summary, index=False)

    result = {
        "success": True,
        "input_file": str(input_path),
        "output_h5ad": str(output_h5ad),
        "output_csv": str(output_csv),
        "output_summary": str(output_summary),
        "model": model,
        "cells": int(adata.n_obs),
        "genes": int(adata.n_vars),
        "predicted_labels": adata.obs[pred_col].value_counts().to_dict(),
        "comparison": comparison,
    }

    print("CellTypist annotation complete.")
    return result


if __name__ == "__main__":
    result = main()
    print(json.dumps(result, indent=2, default=str))


# Skill entrypoint wrapper
if 'main' in dir() and callable(main):
    result = main(__inputs__)


# Serialize result
if 'result' not in locals():
    result = {}

with open('__skill_result__.json', 'w') as f:
    json.dump(result, f)
