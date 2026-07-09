#!/usr/bin/env python3
"""
CellTypist annotation demonstration.
Generates a small synthetic PBMC-like dataset with raw counts using genes that
overlap the Immune_All_Low model, then runs the full CellTypist pipeline.

Outputs:
    - synthetic_pbmc_annotated.h5ad
    - celltypist_annotation_summary.csv
    - celltypist_annotations.csv
"""

import os
import warnings
import numpy as np
import pandas as pd
import scanpy as sc
import celltypist
from scipy import sparse

warnings.filterwarnings("ignore")

np.random.seed(42)

# ---------------------------------------------------------------------------
# 1. Configuration
# ---------------------------------------------------------------------------
OUTPUT_H5AD = "synthetic_pbmc_annotated.h5ad"
OUTPUT_SUMMARY = "celltypist_annotation_summary.csv"
OUTPUT_ANNOTATIONS = "celltypist_annotations.csv"
MODEL = "Immune_All_Low.pkl"
CONFIDENCE_THRESHOLD = 0.5

N_CELLS = 500
N_GENES = 2000

# ---------------------------------------------------------------------------
# 2. Load model and choose marker genes
# ---------------------------------------------------------------------------
print(f"Loading CellTypist model: {MODEL}")
model = celltypist.models.Model.load(MODEL)
print(f"Model features: {len(model.features)}, cell types: {len(model.cell_types)}")

# Select a subset of model features to simulate
rng = np.random.default_rng(42)
selected_genes = rng.choice(model.features, size=N_GENES, replace=False)

# Define simple marker panels for a handful of immune cell types
markers = {
    "B cells": ["CD19", "MS4A1", "CD79A", "CD79B"],
    "CD4 T cells": ["CD3D", "CD4", "IL7R"],
    "CD8 T cells": ["CD3D", "CD8A", "CD8B", "GZMA"],
    "NK cells": ["NKG7", "GNLY", "KLRD1", "NCAM1"],
    "Monocytes": ["LYZ", "CD14", "S100A9", "S100A8"],
}

# Ensure all markers are in selected_genes
for ct, genes in markers.items():
    for g in genes:
        if g not in selected_genes:
            # swap in a random gene
            idx = rng.integers(0, len(selected_genes))
            selected_genes[idx] = g

# ---------------------------------------------------------------------------
# 3. Generate synthetic raw counts
# ---------------------------------------------------------------------------
print(f"Generating synthetic raw count matrix: {N_CELLS} cells x {N_GENES} genes")

# Base counts: negative binomial-ish
base_counts = rng.poisson(0.5, size=(N_CELLS, N_GENES))

labels = []
cell_types = list(markers.keys())
for i in range(N_CELLS):
    ct = cell_types[i % len(cell_types)]
    labels.append(ct)
    for g in markers[ct]:
        j = np.where(selected_genes == g)[0][0]
        # add expression for marker genes
        base_counts[i, j] += rng.poisson(5 + rng.exponential(5))

adata = sc.AnnData(
    X=sparse.csr_matrix(base_counts.astype(np.float32)),
    obs=pd.DataFrame(index=[f"cell_{i}" for i in range(N_CELLS)]),
    var=pd.DataFrame(index=selected_genes),
)
adata.obs["true_label"] = labels

print(f"AnnData shape: {adata.shape}")
print(f"Max raw count: {adata.X.max():.0f}")

# ---------------------------------------------------------------------------
# 4. Normalize for CellTypist
# ---------------------------------------------------------------------------
print("Normalizing total counts and log-transforming...")
sc.pp.normalize_total(adata, target_sum=1e4)
sc.pp.log1p(adata)

# ---------------------------------------------------------------------------
# 5. Cluster for majority voting
# ---------------------------------------------------------------------------
print("Computing HVGs, PCA, neighbors, and Leiden clusters...")
sc.pp.highly_variable_genes(adata, n_top_genes=2000)
sc.pp.pca(adata, use_highly_variable=True)
sc.pp.neighbors(adata)
sc.tl.leiden(adata, resolution=0.5)

# ---------------------------------------------------------------------------
# 6. Download model and run CellTypist
# ---------------------------------------------------------------------------
print(f"Downloading/using CellTypist model: {MODEL}")
celltypist.models.download_models(model=MODEL)

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
print("\n=== CellTypist annotation summary (filtered labels) ===")
summary = adata.obs.groupby("celltypist_label_filtered").agg(
    n_cells=("celltypist_label_filtered", "size"),
    proportion=("celltypist_label_filtered", lambda x: x.size / len(adata.obs)),
    mean_confidence=("celltypist_conf_score", "mean"),
    median_confidence=("celltypist_conf_score", "median"),
).sort_values("n_cells", ascending=False)
print(summary)

summary.to_csv(OUTPUT_SUMMARY)
print(f"Saved summary to {OUTPUT_SUMMARY}")

annotations = adata.obs[[
    "celltypist_predicted_labels",
    "celltypist_majority_voting",
    "celltypist_conf_score",
    "celltypist_label",
    "celltypist_label_filtered",
    "true_label",
]].copy()
annotations.insert(0, "cell_barcode", adata.obs_names)
annotations.to_csv(OUTPUT_ANNOTATIONS)
print(f"Saved per-cell annotations to {OUTPUT_ANNOTATIONS}")

adata.write(OUTPUT_H5AD)
print(f"Saved annotated AnnData to {OUTPUT_H5AD}")
print("Done.")
