"""Minimal Example: CellTypist Automated Cell Type Annotation
==============================================================

Basic workflow for cell type annotation using CellTypist pre-trained models.

Reference: Domínguez Conde et al., Science 2022
"""

import numpy as np
import pandas as pd
import scanpy as sc
import celltypist

print("=" * 60)
print("CellTypist Minimal Example")
print("=" * 60)

# -----------------------------------------------------------------------------
# Step 1: Create or load test data
# -----------------------------------------------------------------------------
print("\n[Step 1] Preparing data...")

np.random.seed(42)
adata = sc.AnnData(
    X=np.random.lognormal(3, 1, (500, 1000)),
    obs=pd.DataFrame(index=[f"cell_{i}" for i in range(500)]),
    var=pd.DataFrame(index=[f"GENE_{i}" for i in range(1000)])
)

# CellTypist requires log-normalized data
sc.pp.normalize_total(adata, target_sum=1e4)
sc.pp.log1p(adata)

print(f"Data: {adata.n_obs} cells x {adata.n_vars} genes")

# -----------------------------------------------------------------------------
# Step 2: Validate input
# -----------------------------------------------------------------------------
print("\n[Step 2] Validating input...")

import sys
sys.path.append('../scripts/python')
from core_analysis import validate_celltypist_input

validation = validate_celltypist_input(adata)
if validation['warnings']:
    for warning in validation['warnings']:
        print(f"  Warning: {warning}")
else:
    print("  Input looks good.")

# -----------------------------------------------------------------------------
# Step 3: Run CellTypist annotation
# -----------------------------------------------------------------------------
print("\n[Step 3] Running CellTypist annotation...")

# Download model if needed (cached after first run)
celltypist.models.download_models(model='Immune_All_Low.pkl')

# Run annotation
# NOTE: This example uses synthetic data with random gene names, so the real
# annotation will fail with "No features overlap". In practice, use real data
# with gene symbols matching the model.
try:
    predictions = celltypist.annotate(
        adata,
        model='Immune_All_Low.pkl',
        mode='best match',
        majority_voting=False
    )
    adata = predictions.to_adata(prefix='celltypist_')
    print(f"  Annotated {predictions.cell_count} cells")
    print(f"  Top prediction: {predictions.predicted_labels.iloc[0, 0]}")
except Exception as e:
    print(f"  (Expected error with random gene names: {e})")
    # Add mock predictions for demonstration of downstream steps
    print("  Adding mock predictions for demonstration...")
    adata.obs['celltypist_predicted_labels'] = np.random.choice(
        ['T cell', 'B cell', 'Monocyte', 'NK cell', 'DC'],
        adata.n_obs
    )
    adata.obs['celltypist_conf_score'] = np.random.beta(7, 2, adata.n_obs)
    adata.obs['celltypist_label'] = adata.obs['celltypist_predicted_labels']

# -----------------------------------------------------------------------------
# Step 4: Filter by confidence
# -----------------------------------------------------------------------------
print("\n[Step 4] Filtering by confidence...")

from core_analysis import filter_by_confidence

adata = filter_by_confidence(adata, threshold=0.5)

# -----------------------------------------------------------------------------
# Step 5: Summarize results
# -----------------------------------------------------------------------------
print("\n[Step 5] Summarizing results...")

from utils import summarize_annotations

summary = summarize_annotations(adata)
print("\nCell Type Summary:")
print(summary.to_string())

# -----------------------------------------------------------------------------
# Step 6: Export
# -----------------------------------------------------------------------------
print("\n[Step 6] Exporting...")

from utils import export_annotations

export_annotations(adata, output_file='minimal_annotation_results.csv')

print("\n" + "=" * 60)
print("Minimal example complete!")
print("=" * 60)
