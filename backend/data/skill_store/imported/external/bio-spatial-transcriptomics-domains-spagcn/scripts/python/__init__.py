"""
SpaGCN analysis module for spatial domain identification.

Author: Yang Guo
Date: 2026-04-03
"""

from .core_analysis import (
    prepare_data,
    calculate_adjacency_matrix,
    search_optimal_l,
    search_optimal_resolution,
    run_spagcn,
    run_spagcn_multi_sample,
    refine_domains,
    identify_svgs,
    find_meta_gene,
)

from .visualization import (
    plot_spatial_domains,
    plot_domain_comparison,
    plot_gene_expression,
    plot_multiple_genes,
    plot_domain_heatmap,
    plot_domain_proportions,
    plot_svg_results,
    plot_meta_gene,
    plot_multi_sample_domains,
)

from .utils import (
    find_neighbor_clusters,
    rank_genes_groups,
    calculate_moran_i,
)

__all__ = [
    'prepare_data',
    'calculate_adjacency_matrix',
    'search_optimal_l',
    'search_optimal_resolution',
    'run_spagcn',
    'run_spagcn_multi_sample',
    'refine_domains',
    'identify_svgs',
    'find_meta_gene',
    'plot_spatial_domains',
    'plot_domain_comparison',
    'plot_gene_expression',
    'plot_multiple_genes',
    'plot_domain_heatmap',
    'plot_domain_proportions',
    'plot_svg_results',
    'plot_meta_gene',
    'plot_multi_sample_domains',
    'find_neighbor_clusters',
    'rank_genes_groups',
    'calculate_moran_i',
]
