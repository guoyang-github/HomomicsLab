#!/usr/bin/env python3
"""
GraphST Skill Unit Tests

Comprehensive tests for bio-spatial-transcriptomics-domains-graphst skill
covering data validation, model training, clustering, and utilities.
"""

import warnings
warnings.filterwarnings('ignore')

import unittest
import numpy as np
import pandas as pd
import scanpy as sc
import torch
import tempfile
import os

# Check if GraphST is available
try:
    from GraphST.GraphST import GraphST
    from GraphST.utils import clustering, search_res, refine_label
    from GraphST.preprocess import (
        construct_interaction, construct_interaction_KNN,
        preprocess, get_feature, add_contrastive_label
    )
    HAS_GRAPHST = True
except ImportError:
    HAS_GRAPHST = False
    print("WARNING: GraphST not installed. Core tests will be skipped.")


# ================================================================================
# Test Setup
# ================================================================================

def create_test_data(n_spots=100, n_genes=200, n_domains=3, seed=42):
    """Create synthetic test data."""
    np.random.seed(seed)

    # Spatial coordinates
    grid_size = int(np.sqrt(n_spots)) + 1
    x = np.repeat(np.arange(1, grid_size + 1), grid_size)[:n_spots]
    y = np.tile(np.arange(1, grid_size + 1), grid_size)[:n_spots]

    # Count matrix with domain patterns
    counts = np.random.poisson(lam=2, size=(n_spots, n_genes)).astype(float)

    # Add domain patterns
    domain_labels = np.zeros(n_spots, dtype=int)
    genes_per_domain = n_genes // n_domains

    for i in range(n_spots):
        # Assign domain based on position
        if x[i] <= grid_size // 2 and y[i] <= grid_size // 2:
            domain = 0
        elif x[i] > grid_size // 2 and y[i] <= grid_size // 2:
            domain = 1
        else:
            domain = 2

        domain_labels[i] = domain
        marker_start = domain * genes_per_domain
        marker_end = marker_start + genes_per_domain
        counts[i, marker_start:marker_end] += np.random.poisson(10, marker_end - marker_start)

    # Create AnnData
    adata = sc.AnnData(X=counts)
    adata.obs_names = [f"Spot_{i:03d}" for i in range(n_spots)]
    adata.var_names = [f"Gene_{i:03d}" for i in range(n_genes)]
    adata.obsm['spatial'] = np.column_stack([x, y])
    adata.obs['domain_gt'] = [f"Domain_{d}" for d in domain_labels]

    return adata


# ================================================================================
# Test Suite 1: Data Validation
# ================================================================================

class TestDataValidation(unittest.TestCase):
    """Tests for data validation and preparation."""

    def test_create_test_data(self):
        """Test synthetic data creation."""
        adata = create_test_data(n_spots=50, n_genes=100)
        self.assertEqual(adata.n_obs, 50)
        self.assertEqual(adata.n_vars, 100)
        self.assertIn('spatial', adata.obsm)
        self.assertEqual(adata.obsm['spatial'].shape, (50, 2))

    def test_spatial_coordinates(self):
        """Test spatial coordinates format."""
        adata = create_test_data(n_spots=100)
        self.assertIn('spatial', adata.obsm)
        self.assertEqual(adata.obsm['spatial'].shape[1], 2)
        self.assertTrue(np.all(adata.obsm['spatial'] > 0))

    def test_anndata_structure(self):
        """Test AnnData object structure."""
        adata = create_test_data(n_spots=50)
        self.assertIsNotNone(adata.X)
        self.assertEqual(len(adata.obs_names), 50)
        self.assertEqual(len(adata.var_names), 200)


# ================================================================================
# Test Suite 2: Preprocessing
# ================================================================================

