"""
Cell2location deconvolution for spatial transcriptomics.

Reference-based deconvolution with uncertainty quantification.
"""

from .core_analysis import (
    prepare_data,
    run_cell2location,
    estimate_cell_type_proportions,
    extract_proportions,
)
from .visualization import (
    plot_proportions_spatial,
    plot_cell_type_maps,
    plot_proportion_distribution,
    plot_dominant_cell_type,
    normalize_proportions,
)
from .utils import validate_inputs, filter_low_quality_spots, estimate_optimal_epochs

__all__ = [
    'prepare_data',
    'run_cell2location',
    'estimate_cell_type_proportions',
    'extract_proportions',
    'plot_proportions_spatial',
    'plot_cell_type_maps',
    'plot_proportion_distribution',
    'plot_dominant_cell_type',
    'normalize_proportions',
    'validate_inputs',
    'filter_low_quality_spots',
    'estimate_optimal_epochs',
]
