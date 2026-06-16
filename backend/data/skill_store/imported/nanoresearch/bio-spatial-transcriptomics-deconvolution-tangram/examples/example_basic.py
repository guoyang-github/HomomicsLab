"""
Tangram Example Workflow

This example demonstrates the complete Tangram workflow for spatial
transcriptomics deconvolution using single-cell RNA-seq reference.

Workflow:
1. Data preparation and preprocessing
2. Cell mapping (clusters mode - faster)
3. Cell mapping (cells mode - higher resolution)
4. Gene imputation
5. Cell type projection and visualization
6. Cross-validation for quality assessment
7. Constrained mode for cell counting (optional)

Author: Yang Guo
Date: 2026-04-03
"""

import numpy as np
import pandas as pd
import scanpy as sc
import matplotlib.pyplot as plt

# Import Tangram wrapper functions
import sys
sys.path.insert(0, '../scripts/python')
from core_analysis import (
    prepare_data,
    map_cells_to_space,
    project_genes,
    project_cell_annotations,
    compare_spatial_geneexp,
    cross_val,
    eval_metric,
    extract_deconvolution_results,
    export_results,
)
from visualization import (
    plot_training_scores,
    plot_cell_annotation_sc,
    plot_genes_sc,
    plot_annotation_comparison,
    plot_auc,
)

# =============================================================================
# Configuration
# =============================================================================

# File paths (modify these to your data locations)
SC_DATA_PATH = 'path/to/single_cell_data.h5ad'
SP_DATA_PATH = 'path/to/spatial_data.h5ad'
OUTPUT_DIR = './tangram_output'

# Analysis parameters
CELL_TYPE_KEY = 'cell_type'  # Column in adata_sc.obs with cell type labels
DEVICE = 'cuda:0'  # Use 'cpu' if no GPU available
NUM_EPOCHS = 1000
RANDOM_STATE = 42

# Gene selection (optional)
# Use marker genes if available, otherwise Tangram will use shared genes
MARKER_GENES = None  # ['Gene1', 'Gene2', ...]


def load_and_inspect_data():
    """
    Load and inspect single-cell and spatial data.

    Returns:
        tuple: (adata_sc, adata_sp)
    """
    print("=" * 60)
    print("Step 1: Loading Data")
    print("=" * 60)

    # Load single-cell data
    adata_sc = sc.read_h5ad(SC_DATA_PATH)
    print(f"Single-cell data: {adata_sc.n_obs} cells x {adata_sc.n_vars} genes")
    print(f"Cell types: {adata_sc.obs[CELL_TYPE_KEY].nunique()}")
    print(f"Cell type distribution:")
    print(adata_sc.obs[CELL_TYPE_KEY].value_counts())

    # Load spatial data
    adata_sp = sc.read_h5ad(SP_DATA_PATH)
    print(f"\nSpatial data: {adata_sp.n_obs} spots x {adata_sp.n_vars} genes")
    print(f"Spatial coordinates present: {'spatial' in adata_sp.obsm}")

    return adata_sc, adata_sp


def run_data_preparation(adata_sc, adata_sp):
    """
    Prepare data for Tangram mapping.

    Args:
        adata_sc: Single-cell AnnData
        adata_sp: Spatial AnnData

    Returns:
        tuple: (adata_sc_prep, adata_sp_prep)
    """
    print("\n" + "=" * 60)
    print("Step 2: Data Preparation")
    print("=" * 60)

    # Preprocess data with Tangram
    adata_sc_prep, adata_sp_prep = prepare_data(
        adata_sc=adata_sc,
        adata_sp=adata_sp,
        genes=MARKER_GENES,
        gene_to_lowercase=True,
        copy=True,
    )

    print(f"\nTraining genes: {len(adata_sc_prep.uns['training_genes'])}")
    print(f"Overlap genes: {len(adata_sc_prep.uns['overlap_genes'])}")

    return adata_sc_prep, adata_sp_prep


