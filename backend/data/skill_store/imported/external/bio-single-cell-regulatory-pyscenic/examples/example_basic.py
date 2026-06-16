#!/usr/bin/env python3
"""
pySCENIC Basic Analysis Example
Demonstrates complete pySCENIC pipeline with database management.
"""

import scanpy as sc
import pandas as pd
import numpy as np
from pathlib import Path

# Import pySCENIC analysis module
import sys
sys.path.insert(0, '../scripts/python')
from pyscenic_analysis import (
    check_database,
    download_databases,
    run_pyscenic_pipeline,
    add_aucell_to_adata,
    get_top_regulons_per_celltype,
    export_regulons_to_gmt
)

# ============================================================================
# Step 1: Check and Download Databases
# ============================================================================

print("=" * 60)
print("Step 1: Database Setup")
print("=" * 60)

# Check database status
status = check_database(organism="human", db_type="10kb", motif_version="v10")
print(f"\nDatabase cached: {status['database']}")
print(f"Motifs cached: {status['motif_annotations']}")
print(f"TF list cached: {status['tf_list']}")

# Download if needed
if not all([status['database'], status['motif_annotations'], status['tf_list']]):
    print("\nDownloading databases...")
    print("Note: This may take several minutes and requires ~1GB disk space.")
    db_paths = download_databases(
        organism="human",
        db_type="10kb",
        motif_version="v10"
    )
    print(f"\nDatabases downloaded to: {db_paths}")
else:
    print("\nAll databases are ready!")

# ============================================================================
# Step 2: Load Data
# ============================================================================

print("\n" + "=" * 60)
print("Step 2: Load Expression Data")
print("=" * 60)

# For demonstration, create mock scRNA-seq data
np.random.seed(42)
n_cells = 200
n_genes = 1000

counts = np.random.poisson(3, size=(n_cells, n_genes))

adata = sc.AnnData(
    X=counts,
    obs=pd.DataFrame(index=[f"cell_{i}" for i in range(n_cells)]),
    var=pd.DataFrame(index=[f"gene_{i}" for i in range(n_genes)])
)

# Add cell type annotations
adata.obs['cell_type'] = np.random.choice(
    ['T_cell', 'B_cell', 'Monocyte', 'NK_cell'],
    n_cells
)

print(f"Loaded {adata.n_obs} cells and {adata.n_vars} genes")

# ============================================================================
# Step 3: Run pySCENIC Pipeline
# ============================================================================

print("\n" + "=" * 60)
print("Step 3: Run pySCENIC Pipeline")
print("=" * 60)

# Run complete pipeline
adjacencies, regulons, auc_matrix = run_pyscenic_pipeline(
    adata=adata,
    organism="human",
    db_type="10kb",
    motif_version="v10",
    grn_method="grnboost2",
    num_workers=4,
    seed=42,
    download_if_missing=True,
    verbose=True
)

print(f"\nPipeline complete!")
print(f"  - Adjacencies: {len(adjacencies)} TF-target relationships")
print(f"  - Regulons: {len(regulons)} regulons identified")
print(f"  - AUC matrix: {auc_matrix.shape}")

# ============================================================================
# Step 4: Export Results
# ============================================================================

print("\n" + "=" * 60)
print("Step 4: Export Results")
print("=" * 60)

# Add AUCell scores to AnnData
adata = add_aucell_to_adata(adata, auc_matrix, assay_name="X_aucell")

# Get top regulons per cell type
top_regulons = get_top_regulons_per_celltype(
    adata,
    celltype_col="cell_type",
    auc_key="X_aucell",
    top_n=5
)

print("\nTop regulons per cell type:")
print(top_regulons)

# Export to GMT format
export_regulons_to_gmt(
    regulons=regulons,
    output_file=Path("regulons.gmt"),
    min_genes=5
)

print("\nExport complete!")
