"""
Unit tests for STAGATE spatial domain identification skill.

Tests the wrapper functions in scripts/python/.
"""

import unittest
import numpy as np
import pandas as pd
import scanpy as sc
from anndata import AnnData

# Import functions to test
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts' / 'python'))

from core_analysis import (
    prepare_data,
    build_spatial_network,
    create_batch_data,
    leiden_clustering,
    louvain_clustering,
)

from visualization import (
    plot_domains,
    plot_embedding_umap,
    plot_domain_proportions,
)


def create_test_adata(n_spots=100, n_genes=200, spatial_key='spatial'):
    """Create minimal test AnnData with spatial coordinates."""
    np.random.seed(42)

    counts = np.random.poisson(5, (n_spots, n_genes))
    adata = AnnData(X=counts)
    adata.var_names = [f'GENE_{i}' for i in range(n_genes)]
    adata.obs_names = [f'SPOT_{i}' for i in range(n_spots)]

    # Grid coordinates
    grid_size = int(np.ceil(np.sqrt(n_spots)))
    x = np.repeat(np.arange(grid_size), grid_size)[:n_spots]
    y = np.tile(np.arange(grid_size), grid_size)[:n_spots]
    adata.obsm[spatial_key] = np.column_stack([x * 100, y * 100])

    adata.obs['cluster'] = pd.Categorical(np.random.choice(['A', 'B', 'C'], n_spots))

    return adata


class TestDataPreparation(unittest.TestCase):
    """Tests for data preparation functions."""

    def test_prepare_data_basic(self):
        """Test basic data preparation."""
        adata = create_test_adata()
        adata_prep = prepare_data(adata, min_counts=1, normalize=False, log1p=False)

        self.assertIsInstance(adata_prep, AnnData)
        self.assertEqual(adata_prep.n_obs, adata.n_obs)

    def test_prepare_data_filtering(self):
        """Test that low-count spots are filtered."""
        adata = create_test_adata()
        adata.X[0, :] = 0

        adata_prep = prepare_data(adata, min_counts=10, normalize=False, log1p=False)
        self.assertLess(adata_prep.n_obs, adata.n_obs)

    def test_prepare_data_hvg(self):
        """Test HVG selection."""
        adata = create_test_adata(n_spots=100, n_genes=500)
        adata_prep = prepare_data(adata, n_top_genes=100, normalize=False, log1p=False)

        self.assertIn('highly_variable', adata_prep.var.columns)


class TestSpatialNetwork(unittest.TestCase):
    """Tests for spatial network functions."""

    def test_build_spatial_network_radius(self):
        """Test radius-based network construction."""
        adata = create_test_adata()
        build_spatial_network(adata, rad_cutoff=150, model='Radius', verbose=False)

        self.assertIn('Spatial_Net', adata.uns)
        self.assertIn('Cell1', adata.uns['Spatial_Net'].columns)
        self.assertIn('Cell2', adata.uns['Spatial_Net'].columns)

    def test_build_spatial_network_knn(self):
        """Test KNN-based network construction."""
        adata = create_test_adata()
        build_spatial_network(adata, k_cutoff=5, model='KNN', verbose=False)

        self.assertIn('Spatial_Net', adata.uns)

    def test_build_spatial_network_missing_coords(self):
        """Test error for missing coordinates."""
        adata = create_test_adata()
        del adata.obsm['spatial']

        with self.assertRaises(ValueError):
            build_spatial_network(adata, rad_cutoff=150)


class TestBatchProcessing(unittest.TestCase):
    """Tests for batch processing."""

    def test_create_batch_data(self):
        """Test batch data creation."""
        adata = create_test_adata(n_spots=400)
        batch_list = create_batch_data(adata, num_batch_x=2, num_batch_y=2)

        self.assertEqual(len(batch_list), 4)

    def test_create_batch_data_sizes(self):
        """Test batch sizes are reasonable."""
        adata = create_test_adata(n_spots=400)
        batch_list = create_batch_data(adata, num_batch_x=2, num_batch_y=2)

        sizes = [b.n_obs for b in batch_list]
        # Each batch should have some cells
        self.assertTrue(all(s > 0 for s in sizes))


class TestClustering(unittest.TestCase):
    """Tests for clustering functions."""

    def test_leiden_clustering(self):
        """Test Leiden clustering."""
        adata = create_test_adata()

        # Add mock embeddings
        adata.obsm['STAGATE'] = np.random.rand(adata.n_obs, 30)

        adata = leiden_clustering(adata, resolution=0.5, used_obsm='STAGATE')

        self.assertIn('stagate_leiden', adata.obs)
        self.assertTrue(adata.obs['stagate_leiden'].nunique() > 0)

    def test_louvain_clustering(self):
        """Test Louvain clustering."""
        adata = create_test_adata()
        adata.obsm['STAGATE'] = np.random.rand(adata.n_obs, 30)

        adata = louvain_clustering(adata, resolution=0.5, used_obsm='STAGATE')

        self.assertIn('stagate_louvain', adata.obs)

    def test_clustering_missing_embedding(self):
        """Test error for missing embedding."""
        adata = create_test_adata()

        with self.assertRaises(ValueError):
            leiden_clustering(adata, used_obsm='MISSING')


class TestVisualization(unittest.TestCase):
    """Tests for visualization functions."""

    def test_plot_domains(self):
        """Test domain plotting."""
        import matplotlib.pyplot as plt

        adata = create_test_adata()
        adata.obs['mclust'] = pd.Categorical(np.random.choice([1, 2, 3], adata.n_obs))

        fig, ax = plt.subplots()
        result = plot_domains(adata, domain_key='mclust', ax=ax)

        self.assertIsNotNone(result)
        plt.close()

    def test_plot_embedding_umap(self):
        """Test UMAP plotting."""
        import matplotlib.pyplot as plt

        adata = create_test_adata()
        adata.obsm['STAGATE'] = np.random.rand(adata.n_obs, 30)
        adata.obs['mclust'] = pd.Categorical(np.random.choice([1, 2, 3], adata.n_obs))

        fig, ax = plt.subplots()
        result = plot_embedding_umap(adata, embedding_key='STAGATE', color_key='mclust', ax=ax)

        self.assertIsNotNone(result)
        plt.close()

    def test_plot_domain_proportions(self):
        """Test domain proportions plotting."""
        adata = create_test_adata()
        adata.obs['mclust'] = pd.Categorical(np.random.choice([1, 2, 3], adata.n_obs))

        fig = plot_domain_proportions(adata, domain_key='mclust')

        self.assertIsNotNone(fig)
        import matplotlib.pyplot as plt
        plt.close()


class TestIntegration(unittest.TestCase):
    """Integration tests."""

    def test_complete_workflow_mock(self):
        """Test complete workflow with mock data."""
        # Create data
        adata = create_test_adata(n_spots=50, n_genes=100)

        # Prepare
        adata_prep = prepare_data(adata, min_counts=1, normalize=False, log1p=False)
        self.assertIsInstance(adata_prep, AnnData)

        # Build network
        build_spatial_network(adata_prep, rad_cutoff=150, verbose=False)
        self.assertIn('Spatial_Net', adata_prep.uns)

        # Mock STAGATE training (would require PyTorch)
        adata_prep.obsm['STAGATE'] = np.random.rand(adata_prep.n_obs, 30)

        # Cluster
        adata_prep = leiden_clustering(adata_prep, used_obsm='STAGATE')
        self.assertIn('stagate_leiden', adata_prep.obs)

        print("Workflow setup successful")


if __name__ == '__main__':
    unittest.main(verbosity=2)