def run_clusters_mode(adata_sc_prep, adata_sp_prep):
    """
    Run Tangram in clusters mode (fast, good for initial exploration).

    Args:
        adata_sc_prep: Prepared single-cell data
        adata_sp_prep: Prepared spatial data

    Returns:
        AnnData: Mapping result
    """
    print("\n" + "=" * 60)
    print("Step 3: Cell Mapping (Clusters Mode)")
    print("=" * 60)

    # Map cells to space in clusters mode
    adata_map = map_cells_to_space(
        adata_sc=adata_sc_prep,
        adata_sp=adata_sp_prep,
        mode='clusters',
        cluster_label=CELL_TYPE_KEY,
        density_prior='rna_count_based',
        num_epochs=NUM_EPOCHS,
        device=DEVICE,
        random_state=RANDOM_STATE,
        verbose=True,
        # Loss function parameters
        lambda_g1=1.0,
        lambda_r=0.0,
    )

    print("\nMapping complete!")
    print(f"Mapping matrix shape: {adata_map.X.shape}")

    # Check training scores
    df_scores = adata_map.uns['train_genes_df']
    print(f"\nTraining scores summary:")
    print(f"  Mean: {df_scores['train_score'].mean():.3f}")
    print(f"  Median: {df_scores['train_score'].median():.3f}")
    print(f"  Min: {df_scores['train_score'].min():.3f}")
    print(f"  Max: {df_scores['train_score'].max():.3f}")

    return adata_map


def run_cells_mode(adata_sc_prep, adata_sp_prep):
    """
    Run Tangram in cells mode (higher resolution, slower).

    Args:
        adata_sc_prep: Prepared single-cell data
        adata_sp_prep: Prepared spatial data

    Returns:
        AnnData: Mapping result
    """
    print("\n" + "=" * 60)
    print("Step 4: Cell Mapping (Cells Mode)")
    print("=" * 60)

    # Map cells to space in cells mode
    adata_map_cells = map_cells_to_space(
        adata_sc=adata_sc_prep,
        adata_sp=adata_sp_prep,
        mode='cells',
        density_prior='rna_count_based',
        num_epochs=NUM_EPOCHS,
        device=DEVICE,
        random_state=RANDOM_STATE,
        verbose=True,
        # Add entropy regularizer for sharper mappings
        lambda_r=0.5,
    )

    print("\nCells mode mapping complete!")
    print(f"Mapping matrix shape: {adata_map_cells.X.shape}")

    return adata_map_cells


def run_gene_imputation(adata_map, adata_sc_prep, adata_sp_prep):
    """
    Impute gene expression from scRNA-seq to spatial data.

    Args:
        adata_map: Mapping result
        adata_sc_prep: Prepared single-cell data
        adata_sp_prep: Prepared spatial data

    Returns:
        AnnData: Spatial data with imputed genes
    """
    print("\n" + "=" * 60)
    print("Step 5: Gene Imputation")
    print("=" * 60)

    # Project genes using the mapping matrix
    adata_ge = project_genes(
        adata_map=adata_map,
        adata_sc=adata_sc_prep,
        cluster_label=CELL_TYPE_KEY if adata_map.n_obs < adata_sc_prep.n_obs else None,
        scale=True,
    )

    print(f"Projected {adata_ge.n_vars} genes to spatial data")
    print(f"Training genes: {adata_ge.var['is_training'].sum()}")

    # Compare projected vs measured expression
    df_compare = compare_spatial_geneexp(
        adata_ge=adata_ge,
        adata_sp=adata_sp_prep,
        adata_sc=adata_sc_prep,
    )

    print("\nGene prediction scores:")
    print(f"  Training genes mean score: {df_compare[df_compare['is_training']]['score'].mean():.3f}")
    print(f"  All genes mean score: {df_compare['score'].mean():.3f}")

    return adata_ge, df_compare


def run_cell_type_projection(adata_map, adata_sp_prep):
    """
    Project cell type annotations to spatial data.

    Args:
        adata_map: Mapping result
        adata_sp_prep: Prepared spatial data

    Returns:
        pd.DataFrame: Cell type proportions
    """
    print("\n" + "=" * 60)
    print("Step 6: Cell Type Projection")
    print("=" * 60)

    # Project cell type annotations
    project_cell_annotations(
        adata_map=adata_map,
        adata_sp=adata_sp_prep,
        annotation=CELL_TYPE_KEY,
    )

    # Extract proportions
    props = extract_deconvolution_results(
        adata_sp=adata_sp_prep,
        annotation_key='tangram_ct_pred',
        normalize=True,
    )

    print(f"Cell type proportions shape: {props.shape}")
    print("\nMean proportions per spot:")
    print(props.mean().sort_values(ascending=False))

    return props


