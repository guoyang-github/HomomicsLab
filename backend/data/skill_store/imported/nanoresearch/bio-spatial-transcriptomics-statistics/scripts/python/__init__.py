"""
Spatial Transcriptomics Statistics Package

This package provides comprehensive spatial statistical analysis methods
for spatial transcriptomics data.

Modules:
    core_stats: Spatial autocorrelation statistics (Moran's I, Geary's C, LISA)
    hotspot: Hotspot detection (Getis-Ord Gi*)
    pattern: Pattern analysis (co-occurrence, join counts, Ripley's K/L)
    network: Network analysis (centrality, network properties)
    zones: Zone analysis (anchor zones, Ro/e, niche enrichment)
    utils: Utility functions for data validation

Example:
    >>> import sys
    >>> sys.path.append('scripts/python')
    >>> from core_stats import compute_morans_i
    >>> from hotspot import compute_getis_ord_gi
    >>> results = compute_morans_i(adata, genes=['GeneA'], k=6)
"""

__version__ = "1.0.0"
__author__ = "NanoResearch Team"

# Import main functions from each module
from .core_stats import (
    compute_morans_i,
    compute_gearys_c,
    compute_lisa,
    compute_bivariate_moran,
    compare_morans_geary,
    run_autocorrelation_analysis,
    validate_spatial_data,
    check_spatial_neighbors
)

from .hotspot import (
    compute_getis_ord_gi,
    compute_getis_ord_gi_batch,
    extract_hotspots,
    plot_hotspots,
    comprehensive_hotspot_analysis
)

from .pattern import (
    compute_cooccurrence,
    compute_cooccurrence_probability,
    compute_join_counts,
    interpret_join_counts,
    compute_neighborhood_enrichment,
    extract_enrichment_zscores,
    compute_ripley_k,
    compute_ripley_l,
    plot_ripley,
    analyze_spatial_patterns
)

from .network import (
    compute_centrality_scores,
    compute_spatial_centrality,
    compute_degree_centrality,
    compute_closeness_centrality,
    compute_betweenness_centrality,
    compute_network_properties,
    compute_clustering_coefficient,
    compute_network_efficiency,
    compute_interaction_matrix,
    extract_adjacency_matrix,
    analyze_network_structure
)

from .zones import (
    define_anchor_zones,
    define_neural_zones,
    analyze_zone_composition,
    compare_zone_gradients,
    compute_roe,
    interpret_roe_results,
    plot_roe_heatmap,
    compute_niche_enrichment_stats,
    analyze_spatial_zones
)

from .utils import (
    validate_spatial_data,
    check_sample_size,
    check_spatial_neighbors,
    infer_spatial_platform,
    suggest_neighbors
)

__all__ = [
    # Core stats
    'compute_morans_i',
    'compute_gearys_c',
    'compute_lisa',
    'compute_bivariate_moran',
    'compare_morans_geary',
    'run_autocorrelation_analysis',
    # Hotspot
    'compute_getis_ord_gi',
    'compute_getis_ord_gi_batch',
    'extract_hotspots',
    'plot_hotspots',
    'comprehensive_hotspot_analysis',
    # Pattern
    'compute_cooccurrence',
    'compute_cooccurrence_probability',
    'compute_join_counts',
    'interpret_join_counts',
    'compute_neighborhood_enrichment',
    'extract_enrichment_zscores',
    'compute_ripley_k',
    'compute_ripley_l',
    'plot_ripley',
    'analyze_spatial_patterns',
    # Network
    'compute_centrality_scores',
    'compute_spatial_centrality',
    'compute_degree_centrality',
    'compute_closeness_centrality',
    'compute_betweenness_centrality',
    'compute_network_properties',
    'compute_clustering_coefficient',
    'compute_network_efficiency',
    'compute_interaction_matrix',
    'extract_adjacency_matrix',
    'analyze_network_structure',
    # Zones
    'define_anchor_zones',
    'define_neural_zones',
    'analyze_zone_composition',
    'compare_zone_gradients',
    'compute_roe',
    'interpret_roe_results',
    'plot_roe_heatmap',
    'compute_niche_enrichment_stats',
    'analyze_spatial_zones',
    # Utils
    'validate_spatial_data',
    'check_sample_size',
    'check_spatial_neighbors',
    'infer_spatial_platform',
    'suggest_neighbors'
]
