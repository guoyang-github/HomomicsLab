"""
STAGATE spatial domain identification skill.

Graph attention autoencoder for spatial transcriptomics clustering.
"""

__version__ = "1.1.0"
__author__ = "Yang Guo"

from .core_analysis import (
    prepare_data,
    build_spatial_network,
    build_3d_spatial_network,
    plot_network_stats,
    train_stagate,
    mclust_clustering,
    leiden_clustering,
    louvain_clustering,
    create_batch_data,
    export_results,
    compute_domain_enrichment,
)

from .visualization import (
    plot_domains,
    plot_domains_comparison,
    plot_embedding_umap,
    plot_embedding_pca,
    plot_domain_proportions,
    plot_confusion_matrix,
    plot_multi_sample_domains,
    plot_aligned_slices,
    plot_gene_expression,
    plot_denoising_comparison,
    plot_training_loss,
)

__all__ = [
    # Core analysis
    'prepare_data',
    'build_spatial_network',
    'build_3d_spatial_network',
    'plot_network_stats',
    'train_stagate',
    'mclust_clustering',
    'leiden_clustering',
    'louvain_clustering',
    'create_batch_data',
    'export_results',
    'compute_domain_enrichment',
    # Visualization
    'plot_domains',
    'plot_domains_comparison',
    'plot_embedding_umap',
    'plot_embedding_pca',
    'plot_domain_proportions',
    'plot_confusion_matrix',
    'plot_multi_sample_domains',
    'plot_aligned_slices',
    'plot_gene_expression',
    'plot_denoising_comparison',
    'plot_training_loss',
]
