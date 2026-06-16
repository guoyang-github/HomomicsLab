"""
GSEApy enrichment analysis for single-cell data.

This module provides ORA, GSEA, and ssGSEA functionality using gseapy.
"""

from .ora_analysis import run_enrichr, run_ora, run_ora_per_cluster
from .gsea_analysis import run_prerank, run_gsea, run_gsea_per_cluster, prepare_ranked_list
from .ssgsea_analysis import run_ssgsea, run_ssgsea_pseudobulk, score_pathway_on_umap, compare_pathways_across_groups
from .visualization import plot_enrichment, plot_gsea, plot_ssgsea_heatmap, plot_pathway_comparison
from .utils import prepare_gene_list, filter_gene_sets, load_gene_set

__all__ = [
    # ORA
    'run_enrichr',
    'run_ora',
    'run_ora_per_cluster',
    # GSEA
    'run_prerank',
    'run_gsea',
    'run_gsea_per_cluster',
    'prepare_ranked_list',
    # ssGSEA
    'run_ssgsea',
    'run_ssgsea_pseudobulk',
    'score_pathway_on_umap',
    'compare_pathways_across_groups',
    # Visualization
    'plot_enrichment',
    'plot_gsea',
    'plot_ssgsea_heatmap',
    'plot_pathway_comparison',
    # Utilities
    'prepare_gene_list',
    'filter_gene_sets',
    'load_gene_set',
]
