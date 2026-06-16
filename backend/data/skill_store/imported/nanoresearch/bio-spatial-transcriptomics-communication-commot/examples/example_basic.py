"""
Basic COMMOT Spatial Communication Analysis Example

This example demonstrates the complete workflow for analyzing cell-cell
communication in spatial transcriptomics data using COMMOT.

Steps:
1. Load and prepare spatial data
2. Load ligand-receptor database
3. Run COMMOT spatial communication analysis
4. Visualize communication patterns
5. Analyze cluster-level communication
6. Export results

Author: Yang Guo
Date: 2026-04-03
"""

import numpy as np
import pandas as pd
import scanpy as sc
import matplotlib.pyplot as plt

# Import COMMOT wrapper functions
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts' / 'python'))

from core_analysis import (
    prepare_data,
    check_spatial_units,
    get_lr_database,
    filter_lr_database,
    create_custom_lr_database,
    run_commot,
    run_commot_database,
    infer_communication_direction,
    cluster_communication,
    get_top_lr_pairs,
    export_results,
)

from visualization import (
    plot_communication_strength,
    plot_communication_direction,
    plot_lr_expression,
    plot_cluster_communication_network,
    plot_cluster_communication_dotplot,
    plot_top_lr_pairs,
    plot_communication_heatmap,
    plot_multiple_lr_pairs,
)


# ============================================================================
# PART 1: Load Sample Data
# ============================================================================

print("=" * 70)
print("PART 1: Loading Spatial Data")
print("=" * 70)

# Option 1: Use Visium sample data from scanpy
try:
    adata = sc.datasets.visium(
        filename='V1_Mouse_Brain_Sagittal_Posterior'
    )
    adata.var_names_make_unique()
    print(f"Loaded Visium mouse brain data: {adata.n_obs} spots x {adata.n_vars} genes")
except:
    # Create minimal synthetic data for demonstration
    print("Creating synthetic spatial data for demonstration...")
    n_spots = 500
    n_genes = 1000

    # Create count matrix
    counts = np.random.poisson(5, (n_spots, n_genes))

    # Create AnnData
    adata = sc.AnnData(X=counts)
    adata.var_names = pd.Index([f'GENE_{i}' for i in range(n_genes)])
    adata.obs_names = [f'SPOT_{i}' for i in range(n_spots)]

    # Add spatial coordinates (simulating a grid)
    grid_size = int(np.ceil(np.sqrt(n_spots)))
    x = np.repeat(np.arange(grid_size), grid_size)[:n_spots]
    y = np.tile(np.arange(grid_size), grid_size)[:n_spots]
    adata.obsm['spatial'] = np.column_stack([x * 100, y * 100])  # 100 micron spacing

    # Add some marker genes
    marker_genes = ['TGFB1', 'TGFBR1', 'TGFBR2', 'IL6', 'IL6R', 'IL6ST',
                    'CXCL12', 'CXCR4', 'WNT5A', 'FZD4']
    var_names = adata.var_names.tolist()
    for i, gene in enumerate(marker_genes):
        if i < n_genes:
            var_names[i] = gene
    adata.var_names = pd.Index(var_names)

    print(f"Created synthetic data: {adata.n_obs} spots x {adata.n_vars} genes")

# Check spatial coordinates
print(f"\nSpatial coordinates shape: {adata.obsm['spatial'].shape}")
print(f"Coordinate range:")
print(f"  X: [{adata.obsm['spatial'][:,0].min():.1f}, {adata.obsm['spatial'][:,0].max():.1f}]")
print(f"  Y: [{adata.obsm['spatial'][:,1].min():.1f}, {adata.obsm['spatial'][:,1].max():.1f}]")


# ============================================================================
# PART 2: Data Preparation
# ============================================================================

print("\n" + "=" * 70)
print("PART 2: Data Preparation")
print("=" * 70)

# Prepare data for COMMOT
adata = prepare_data(
    adata,
    spatial_key='spatial',
    min_counts=100,
    normalize=True,
    log1p=True,
)

# Check spatial units
print("\nChecking spatial coordinate units...")
check_spatial_units(adata, spatial_key='spatial')

# Perform basic clustering for downstream analysis
print("\nPerforming clustering...")
sc.pp.highly_variable_genes(adata, n_top_genes=2000)
sc.pp.scale(adata)
sc.pp.pca(adata, n_comps=20)
sc.pp.neighbors(adata)
sc.tl.leiden(adata, resolution=0.5)
sc.tl.umap(adata)

print(f"Identified {adata.obs['leiden'].nunique()} clusters")


# ============================================================================
# PART 3: Load Ligand-Receptor Database
# ============================================================================

print("\n" + "=" * 70)
print("PART 3: Loading Ligand-Receptor Database")
print("=" * 70)

