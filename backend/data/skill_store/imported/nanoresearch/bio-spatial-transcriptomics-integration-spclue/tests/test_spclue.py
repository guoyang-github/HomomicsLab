"""
Unit tests for spCLUE implementation.

Tests core functionality including data preprocessing, graph construction,
model training, and clustering.

Author: Claude Code
Date: 2026-04-07
"""

import unittest
import numpy as np
import torch
import scanpy as sc
import anndata
from sklearn.decomposition import PCA
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from scripts import (
    spCLUE, preprocess, prepare_graph, clustering,
    fix_seed, refine_label, symm_norm
)


class TestDataPreprocessing(unittest.TestCase):
    """Test data preprocessing functions."""

    def setUp(self):
        """Create synthetic data for testing."""
        np.random.seed(42)
        n_spots = 100
        n_genes = 500

        # Create count matrix
        X = np.random.poisson(5, (n_spots, n_genes))

        # Create spatial coordinates
        spatial = np.random.rand(n_spots, 2) * 100

        # Create AnnData
        self.adata = anndata.AnnData(X=X)
        self.adata.obsm['spatial'] = spatial
        self.adata.layers['count'] = X.copy()

    def test_preprocess(self):
        """Test basic preprocessing."""
        adata_processed = preprocess(self.adata, hvgNumber=None)

        # Check output
        self.assertIsNotNone(adata_processed)
        self.assertEqual(adata_processed.shape[0], self.adata.shape[0])

    def test_prepare_graph_spatial(self):
        """Test spatial graph construction."""
        graph = prepare_graph(self.adata, key="spatial", n_neighbors=6)

        # Check output
        self.assertIsNotNone(graph)
        self.assertEqual(graph.shape, (self.adata.n_obs, self.adata.n_obs))

    def test_prepare_graph_expr(self):
        """Test expression graph construction."""
        # First preprocess
        adata = preprocess(self.adata, hvgNumber=100)

        graph = prepare_graph(adata, key="expr", n_neighbors=6, n_comps=10)

        # Check output
        self.assertIsNotNone(graph)
        self.assertEqual(graph.shape, (adata.n_obs, adata.n_obs))

    def test_symm_norm(self):
        """Test symmetric normalization."""
        adj = np.random.rand(10, 10)
        adj = (adj + adj.T) / 2  # Make symmetric
        np.fill_diagonal(adj, 0)  # Zero diagonal

        normalized = symm_norm(adj, weightDiag=0.3)

        # Check output properties
        self.assertEqual(normalized.shape, adj.shape)
        self.assertTrue(np.all(np.isfinite(normalized)))


class TestModelTraining(unittest.TestCase):
    """Test spCLUE model training."""

    def setUp(self):
        """Create synthetic data for model testing."""
        fix_seed(42)
        np.random.seed(42)

        n_spots = 50
        n_features = 20

        # Create synthetic input data (PCA-reduced)
        self.input_data = np.random.randn(n_spots, n_features).astype(np.float32)

        # Create synthetic graphs
        adj = np.random.rand(n_spots, n_spots)
        adj = (adj + adj.T) / 2
        np.fill_diagonal(adj, 1)
        import scipy.sparse as sp
        self.graph_spatial = sp.coo_matrix(adj)
        self.graph_expr = sp.coo_matrix(adj)

        self.graph_dict = {
            "spatial": self.graph_spatial,
            "expr": self.graph_expr
        }

        self.device = torch.device("cpu")

    def test_model_initialization(self):
        """Test model initialization."""
        model = spCLUE(
            input_data=self.input_data,
            graph_dict=self.graph_dict,
            n_clusters=5,
            epochs=10,
            device=self.device,
            dim_input=20,
            dim_hidden=16,
            dim_embed=8,
            random_seed=42
        )

        self.assertIsNotNone(model)
        self.assertEqual(model.n_clusters, 5)

    def test_model_training(self):
        """Test model training."""
        model = spCLUE(
            input_data=self.input_data,
            graph_dict=self.graph_dict,
            n_clusters=5,
            epochs=10,
            device=self.device,
            dim_input=20,
            dim_hidden=16,
            dim_embed=8,
            random_seed=42
        )

        pred_labels, embeddings = model.train()

        # Check outputs
        self.assertEqual(len(pred_labels), self.input_data.shape[0])
        self.assertEqual(embeddings.shape, (self.input_data.shape[0], 8))
        self.assertTrue(np.all(np.isfinite(embeddings)))

    def test_batch_training(self):
        """Test batch training for multi-slice."""
        batch_list = np.array([0] * 25 + [1] * 25)

        model = spCLUE(
            input_data=self.input_data,
            graph_dict=self.graph_dict,
            n_clusters=5,
            batch_list=batch_list,
            epochs=10,
            device=self.device,
            dim_input=20,
            dim_hidden=16,
            dim_embed=8,
            batch_train=False,
            random_seed=42
        )

        _, embeddings = model.trainBatch()

        # Check outputs
        self.assertEqual(embeddings.shape, (self.input_data.shape[0], 8))
        self.assertTrue(np.all(np.isfinite(embeddings)))


