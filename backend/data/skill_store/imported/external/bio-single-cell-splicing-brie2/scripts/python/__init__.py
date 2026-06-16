"""
BRIE2 Single-Cell Splicing Analysis Module

This module provides wrapper functions for BRIE2 (Bayesian Regression for Isoform Estimate)
to perform single-cell alternative splicing analysis.
"""

__version__ = "1.0.0"

from .core_analysis import (
    run_brie_count,
    run_brie_quant,
    filter_splicing_data,
    get_psi_values,
    get_significant_events,
    compare_cell_groups,
)

from .visualization import (
    plot_psi_distribution,
    plot_psi_heatmap,
    plot_volcano,
    plot_psi_trajectory,
    plot_splicing_summary,
)

from .utils import (
    load_brie_data,
    validate_adata_for_brie,
    prepare_cell_features,
    export_results,
    summarize_splicing_results,
)

__all__ = [
    # Core analysis
    "run_brie_count",
    "run_brie_quant",
    "filter_splicing_data",
    "get_psi_values",
    "get_significant_events",
    "compare_cell_groups",
    # Visualization
    "plot_psi_distribution",
    "plot_psi_heatmap",
    "plot_volcano",
    "plot_psi_trajectory",
    "plot_splicing_summary",
    # Utils
    "load_brie_data",
    "validate_adata_for_brie",
    "prepare_cell_features",
    "export_results",
    "summarize_splicing_results",
]
