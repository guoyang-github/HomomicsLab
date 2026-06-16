"""
Tangram deconvolution for spatial transcriptomics.

Deep learning method for mapping single-cell RNA-seq data to spatial coordinates.

Author: Yang Guo
Date: 2026-04-03
"""

from .core_analysis import (
    # Data preparation
    prepare_data,
    annotate_gene_sparsity,

    # Core mapping
    map_cells_to_space,

    # Gene projection
    project_genes,
    compare_spatial_geneexp,

    # Cell annotation projection
    project_cell_annotations,
    count_cell_annotations,
    create_segment_cell_df,
    deconvolve_cell_annotations,
    extract_deconvolution_results,

    # Evaluation
    cross_val,
    eval_metric,
    get_training_scores,
    check_mapping_quality,

    # Utilities
    export_results,
    check_tangram_installed,
)

from .visualization import (
    # Training diagnostics
    plot_training_scores,
    plot_test_scores,
    plot_auc,
    plot_gene_sparsity,

    # Cell type visualization
    plot_cell_annotation,
    plot_cell_annotation_sc,
    plot_cell_type_map,
    plot_annotation_comparison,
    plot_deconvolution_results,

    # Gene visualization
    plot_genes,
    plot_genes_sc,

    # Other
    plot_annotation_entropy,
)

__all__ = [
    # Data preparation
    'prepare_data',
    'annotate_gene_sparsity',

    # Core mapping
    'map_cells_to_space',

    # Gene projection
    'project_genes',
    'compare_spatial_geneexp',

    # Cell annotation
    'project_cell_annotations',
    'count_cell_annotations',
    'create_segment_cell_df',
    'deconvolve_cell_annotations',

    'extract_deconvolution_results',

    # Evaluation
    'cross_val',
    'eval_metric',
    'get_training_scores',
    'check_mapping_quality',

    # Utilities
    'export_results',
    'check_tangram_installed',

    # Visualization - training
    'plot_training_scores',
    'plot_test_scores',
    'plot_auc',
    'plot_gene_sparsity',

    # Visualization - cell types
    'plot_cell_annotation',
    'plot_cell_annotation_sc',
    'plot_cell_type_map',
    'plot_annotation_comparison',
    'plot_deconvolution_results',

    # Visualization - genes
    'plot_genes',
    'plot_genes_sc',

    # Visualization - other
    'plot_annotation_entropy',
]
