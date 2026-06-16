"""
COMMOT spatial communication analysis using optimal transport.

Spatially-aware cell-cell communication analysis with optimal transport.
"""

from .core_analysis import (
    prepare_data,
    check_spatial_units,
    get_lr_database,
    filter_lr_database,
    create_custom_lr_database,
    run_commot,
    run_commot_database,
    infer_communication_direction,
    cluster_communication,
    detect_communication_deg,
    communication_spatial_autocorrelation,
    get_communication_matrix,
    get_communication_summary,
    get_top_lr_pairs,
    export_results,
)
from .visualization import (
    plot_communication_strength,
    plot_communication_direction,
    plot_lr_expression,
    plot_cluster_communication_network,
    plot_cluster_communication_dotplot,
    plot_cluster_communication_chord,
    plot_communication_heatmap,
    plot_top_lr_pairs,
    plot_communication_summary_by_cluster,
    plot_communication_comparison,
    plot_multiple_lr_pairs,
    create_figure_grid,
)

__all__ = [
    'prepare_data',
    'check_spatial_units',
    'get_lr_database',
    'filter_lr_database',
    'create_custom_lr_database',
    'run_commot',
    'run_commot_database',
    'infer_communication_direction',
    'cluster_communication',
    'detect_communication_deg',
    'communication_spatial_autocorrelation',
    'get_communication_matrix',
    'get_communication_summary',
    'get_top_lr_pairs',
    'export_results',
    'plot_communication_strength',
    'plot_communication_direction',
    'plot_lr_expression',
    'plot_cluster_communication_network',
    'plot_cluster_communication_dotplot',
    'plot_cluster_communication_chord',
    'plot_communication_heatmap',
    'plot_top_lr_pairs',
    'plot_communication_summary_by_cluster',
    'plot_communication_comparison',
    'plot_multiple_lr_pairs',
    'create_figure_grid',
]