def run_cross_validation(adata_sc_prep, adata_sp_prep):
    """
    Run cross-validation to assess gene prediction accuracy.

    Args:
        adata_sc_prep: Prepared single-cell data
        adata_sp_prep: Prepared spatial data

    Returns:
        tuple: (cv_dict, adata_ge_cv, df_test)
    """
    print("\n" + "=" * 60)
    print("Step 7: Cross-Validation")
    print("=" * 60)

    # Run leave-one-out cross-validation
    cv_dict, adata_ge_cv, df_test = cross_val(
        adata_sc=adata_sc_prep,
        adata_sp=adata_sp_prep,
        mode='clusters',
        cluster_label=CELL_TYPE_KEY,
        num_epochs=500,  # Fewer epochs for CV
        device=DEVICE,
        cv_mode='loo',
        return_gene_pred=True,
        verbose=True,
    )

    print("\nCross-validation results:")
    print(f"  Average test score: {cv_dict['avg_test_score']:.3f}")
    print(f"  Average train score: {cv_dict['avg_train_score']:.3f}")

    return cv_dict, adata_ge_cv, df_test


def create_visualizations(adata_map, adata_sp_prep, adata_ge, df_compare):
    """
    Create diagnostic and result visualizations.

    Args:
        adata_map: Mapping result
        adata_sp_prep: Spatial data with projections
        adata_ge: Projected gene expression
        df_compare: Gene comparison results
    """
    print("\n" + "=" * 60)
    print("Step 8: Visualization")
    print("=" * 60)

    # 1. Training scores plot
    print("\n1. Creating training scores plot...")
    fig = plot_training_scores(adata_map)
    fig.savefig(f'{OUTPUT_DIR}/training_scores.png', dpi=300, bbox_inches='tight')
    plt.close()

    # 2. Cell type projections
    print("2. Creating cell type projection plots...")
    cell_types = adata_sp_prep.obsm['tangram_ct_pred'].columns.tolist()[:6]  # First 6
    fig = plot_annotation_comparison(
        adata_sp=adata_sp_prep,
        cell_types=cell_types,
        n_cols=3,
        cmap='viridis',
    )
    fig.savefig(f'{OUTPUT_DIR}/cell_type_projections.png', dpi=300, bbox_inches='tight')
    plt.close()

    # 3. Gene comparison
    print("3. Creating gene comparison plots...")
    # Select top and bottom performing genes
    top_genes = df_compare.sort_values('score', ascending=False).head(3).index.tolist()
    bottom_genes = df_compare.sort_values('score', ascending=True).head(3).index.tolist()
    genes_to_plot = top_genes[:2] + bottom_genes[:2]

    if genes_to_plot:
        fig = plot_genes_sc(
            genes=genes_to_plot,
            adata_measured=adata_sp_prep,
            adata_predicted=adata_ge,
            cmap='inferno',
        )
        fig.savefig(f'{OUTPUT_DIR}/gene_comparison.png', dpi=300, bbox_inches='tight')
        plt.close()

    print(f"\nVisualizations saved to {OUTPUT_DIR}/")


def main():
    """
    Main workflow execution.
    """
    import os
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("""
    =========================================
    Tangram Spatial Transcriptomics Deconvolution
    =========================================
    This workflow demonstrates:
    - Data preparation
    - Cell mapping (clusters and cells modes)
    - Gene imputation
    - Cell type projection
    - Cross-validation
    - Visualization
    """)

    # Step 1: Load data
    adata_sc, adata_sp = load_and_inspect_data()

    # Step 2: Prepare data
    adata_sc_prep, adata_sp_prep = run_data_preparation(adata_sc, adata_sp)

    # Step 3: Run clusters mode (fast)
    adata_map = run_clusters_mode(adata_sc_prep, adata_sp_prep)

    # Step 4: Run cells mode (optional - higher resolution but slower)
    # adata_map_cells = run_cells_mode(adata_sc_prep, adata_sp_prep)

    # Step 5: Gene imputation
    adata_ge, df_compare = run_gene_imputation(adata_map, adata_sc_prep, adata_sp_prep)

    # Step 6: Cell type projection
    props = run_cell_type_projection(adata_map, adata_sp_prep)

    # Step 7: Cross-validation (optional but recommended)
    cv_dict, adata_ge_cv, df_test = run_cross_validation(adata_sc_prep, adata_sp_prep)

    # Step 8: Visualizations
    create_visualizations(adata_map, adata_sp_prep, adata_ge, df_compare)

    # Step 9: Export results
    print("\n" + "=" * 60)
    print("Step 9: Exporting Results")
    print("=" * 60)
    export_results(
        adata_map=adata_map,
        adata_sp=adata_sp_prep,
        output_dir=OUTPUT_DIR,
        annotation_key=CELL_TYPE_KEY,
        prefix='tangram',
    )

    print("\n" + "=" * 60)
    print("Workflow Complete!")
    print("=" * 60)
    print(f"Results saved to: {OUTPUT_DIR}/")


if __name__ == '__main__':
    main()