class TestClustering(unittest.TestCase):
    """Test clustering functions."""

    def setUp(self):
        """Create synthetic data with embeddings."""
        np.random.seed(42)
        n_spots = 100

        # Create AnnData
        X = np.random.poisson(5, (n_spots, 50))
        self.adata = anndata.AnnData(X=X)

        # Add synthetic embeddings
        self.adata.obsm['spCLUE'] = np.random.randn(n_spots, 16)
        self.adata.obsm['spatial'] = np.random.rand(n_spots, 2) * 100

    def test_kmeans_clustering(self):
        """Test k-means clustering."""
        adata = clustering(
            self.adata,
            n_clusters=5,
            key='spCLUE',
            cluster_methods='kmeans'
        )

        self.assertIn('kmeans', adata.obs.columns)
        self.assertEqual(adata.obs['kmeans'].nunique(), 5)

    def test_leiden_clustering(self):
        """Test Leiden clustering."""
        # Create neighbors first
        sc.pp.neighbors(self.adata, use_rep='spCLUE')

        adata = clustering(
            self.adata,
            n_clusters=5,
            key='spCLUE',
            cluster_methods='leiden'
        )

        self.assertIn('leiden', adata.obs.columns)

    def test_refine_label(self):
        """Test spatial label refinement."""
        # Add initial labels
        self.adata.obs['label'] = np.random.randint(0, 5, self.adata.n_obs).astype(str)

        refined = refine_label(self.adata, radius=10, key='label', suffix='test')

        self.assertIn('label_refined_test', self.adata.obs.columns)
        self.assertEqual(len(refined), self.adata.n_obs)


class TestIntegration(unittest.TestCase):
    """Test full integration workflow."""

    def test_end_to_end_single_slice(self):
        """Test complete single-slice workflow."""
        fix_seed(42)
        np.random.seed(42)

        # Create synthetic data
        n_spots = 50
        n_genes = 100
        X = np.random.poisson(5, (n_spots, n_genes))
        adata = anndata.AnnData(X=X)
        adata.obsm['spatial'] = np.random.rand(n_spots, 2) * 100
        adata.layers['count'] = X.copy()

        # Preprocess
        adata = preprocess(adata, hvgNumber=None)

        # PCA
        pca = PCA(n_components=20, random_state=0)
        input_data = pca.fit_transform(adata.X)

        # Build graphs
        graph_dict = {
            "spatial": prepare_graph(adata, key="spatial", n_neighbors=6),
            "expr": prepare_graph(adata, key="expr", n_neighbors=6, n_comps=10)
        }

        # Train
        device = torch.device("cpu")
        model = spCLUE(
            input_data=input_data,
            graph_dict=graph_dict,
            n_clusters=5,
            epochs=10,
            device=device,
            dim_input=20,
            dim_hidden=16,
            dim_embed=8,
            random_seed=42
        )

        pred_labels, embeddings = model.train()

        # Store and cluster
        adata.obsm['spCLUE'] = embeddings
        adata.obs['pred'] = pred_labels

        adata = clustering(adata, n_clusters=5, key='spCLUE', cluster_methods='kmeans')

        # Verify results
        self.assertIn('spCLUE', adata.obsm)
        self.assertIn('kmeans', adata.obs.columns)
        self.assertEqual(adata.obsm['spCLUE'].shape[0], n_spots)


def run_tests():
    """Run all tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestDataPreprocessing))
    suite.addTests(loader.loadTestsFromTestCase(TestModelTraining))
    suite.addTests(loader.loadTestsFromTestCase(TestClustering))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