@unittest.skipUnless(HAS_GRAPHST, "GraphST not installed")
class TestPreprocessing(unittest.TestCase):
    """Tests for preprocessing functions."""

    def test_construct_interaction(self):
        """Test spatial graph construction."""
        adata = create_test_data(n_spots=50)
        construct_interaction(adata, n_neighbors=3)

        self.assertIn('adj', adata.obsm)
        self.assertIn('graph_neigh', adata.obsm)
        self.assertEqual(adata.obsm['adj'].shape, (50, 50))

    def test_construct_interaction_knn(self):
        """Test KNN graph construction."""
        adata = create_test_data(n_spots=50)
        construct_interaction_KNN(adata, n_neighbors=3)

        self.assertIn('adj', adata.obsm)
        self.assertIn('graph_neigh', adata.obsm)

    def test_preprocess(self):
        """Test standard preprocessing."""
        adata = create_test_data(n_spots=50)
        preprocess(adata)

        self.assertIn('highly_variable', adata.var.columns)
        self.assertTrue(np.any(adata.var['highly_variable']))

    def test_get_feature(self):
        """Test feature extraction."""
        adata = create_test_data(n_spots=50)
        preprocess(adata)
        get_feature(adata)

        self.assertIn('feat', adata.obsm)
        self.assertIn('feat_a', adata.obsm)

    def test_add_contrastive_label(self):
        """Test contrastive label addition."""
        adata = create_test_data(n_spots=50)
        add_contrastive_label(adata)

        self.assertIn('label_CSL', adata.obsm)
        self.assertEqual(adata.obsm['label_CSL'].shape, (50, 2))


# ================================================================================
# Test Suite 3: GraphST Model
# ================================================================================

@unittest.skipUnless(HAS_GRAPHST, "GraphST not installed")
class TestGraphSTModel(unittest.TestCase):
    """Tests for GraphST model."""

    def test_model_initialization(self):
        """Test GraphST model initialization."""
        adata = create_test_data(n_spots=50)

        model = GraphST(
            adata=adata,
            device=torch.device('cpu'),
            epochs=10,
            random_seed=42
        )

        self.assertIsNotNone(model)
        self.assertEqual(model.epochs, 10)

    def test_model_training(self):
        """Test model training."""
        adata = create_test_data(n_spots=50)

        model = GraphST(
            adata=adata,
            device=torch.device('cpu'),
            epochs=10,
            random_seed=42
        )

        adata_out = model.train()

        self.assertIn('emb', adata_out.obsm)
        self.assertEqual(adata_out.obsm['emb'].shape[0], 50)

    def test_embeddings_properties(self):
        """Test learned embeddings properties."""
        adata = create_test_data(n_spots=50)

        model = GraphST(
            adata=adata,
            device=torch.device('cpu'),
            epochs=10,
            dim_output=32,
            random_seed=42
        )

        adata_out = model.train()
        emb = adata_out.obsm['emb']

        # Check shape (note: GraphST stores reconstruction in 'emb', not the latent embedding)
        self.assertEqual(emb.shape[0], 50)

        # Check no NaN values
        self.assertFalse(np.any(np.isnan(emb)))

        # Check finite values
        self.assertTrue(np.all(np.isfinite(emb)))


# ================================================================================
# Test Suite 4: Clustering
# ================================================================================

@unittest.skipUnless(HAS_GRAPHST, "GraphST not installed")
class TestClustering(unittest.TestCase):
    """Tests for clustering functions."""

    def test_clustering_leiden(self):
        """Test Leiden clustering."""
        adata = create_test_data(n_spots=100)

        model = GraphST(
            adata=adata,
            device=torch.device('cpu'),
            epochs=10,
            random_seed=42
        )
        adata = model.train()

        clustering(adata, n_clusters=3, method='leiden', start=0.1, end=2.0)

        self.assertIn('domain', adata.obs)
        self.assertIn('emb_pca', adata.obsm)

    def test_clustering_louvain(self):
        """Test Louvain clustering (skipped if louvain package not installed)."""
        try:
            import louvain
        except ImportError:
            self.skipTest("louvain package not installed")

        adata = create_test_data(n_spots=100)

        model = GraphST(
            adata=adata,
            device=torch.device('cpu'),
            epochs=10,
            random_seed=42
        )
        adata = model.train()

        clustering(adata, n_clusters=3, method='louvain', start=0.1, end=2.0)

        self.assertIn('domain', adata.obs)

    def test_refine_label(self):
        """Test spatial label refinement."""
        adata = create_test_data(n_spots=50)
        adata.obs['domain'] = np.random.choice(['A', 'B', 'C'], 50)

        refined = refine_label(adata, radius=10, key='domain')

        self.assertEqual(len(refined), 50)
        self.assertIsInstance(refined, list)


