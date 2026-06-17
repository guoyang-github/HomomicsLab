#!/usr/bin/env python3
"""
Minimal working example for bio-single-cell-enrichment-gseapy.

Demonstrates basic ORA, GSEA, and ssGSEA workflow with test data.
"""

import sys
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "python"))

import scanpy as sc
import matplotlib.pyplot as plt

# Import from skill
from ora_analysis import run_ora, run_ora_per_cluster
from gsea_analysis import run_prerank, prepare_ranked_list
from ssgsea_analysis import run_ssgsea, score_pathway_on_umap
from visualization import plot_enrichment


def main():
    print("=" * 60)
    print("Minimal Example: bio-single-cell-enrichment-gseapy")
    print("=" * 60)

    # Load test data
    print("\n1. Loading test data...")
    adata = sc.datasets.pbmc3k_processed()
    print(f"   Loaded {adata.n_obs} cells x {adata.n_vars} genes")

    # Ensure raw counts available
    if adata.raw is not None:
        adata = adata.raw.to_adata()

    # Preprocess
    print("\n2. Preprocessing...")
    sc.pp.normalize_total(adata, target_sum=1e4)
    sc.pp.log1p(adata)
    sc.pp.highly_variable_genes(adata, n_top_genes=2000)
    # NOTE: Do NOT scale before rank_genes_groups — scaling causes NaN logfoldchanges
    sc.tl.pca(adata)
    sc.pp.neighbors(adata)
    sc.tl.umap(adata)
    sc.tl.leiden(adata, resolution=0.5)
    print(f"   Found {len(adata.obs['leiden'].unique())} clusters")

    # 3. ORA Analysis
    print("\n3. Running ORA analysis...")
    sc.tl.rank_genes_groups(adata, groupby='leiden', method='wilcoxon')

    # Run ORA for first cluster
    cluster_0 = adata.obs['leiden'].cat.categories[0]
    ora_results = run_ora(
        adata,
        group=cluster_0,
        gene_sets='KEGG_2021_Human',
        top_n=100,  # Use top 100 genes
    )
    print(f"   Cluster {cluster_0}: {len(ora_results)} pathways enriched")

    if len(ora_results) > 0:
        print(f"   Top pathway: {ora_results.iloc[0]['Term']}")

    # 4. GSEA Analysis
    print("\n4. Running GSEA analysis...")
    ranked = prepare_ranked_list(adata, group=cluster_0)

    pre_res = run_prerank(
        ranked,
        gene_sets='MSigDB_Hallmark_2020',
        permutation_num=100,  # Reduced for speed
    )
    print(f"   GSEA results: {len(pre_res.res2d)} pathways")

    if len(pre_res.res2d) > 0:
        print(f"   Top pathway: {pre_res.res2d.iloc[0]['Term']}")

    # 5. ssGSEA Analysis
    print("\n5. Running ssGSEA analysis...")
    # Use small gene set for speed
    test_sets = {
        'Immune_Response': ['CD3D', 'CD3E', 'CD4', 'CD8A', 'CD8B'],
        'B_Cell': ['CD19', 'CD20', 'CD79A', 'CD79B'],
    }

    run_ssgsea(
        adata,
        gene_sets=test_sets,
        key_added='X_ssgsea',
        verbose=False,
    )
    print(f"   ssGSEA scores shape: {adata.obsm['X_ssgsea'].shape}")

    # 6. Visualization
    print("\n6. Creating visualizations...")
    output_dir = Path("./output")
    output_dir.mkdir(exist_ok=True)

    # Plot ORA results if available
    if len(ora_results) > 0:
        fig = plot_enrichment(
            ora_results,
            top_n=10,
            title=f'ORA Results - Cluster {cluster_0}',
        )
        fig.savefig(output_dir / 'ora_results.png', dpi=150, bbox_inches='tight')
        plt.close(fig)
        print(f"   Saved ORA plot to {output_dir / 'ora_results.png'}")

    # Plot GSEA for top pathway
    if len(pre_res.res2d) > 0:
        top_pathway = pre_res.res2d.iloc[0]['Term']
        fig = pre_res.plot(terms=[top_pathway])
        if fig is not None:
            fig.savefig(output_dir / 'gsea_plot.png', dpi=150, bbox_inches='tight')
            plt.close()
            print(f"   Saved GSEA plot for {top_pathway}")
        else:
            print(f"   GSEA plot returned None for {top_pathway}")

    print("\n" + "=" * 60)
    print("Example complete! Results saved to ./output/")
    print("=" * 60)

    return adata


if __name__ == "__main__":
    adata = main()
