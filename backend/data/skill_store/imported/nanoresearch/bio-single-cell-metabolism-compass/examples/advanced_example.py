"""Advanced example of COMPASS metabolic flux analysis.

This example demonstrates advanced features including:
- Differential flux analysis between groups
- Subsystem-level analysis
- Visualization of results
- Integration with Scanpy workflows
"""

import sys
sys.path.append('../scripts/python')

import scanpy as sc
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

from core_analysis import (
    run_compass,
    add_compass_results_to_adata,
    analyze_differential_flux,
    summarize_metabolic_activity,
    get_available_models,
    load_compass_results
)
from utils import (
    check_gene_overlap,
    recommend_model,
    filter_reactions_by_activity,
    get_top_reactions,
    get_top_metabolites,
    summarize_compass_results,
    create_reaction_subset_file
)
from visualization import (
    plot_reaction_heatmap,
    plot_metabolite_scores,
    plot_differential_flux,
    plot_subsystem_activity,
    plot_sample_comparison,
    plot_compass_summary
)

# Step 1: Load and prepare data
# -----------------------------
print("Loading data...")

# For this example, we'll create synthetic data with known metabolic differences
# In practice, load your real data: adata = sc.read_h5ad('your_data.h5ad')

np.random.seed(42)
n_cells = 200
n_genes = 1000

# Create metabolic gene expression
genes = [f'GENE_{i}' for i in range(n_genes)]

# Add some real metabolic gene names
metabolic_genes = [
    'GAPDH', 'LDHA', 'LDHB', 'HK1', 'HK2', 'PFKP', 'PFKL', 'PKM', 'ENO1', 'PGK1',
    'CS', 'ACO2', 'IDH1', 'IDH2', 'OGDH', 'SUCLG1', 'SDHA', 'SDHB', 'FH', 'MDH1',
    'ATP5F1A', 'ATP5F1B', 'ATP5F1C', 'NDUFV1', 'NDUFV2', 'SDHC', 'UQCRC1', 'COX4I1',
    'G6PD', 'PGD', 'TKT', 'TALDO1',
    'ACACA', 'FASN', 'SCD', 'ACLY',
    'CPT1A', 'CPT1B', 'ACADVL', 'ACADM', 'HADHA',
    'GLS', 'GLS2', 'GLUD1', 'GPT', 'GOT1', 'PSAT1', 'PSPH'
]

for i, gene in enumerate(metabolic_genes):
    if i < len(genes):
        genes[i] = gene

# Create cell types with different metabolic profiles
cell_types = ['High_Glycolysis', 'High_OXPHOS', 'High_FASynthesis']
labels = np.random.choice(cell_types, n_cells)

# Generate expression data
X = np.random.lognormal(2, 0.5, (n_cells, n_genes))

for i, ct in enumerate(cell_types):
    mask = labels == ct
    if ct == 'High_Glycolysis':
        # Boost glycolytic genes
        for gene in ['GAPDH', 'LDHA', 'HK1', 'PFKP', 'PKM']:
            if gene in genes:
                X[mask, genes.index(gene)] *= 5
    elif ct == 'High_OXPHOS':
        # Boost OXPHOS genes
        for gene in ['ATP5F1A', 'NDUFV1', 'SDHA', 'CS', 'ACO2']:
            if gene in genes:
                X[mask, genes.index(gene)] *= 5
    else:  # High_FASynthesis
        # Boost fatty acid synthesis
        for gene in ['ACACA', 'FASN', 'SCD', 'ACLY']:
            if gene in genes:
                X[mask, genes.index(gene)] *= 5

adata = sc.AnnData(
    X=X,
    obs=pd.DataFrame({
        'cell_type': labels,
        'sample': np.random.choice(['Control', 'Treatment'], n_cells)
    }, index=[f'cell_{i}' for i in range(n_cells)]),
    var=pd.DataFrame(index=genes)
)

print(f"Data shape: {adata.shape}")
print(f"Cell type distribution:\n{adata.obs['cell_type'].value_counts()}")

# Step 2: Check gene overlap with metabolic model
# -----------------------------------------------
print("\n" + "="*50)
print("Step 2: Gene Overlap Analysis")
print("="*50)