# Option 1: Use built-in CellChat database
try:
    df_lr_cellchat = get_lr_database(
        database='CellChat',
        species='mouse',  # or 'human'
        signaling_type='Secreted Signaling',
    )

    # Filter to pairs expressed in data
    df_lr_filtered = filter_lr_database(
        df_lr_cellchat,
        adata,
        min_cell_pct=0.05,
    )
except Exception as e:
    print(f"Could not load CellChat database: {e}")
    print("Creating custom database instead...")
    df_lr_filtered = None

# Option 2: Create custom LR database
print("\nCreating custom LR database...")
df_lr_custom = create_custom_lr_database(
    ligands=['TGFB1', 'IL6', 'CXCL12', 'WNT5A'],
    receptors=['TGFBR1_TGFBR2', 'IL6R_IL6ST', 'CXCR4', 'FZD4'],
    pathways=['TGFb', 'IL6', 'CXCL', 'WNT'],
)


# ============================================================================
# PART 4: Run COMMOT Analysis
# ============================================================================

print("\n" + "=" * 70)
print("PART 4: Running COMMOT Analysis")
print("=" * 70)

# Method 1: Run with custom LR pairs
print("\n--- Method 1: Custom LR pairs ---")
run_commot(
    adata,
    df_ligrec=df_lr_custom,
    database_name='custom',
    distance_threshold=200.0,  # microns
    heteromeric=True,
    heteromeric_delimiter='_',
    heteromeric_rule='min',
)

# Method 2: Run with built-in database (if available)
if df_lr_filtered is not None and len(df_lr_filtered) > 0:
    print("\n--- Method 2: Built-in CellChat database ---")
    run_commot(
        adata,
        df_ligrec=df_lr_filtered.head(50),  # Limit to top 50 pairs for speed
        database_name='cellchat',
        distance_threshold=200.0,
    )

# Alternative convenience function
# adata = run_commot_database(
#     adata,
#     database='CellChat',
#     species='mouse',
#     distance_threshold=200.0,
#     filter_pairs=True,
#     min_cell_pct=0.05,
# )

print("\nCOMMOT analysis complete!")
print(f"Available custom results: {[k for k in adata.obsm.keys() if 'commot-custom' in k]}")


# ============================================================================
# PART 5: Visualize Communication Patterns
# ============================================================================

print("\n" + "=" * 70)
print("PART 5: Visualization")
print("=" * 70)

# Get top LR pairs for visualization
df_top = get_top_lr_pairs(adata, n=5, database_name='custom')
print("\nTop LR pairs:")
print(df_top)

top_pairs = df_top['lr_pair'].tolist()

# 1. Plot communication strength (receiver)
print("\n--- Plotting communication strength ---")
fig, axes = plt.subplots(2, 2, figsize=(14, 12))
axes = axes.flatten()

for idx, lr_pair in enumerate(top_pairs[:4]):
    try:
        plot_communication_strength(
            adata,
            lr_pair=lr_pair,
            database_name='custom',
            summary='receiver',
            cmap='coolwarm',
            ax=axes[idx],
        )
        axes[idx].set_title(f'{lr_pair} (Receiver)')
    except Exception as e:
        axes[idx].text(0.5, 0.5, f'Error: {e}', ha='center', transform=axes[idx].transAxes)
        axes[idx].axis('off')

plt.tight_layout()
plt.savefig('commot_strength_receiver.png', dpi=150, bbox_inches='tight')
plt.close()
print("Saved: commot_strength_receiver.png")

# 2. Plot ligand and receptor expression
print("\n--- Plotting LR expression ---")
try:
    first_pair = top_pairs[0].split('-')
    if len(first_pair) == 2:
        ligand = first_pair[0]
        receptor = first_pair[1].split('_')[0]  # Take first part of heteromeric

        fig = plot_lr_expression(
            adata,
            ligand=ligand,
            receptor=receptor,
            figsize=(14, 6),
        )
        plt.savefig('commot_lr_expression.png', dpi=150, bbox_inches='tight')
        plt.close()
        print("Saved: commot_lr_expression.png")
except Exception as e:
    print(f"Could not plot LR expression: {e}")

# 3. Infer and plot communication direction
print("\n--- Inferring communication direction ---")
try:
    # Parse first LR pair into tuple for direction inference
    first_pair_parts = top_pairs[0].split('-')
    if len(first_pair_parts) == 2:
        lr_tuple = (first_pair_parts[0], first_pair_parts[1])

        infer_communication_direction(
            adata,
            database_name='custom',
            lr_pair=lr_tuple,
            k=5,
        )

        # Plot direction
        fig, axes = plt.subplots(1, 2, figsize=(16, 7))
        for idx, lr_pair in enumerate(top_pairs[:2]):
            pair_parts = lr_pair.split('-')
            if len(pair_parts) == 2:
                plot_communication_direction(
                    adata,
                    database_name='custom',
                    lr_pair=(pair_parts[0], pair_parts[1]),
                    plot_method='grid',
                    ax=axes[idx],
                )
                axes[idx].set_title(f'Direction: {lr_pair}')

        plt.tight_layout()
        plt.savefig('commot_direction.png', dpi=150, bbox_inches='tight')
        plt.close()
        print("Saved: commot_direction.png")