# ================================================================================
# Test Suite 5: Utilities
# ================================================================================

@unittest.skipUnless(HAS_GRAPHST, "GraphST not installed")
class TestUtilities(unittest.TestCase):
    """Tests for utility functions."""

    def test_search_res(self):
        """Test resolution search."""
        from sklearn.decomposition import PCA

        adata = create_test_data(n_spots=100)

        model = GraphST(
            adata=adata,
            device=torch.device('cpu'),
            epochs=50,
            random_seed=42
        )
        adata = model.train()

        # search_res requires emb_pca; compute it manually
        pca = PCA(n_components=20, random_state=42)
        adata.obsm['emb_pca'] = pca.fit_transform(adata.obsm['emb'].copy())

        res = search_res(
            adata,
            n_clusters=3,
            method='leiden',
            use_rep='emb_pca',
            start=0.1,
            end=3.0,
            increment=0.05
        )

        self.assertIsInstance(res, float)
        self.assertGreater(res, 0)


# ================================================================================
# Test Suite 6: Edge Cases
# ================================================================================

class TestEdgeCases(unittest.TestCase):
    """Tests for edge cases and error handling."""

    def test_minimal_dataset(self):
        """Test with minimal dataset."""
        adata = create_test_data(n_spots=20, n_genes=50)
        self.assertEqual(adata.n_obs, 20)
        self.assertEqual(adata.n_vars, 50)

    def test_single_domain(self):
        """Test with single domain."""
        adata = create_test_data(n_spots=50)
        adata.obs['domain_gt'] = 'Domain_0'
        self.assertEqual(adata.obs['domain_gt'].nunique(), 1)

    def test_many_domains(self):
        """Test with many domains."""
        adata = create_test_data(n_spots=100, n_domains=10)
        self.assertGreater(adata.obs['domain_gt'].nunique(), 1)


# ================================================================================
# Test Suite 7: Data Export
# ================================================================================

class TestDataExport(unittest.TestCase):
    """Tests for data export functionality."""

    def test_export_domains(self):
        """Test domain export to CSV."""
        adata = create_test_data(n_spots=50)
        adata.obs['domain'] = np.random.choice(['A', 'B', 'C'], 50)

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, 'domains.csv')
            adata.obs[['domain']].to_csv(filepath)
            self.assertTrue(os.path.exists(filepath))

            # Load and verify
            loaded = pd.read_csv(filepath, index_col=0)
            self.assertEqual(len(loaded), 50)

    def test_export_embeddings(self):
        """Test embedding export."""
        adata = create_test_data(n_spots=50)
        adata.obsm['emb'] = np.random.randn(50, 64)

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, 'embeddings.csv')
            pd.DataFrame(adata.obsm['emb'], index=adata.obs_names).to_csv(filepath)
            self.assertTrue(os.path.exists(filepath))

    def test_save_h5ad(self):
        """Test AnnData saving."""
        adata = create_test_data(n_spots=50)

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, 'adata.h5ad')
            adata.write_h5ad(filepath)
            self.assertTrue(os.path.exists(filepath))

            # Load and verify
            loaded = sc.read_h5ad(filepath)
            self.assertEqual(loaded.n_obs, 50)


# ================================================================================
# Main
# ================================================================================

if __name__ == '__main__':
    print("=" * 70)
    print("GraphST Skill Unit Tests")
    print("=" * 70)

    if HAS_GRAPHST:
        print("GraphST package: INSTALLED")
        print("Core tests: ENABLED\n")
    else:
        print("GraphST package: NOT INSTALLED")
        print("Core tests: SKIPPED")
        print("Install with: pip install GraphST\n")

    # Run tests
    unittest.main(verbosity=2)