# Get gene list for RECON2 model (simplified for example)
# In practice, use: from core_analysis import list_model_genes
# model_genes = list_model_genes(model='RECON2_mat', species='homo_sapiens')
model_genes = metabolic_genes  # Simplified for example

overlap = check_gene_overlap(adata, model_genes)
print(f"\nGene overlap statistics:")
print(f"  Data genes: {overlap['n_data_genes']}")
print(f"  Model genes: {overlap['n_model_genes']}")
print(f"  Overlap: {overlap['n_overlap']} ({overlap['overlap_fraction']*100:.1f}%)")

if overlap['overlap_fraction'] < 0.5:
    print("  Warning: Low gene overlap may affect results")

# Step 3: Model selection
# -----------------------
print("\n" + "="*50)
print("Step 3: Model Selection")
print("="*50)

models = get_available_models()
print("\nAvailable models:")
print(models[['model', 'species', 'description']].to_string())

recommended = recommend_model(species='human')
print(f"\nRecommended model: {recommended}")

# Step 4: Run COMPASS with advanced parameters
# --------------------------------------------
print("\n" + "="*50)
print("Step 4: Running COMPASS")
print("="*50)

# For larger datasets, use microclustering
use_microcluster = adata.n_obs > 500
microcluster_size = 50 if use_microcluster else None

print(f"Using microclustering: {use_microcluster}")
if use_microcluster:
    print(f"Target microcluster size: {microcluster_size}")

# Note: This requires COMPASS to be installed with CPLEX
# compass_results = run_compass(
#     adata,
#     output_dir='./compass_output_advanced',
#     model='RECON2_mat',
#     species='homo_sapiens',
#     num_processes=4,
#     lambda_param=0.25,  # Enable penalty sharing between cells
#     num_neighbors=30,
#     penalty_diffusion='knn',
#     and_function='mean',
#     microcluster_size=microcluster_size,
#     calc_metabolites=True,
#     verbose=True
# )

# For demonstration, we'll create mock results
print("Creating mock results for demonstration...")
n_reactions = 500
n_metabolites = 200
compass_results = {
    'reaction_scores': pd.DataFrame(
        np.random.gamma(2, 0.5, (n_reactions, n_cells)),
        index=[f'R{i}' for i in range(n_reactions)],
        columns=adata.obs_names
    ),
    'uptake_scores': pd.DataFrame(
        np.random.gamma(2, 0.5, (n_metabolites, n_cells)),
        index=[f'M{i}' for i in range(n_metabolites)],
        columns=adata.obs_names
    ),
    'secretion_scores': pd.DataFrame(
        np.random.gamma(2, 0.5, (n_metabolites, n_cells)),
        index=[f'M{i}' for i in range(n_metabolites)],
        columns=adata.obs_names
    )
}

# Simulate some metabolic differences
for ct in cell_types:
    mask = adata.obs['cell_type'] == ct
    cells = adata.obs_names[mask]

    if ct == 'High_Glycolysis':
        # Boost glycolysis reactions
        for rxn in ['R1', 'R2', 'R3']:
            if rxn in compass_results['reaction_scores'].index:
                compass_results['reaction_scores'].loc[rxn, cells] *= 2
    elif ct == 'High_OXPHOS':
        # Boost OXPHOS reactions
        for rxn in ['R10', 'R11', 'R12']:
            if rxn in compass_results['reaction_scores'].index:
                compass_results['reaction_scores'].loc[rxn, cells] *= 2

print(f"COMPASS results generated!")
print(f"  Reactions: {compass_results['reaction_scores'].shape[0]}")
print(f"  Metabolites: {compass_results['uptake_scores'].shape[0]}")

# Step 5: Summarize results
# -------------------------
print("\n" + "="*50)
print("Step 5: Result Summary")
print("="*50)

summary = summarize_compass_results(
    compass_results,
    groupby=adata.obs['cell_type']
)

print("\nOverall statistics:")
print(f"  Mean reaction score: {summary['reactions']['mean_score']:.3f}")
print(f"  Median reaction score: {summary['reactions']['median_score']:.3f}")

print("\nBy cell type:")
for ct, stats in summary['reactions']['by_group'].items():
    print(f"  {ct}: mean={stats['mean_score']:.3f}, n={stats['n_cells']}")

# Step 6: Filter and identify top reactions
# -----------------------------------------
print("\n" + "="*50)
print("Step 6: Top Reactions")
print("="*50)