except Exception as e:
    print(f"Could not plot direction: {e}")


# ============================================================================
# PART 6: Cluster-Level Communication Analysis
# ============================================================================

print("\n" + "=" * 70)
print("PART 6: Cluster-Level Communication")
print("=" * 70)

# Compute cluster communication
print("\nComputing cluster communication...")
try:
    comm_matrix = cluster_communication(
        adata,
        cluster_key='leiden',
        database_name='custom',
    )
    print(f"\nCommunication matrix shape: {comm_matrix.shape}")
    print("\nTop sender-receiver pairs:")
    print(comm_matrix.stack().sort_values(ascending=False).head(10))

    # Plot cluster communication network
    print("\n--- Plotting cluster network ---")
    fig, ax = plt.subplots(figsize=(10, 10))
    plot_cluster_communication_network(
        adata,
        database_name='custom',
        cluster_key='leiden',
        ax=ax,
    )
    plt.savefig('commot_cluster_network.png', dpi=150, bbox_inches='tight')
    plt.close()
    print("Saved: commot_cluster_network.png")

    # Plot cluster communication dotplot
    print("\n--- Plotting cluster dotplot ---")
    fig, ax = plt.subplots(figsize=(12, 10))
    plot_cluster_communication_dotplot(
        adata,
        database_name='custom',
        cluster_key='leiden',
        ax=ax,
    )
    plt.savefig('commot_cluster_dotplot.png', dpi=150, bbox_inches='tight')
    plt.close()
    print("Saved: commot_cluster_dotplot.png")

except Exception as e:
    print(f"Cluster communication analysis failed: {e}")


# ============================================================================
# PART 7: Summary Visualizations
# ============================================================================

print("\n" + "=" * 70)
print("PART 7: Summary Visualizations")
print("=" * 70)

# Plot top LR pairs bar chart
print("\n--- Plotting top LR pairs ---")
fig, ax = plt.subplots(figsize=(10, 8))
plot_top_lr_pairs(
    adata,
    n=15,
    database_name='custom',
    summary='total',
    ax=ax,
)
plt.tight_layout()
plt.savefig('commot_top_pairs.png', dpi=150, bbox_inches='tight')
plt.close()
print("Saved: commot_top_pairs.png")

# Plot communication heatmap
print("\n--- Plotting communication heatmap ---")
try:
    fig, ax = plt.subplots(figsize=(12, 8))
    plot_communication_heatmap(
        adata,
        lr_pairs=top_pairs,
        database_name='custom',
        summary='receiver',
        ax=ax,
    )
    plt.tight_layout()
    plt.savefig('commot_heatmap.png', dpi=150, bbox_inches='tight')
    plt.close()
    print("Saved: commot_heatmap.png")
except Exception as e:
    print(f"Could not plot heatmap: {e}")


# ============================================================================
# PART 8: Export Results
# ============================================================================

print("\n" + "=" * 70)
print("PART 8: Exporting Results")
print("=" * 70)

export_results(
    adata,
    output_dir='./commot_results',
    database_name='custom',
    include_matrices=False,  # Set True to include large matrices
)

# Save annotated data
adata.write_h5ad('adata_with_commot.h5ad')
print("\nSaved: adata_with_commot.h5ad")


# ============================================================================
# Summary
# ============================================================================

print("\n" + "=" * 70)
print("Analysis Complete!")
print("=" * 70)
print("\nGenerated files:")
print("  - commot_strength_receiver.png: Communication strength maps")
print("  - commot_lr_expression.png: Ligand/receptor expression")
print("  - commot_direction.png: Communication direction vectors")
print("  - commot_cluster_network.png: Cluster communication network")
print("  - commot_cluster_dotplot.png: Cluster communication dotplot")
print("  - commot_top_pairs.png: Top LR pairs bar chart")
print("  - commot_heatmap.png: Communication heatmap")
print("  - commot_results/: Exported data files")
print("  - adata_with_commot.h5ad: Annotated AnnData object")
print("\nNext steps:")
print("  1. Explore specific pathways of interest")
print("  2. Compare communication between conditions (if applicable)")
print("  3. Perform DEG analysis related to communication (requires tradeSeq)")
print("  4. Validate findings with known biology")
print("=" * 70)
