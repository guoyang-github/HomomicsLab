#!/usr/bin/env python3
"""
CellTypist single-cell annotation pipeline.

Run this in an environment where celltypist and scanpy are installed:
    pip install celltypist scanpy anndata scikit-learn scipy

Usage:
    python run_celltypist_annotation.py

Inputs:
    - mock_pbmc_processed.h5ad (or edit INPUT_PATH)

Outputs:
    - annotated_data_celltypist.h5ad
    - celltypist_annotation_summary.csv
    - celltypist_annotations.csv
"""

import os
import warnings
import scanpy as sc
import celltypist

# ---------------------------------------------------------------------------
# 1. Configuration
# ---------------------------------------------------------------------------
INPUT_PATH = "mock_pbmc_processed.h5ad"
OUTPUT_H5AD = "annotated_data_celltypist.h5ad"
OUTPUT_SUMMARY = "celltypist_annotation_summary.csv"
OUTPUT_ANNOTATIONS = "celltypist_annotations.csv"
MODEL = "Immune_All_Low.pkl"  # broad human immune cell model
CONFIDENCE_THRESHOLD = 0.5

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# 2. Load data
# ---------------------------------------------------------------------------
print(f"Loading {INPUT_PATH} ...")
adata = sc.read_h5ad(INPUT_PATH)
print(f"AnnData shape: {adata.shape}")
print(f"Obs columns: {list(adata.obs.columns)}")
print(f"First var names: {list(adata.var_names[:10])}")

# ---------------------------------------------------------------------------
# 3. Prepare data for CellTypist
#    CellTypist requires log-normalized gene-symbol expression data.
# ---------------------------------------------------------------------------
# Detect if data looks like raw counts (max value > 30) and normalize
x_sample = adata.X[:1000]
try:
    x_max = float(x_sample.max())
except TypeError:
    x_max = float(x_sample.toarray().max())

if x_max > 30:
    print("Data looks like raw counts; applying normalization...")
    sc.pp.normalize_total(adata, target_sum=1e4)
    sc.pp.log1p(adata)
else:
    print("Data appears normalized/log-transformed; skipping normalization.")

# ---------------------------------------------------------------------------
# 4. Ensure clustering exists for majority voting
# ---------------------------------------------------------------------------
if "leiden" not in adata.obs.columns:
    print("Computing HVGs, PCA, neighbors, and Leiden clusters...")
    sc.pp.highly_variable_genes(adata, n_top_genes=2000)
    sc.pp.pca(adata, use_highly_variable=True)
    sc.pp.neighbors(adata)
    sc.tl.leiden(adata, resolution=0.5)
else:
    print(f"Using existing 'leiden' clusters ({adata.obs['leiden'].nunique()} clusters).")

# ---------------------------------------------------------------------------
# 5. Download model if not cached
# ---------------------------------------------------------------------------
print(f"Downloading/using CellTypist model: {MODEL}")
celltypist.models.download_models(model=MODEL)

# ---------------------------------------------------------------------------
# 6. Run CellTypist annotation
# ---------------------------------------------------------------------------
print("Running CellTypist annotation...")
predictions = celltypist.annotate(
    adata,
    model=MODEL,
    mode="best match",
    majority_voting=True,
    over_clustering="leiden",
    p_thres=0.5,
    use_GPU=False,
    min_prop=0,
)

# ---------------------------------------------------------------------------
# 7. Add predictions to AnnData
# ---------------------------------------------------------------------------
adata = predictions.to_adata(prefix="celltypist_")

# Convenience label column: majority_voting if available, else predicted labels
adata.obs["celltypist_label"] = adata.obs["celltypist_majority_voting"].fillna(
    adata.obs["celltypist_predicted_labels"]
)

# ---------------------------------------------------------------------------
# 8. Filter low-confidence predictions
# ---------------------------------------------------------------------------
print(f"Filtering predictions with confidence < {CONFIDENCE_THRESHOLD}...")
adata.obs["celltypist_label_filtered"] = adata.obs["celltypist_label"].where(
    adata.obs["celltypist_conf_score"] >= CONFIDENCE_THRESHOLD,
    "Unassigned",
)

# ---------------------------------------------------------------------------
# 9. Summarize and export
# ---------------------------------------------------------------------------
print("\n=== CellTypist annotation summary (majority voting) ===")
summary = adata.obs.groupby("celltypist_label_filtered").agg(
    n_cells=("celltypist_label_filtered", "size"),
    proportion=("celltypist_label_filtered", lambda x: x.size / len(adata.obs)),
    mean_confidence=("celltypist_conf_score", "mean"),
    median_confidence=("celltypist_conf_score", "median"),
).sort_values("n_cells", ascending=False)
print(summary)

summary.to_csv(OUTPUT_SUMMARY)
print(f"Saved summary to {OUTPUT_SUMMARY}")

# Export per-cell annotations
annotations = adata.obs[[
    "celltypist_predicted_labels",
    "celltypist_majority_voting",
    "celltypist_conf_score",
    "celltypist_label",
    "celltypist_label_filtered",
]].copy()
annotations.insert(0, "cell_barcode", adata.obs_names)
annotations.to_csv(OUTPUT_ANNOTATIONS)
print(f"Saved per-cell annotations to {OUTPUT_ANNOTATIONS}")

# ---------------------------------------------------------------------------
# 10. Save annotated AnnData
# ---------------------------------------------------------------------------
adata.write(OUTPUT_H5AD)
print(f"Saved annotated AnnData to {OUTPUT_H5AD}")
print("Done.")