# Filter to active reactions
active_reactions = filter_reactions_by_activity(
    compass_results['reaction_scores'],
    min_activity=0.5,
    min_cells=10
)
print(f"Active reactions: {active_reactions.shape[0]}")

# Get top reactions by variance (most variable across cells)
top_reactions = get_top_reactions(
    compass_results['reaction_scores'],
    n=10,
    by='std'
)
print("\nTop 10 most variable reactions:")
for rxn in top_reactions.index:
    mean_score = top_reactions.loc[rxn].mean()
    std_score = top_reactions.loc[rxn].std()
    print(f"  {rxn}: mean={mean_score:.3f}, std={std_score:.3f}")

# Step 7: Differential flux analysis
# ----------------------------------
print("\n" + "="*50)
print("Step 7: Differential Flux Analysis")
print("="*50)

# Compare High_Glycolysis vs High_OXPHOS
group1 = 'High_Glycolysis'
group2 = 'High_OXPHOS'
mask = adata.obs['cell_type'].isin([group1, group2])

subset_scores = compass_results['reaction_scores'].loc[:, mask]
subset_groups = adata.obs.loc[mask, 'cell_type']

diff_results = analyze_differential_flux(
    subset_scores,
    subset_groups,
    method='wilcoxon'
)

print(f"\nDifferential reactions between {group1} and {group2}:")
print(f"  Total tested: {len(diff_results)}")
print(f"  Significant (FDR < 0.05): {(diff_results['padj'] < 0.05).sum()}")

if len(diff_results) > 0:
    print("\nTop 5 differential reactions:")
    for _, row in diff_results.head(5).iterrows():
        direction = "higher in B" if row['log2FC'] > 0 else "higher in A"
        print(f"  {row['reaction']}: log2FC={row['log2FC']:.2f}, FDR={row['padj']:.2e} ({direction})")

# Step 8: Visualization
# ---------------------
print("\n" + "="*50)
print("Step 8: Generating Visualizations")
print("="*50)

output_dir = './compass_plots'
Path(output_dir).mkdir(exist_ok=True)

# Plot 1: Reaction heatmap
print("Creating reaction heatmap...")
fig = plot_reaction_heatmap(
    compass_results['reaction_scores'],
    n_top=50,
    save_path=f'{output_dir}/reaction_heatmap.png'
)
plt.close()

# Plot 2: Metabolite scores
print("Creating metabolite score plot...")
fig = plot_metabolite_scores(
    compass_results['uptake_scores'],
    compass_results['secretion_scores'],
    n_top=15,
    save_path=f'{output_dir}/metabolite_scores.png'
)
plt.close()

# Plot 3: Differential flux
print("Creating differential flux plot...")
fig = plot_differential_flux(
    diff_results,
    fdr_threshold=0.05,
    top_n=15,
    save_path=f'{output_dir}/differential_flux.png'
)
plt.close()

# Plot 4: Sample comparison
print("Creating sample comparison plot...")
fig = plot_sample_comparison(
    compass_results['reaction_scores'],
    adata.obs['cell_type'],
    top_n=20,
    save_path=f'{output_dir}/sample_comparison.png'
)
plt.close()

print(f"\nPlots saved to {output_dir}/")

# Step 9: Generate summary report
# -------------------------------
print("\n" + "="*50)
print("Step 9: Summary Report")
print("="*50)

print(f"""
COMPASS Analysis Report
======================

Dataset:
  - Cells: {adata.n_obs}
  - Genes: {adata.n_vars}
  - Cell types: {', '.join(adata.obs['cell_type'].unique())}

Metabolic Model: RECON2_mat

Results:
  - Reactions analyzed: {compass_results['reaction_scores'].shape[0]}
  - Metabolites analyzed: {compass_results['uptake_scores'].shape[0]}
  - Active reactions: {active_reactions.shape[0]}

Key Findings:
  - Most variable reactions identified
  - Differential flux between {group1} and {group2}
  - {(diff_results['padj'] < 0.05).sum()} significantly different reactions

Output files:
  - Plots: {output_dir}/*.png
  - Data: compass_output_advanced/

Next steps:
  1. Explore specific pathways of interest
  2. Correlate with gene expression
  3. Perform GSEA on reaction scores
  4. Export results for further analysis
""")

print("\nAnalysis complete!")
