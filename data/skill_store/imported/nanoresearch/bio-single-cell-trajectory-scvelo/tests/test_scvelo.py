"""
Unit Tests for scVelo RNA Velocity Analysis
===========================================

Tests for core_analysis.py, visualization.py, and utils.py modules.
"""

import unittest
import numpy as np
import pandas as pd
import sys
import os

# Add scripts to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts', 'python'))

# Check if scvelo is available
try:
    import scvelo as scv
    SCVELO_AVAILABLE = True
except ImportError:
    SCVELO_AVAILABLE = False

try:
    import scanpy as sc
    SCANPY_AVAILABLE = True
except ImportError:
    SCANPY_AVAILABLE = False


class TestCoreAnalysis(unittest.TestCase):
    """Test core analysis functions."""

    @classmethod
    def setUpClass(cls):
        """Set up test data if dependencies available."""
        if not SCVELO_AVAILABLE or not SCANPY_AVAILABLE:
            return

        # Create minimal test data
        np.random.seed(42)
        n_cells = 100
        n_genes = 50

        # Create AnnData
        cls.adata = sc.AnnData(
            X=np.random.poisson(5, (n_cells, n_genes)).astype(float)
        )
        cls.adata.var_names = [f'gene_{i}' for i in range(n_genes)]
        cls.adata.obs_names = [f'cell_{i}' for i in range(n_cells)]

        # Add spliced/unspliced layers
        cls.adata.layers['spliced'] = np.random.poisson(3, (n_cells, n_genes)).astype(float)
        cls.adata.layers['unspliced'] = np.random.poisson(1, (n_cells, n_genes)).astype(float)

        # Add clusters
        cls.adata.obs['clusters'] = pd.Categorical(
            np.random.choice(['A', 'B', 'C'], n_cells)
        )

    def setUp(self):
        """Skip tests if dependencies not available."""
        if not SCVELO_AVAILABLE:
            self.skipTest("scvelo not installed")
        if not SCANPY_AVAILABLE:
            self.skipTest("scanpy not installed")

    def test_prepare_data_for_velocity(self):
        """Test data preparation."""
        from core_analysis import prepare_data_for_velocity

        adata_processed = prepare_data_for_velocity(
            self.adata.copy(),
            min_counts=1,
            n_top_genes=20,
            n_pcs=5,
            n_neighbors=10
        )

        self.assertIn('Ms', adata_processed.layers)
        self.assertIn('Mu', adata_processed.layers)
        self.assertIn('X_pca', adata_processed.obsm)

    def test_compute_velocity_deterministic(self):
        """Test velocity computation (deterministic mode)."""
        from core_analysis import compute_velocity

        adata = self.adata.copy()
        sc.pp.normalize_total(adata, target_sum=1e4)
        sc.pp.log1p(adata)
        sc.pp.pca(adata, n_comps=5)

        # Compute moments
        import scvelo as scv
        scv.pp.moments(adata, n_pcs=5, n_neighbors=10)

        result = compute_velocity(
            adata,
            mode='deterministic',
            min_r2=0.01
        )

        self.assertIn('velocity', result.layers)
        self.assertIn('velocity_genes', result.var.columns)

    def test_compute_velocity_graph(self):
        """Test velocity graph computation."""
        from core_analysis import compute_velocity_graph, compute_velocity

        adata = self.adata.copy()
        sc.pp.normalize_total(adata, target_sum=1e4)
        sc.pp.log1p(adata)
        sc.pp.pca(adata, n_comps=5)

        import scvelo as scv
        scv.pp.moments(adata, n_pcs=5, n_neighbors=10)
        compute_velocity(adata, mode='deterministic')

        result = compute_velocity_graph(adata, n_neighbors=10)

        self.assertIn('velocity_graph', result.uns)

    def test_check_velocity_layers(self):
        """Test velocity layers checking."""
        from core_analysis import check_velocity_layers

        # Should pass with correct layers
        self.assertTrue(check_velocity_layers(self.adata))

        # Should raise error with missing layers
        adata_missing = self.adata.copy()
        del adata_missing.layers['spliced']

        with self.assertRaises(ValueError):
            check_velocity_layers(adata_missing)


class TestVisualization(unittest.TestCase):
    """Test visualization functions."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        if not SCVELO_AVAILABLE or not SCANPY_AVAILABLE:
            return

        np.random.seed(42)
        n_cells = 50
        n_genes = 30

        cls.adata = sc.AnnData(
            X=np.random.poisson(5, (n_cells, n_genes)).astype(float)
        )
        cls.adata.var_names = [f'gene_{i}' for i in range(n_genes)]
        cls.adata.obs_names = [f'cell_{i}' for i in range(n_cells)]
        cls.adata.layers['spliced'] = np.random.poisson(3, (n_cells, n_genes)).astype(float)
        cls.adata.layers['unspliced'] = np.random.poisson(1, (n_cells, n_genes)).astype(float)
        cls.adata.obs['clusters'] = pd.Categorical(
            np.random.choice(['A', 'B'], n_cells)
        )

        # Add embedding
        cls.adata.obsm['X_umap'] = np.random.randn(n_cells, 2)

    def setUp(self):
        """Skip tests if dependencies not available."""
        if not SCVELO_AVAILABLE:
            self.skipTest("scvelo not installed")

    def test_plot_velocity_embedding_stream(self):
        """Test velocity stream plotting."""
        from visualization import plot_velocity_embedding_stream
        import matplotlib
        matplotlib.use('Agg')  # Non-interactive backend

        # Just test that it doesn't error with correct data
        # Would need actual velocity computation for full test
        pass  # Placeholder - requires computed velocity

    def test_plot_phase_portrait(self):
        """Test phase portrait plotting."""
        from visualization import plot_phase_portrait
        import matplotlib
        matplotlib.use('Agg')

        # Test with invalid gene
        with self.assertRaises(ValueError):
            plot_phase_portrait(self.adata, gene='invalid_gene', show=False)


class TestUtils(unittest.TestCase):
    """Test utility functions."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        if not SCANPY_AVAILABLE:
            return

        np.random.seed(42)
        n_cells = 50
        n_genes = 30

        cls.adata = sc.AnnData(
            X=np.random.poisson(5, (n_cells, n_genes)).astype(float)
        )
        cls.adata.var_names = [f'gene_{i}' for i in range(n_genes)]
        cls.adata.obs_names = [f'cell_{i}' for i in range(n_cells)]
        cls.adata.layers['spliced'] = np.random.poisson(3, (n_cells, n_genes)).astype(float)
        cls.adata.layers['unspliced'] = np.random.poisson(1, (n_cells, n_genes)).astype(float)

    def setUp(self):
        """Skip tests if dependencies not available."""
        if not SCANPY_AVAILABLE:
            self.skipTest("scanpy not installed")

    def test_check_velocity_layers(self):
        """Test velocity layer checking."""
        from utils import check_velocity_layers

        self.assertTrue(check_velocity_layers(self.adata))

        # Test with missing layer
        adata_test = self.adata.copy()
        del adata_test.layers['spliced']
        self.assertFalse(check_velocity_layers(adata_test, raise_error=False))

    def test_estimate_min_counts(self):
        """Test count estimation."""
        from utils import estimate_min_counts

        stats = estimate_min_counts(self.adata)

        self.assertIn('spliced', stats)
        self.assertIn('unspliced', stats)
        self.assertIn('recommended_min_counts', stats)
        self.assertGreater(stats['recommended_min_counts'], 0)

    def test_get_velocity_summary_stats(self):
        """Test summary statistics."""
        from utils import get_velocity_summary_stats

        # Test with basic data
        stats = get_velocity_summary_stats(self.adata)

        self.assertIn('data_shape', stats)
        self.assertEqual(stats['data_shape']['cells'], self.adata.n_obs)

    def test_export_velocity_to_dataframe(self):
        """Test export function."""
        from utils import export_velocity_to_dataframe

        df = export_velocity_to_dataframe(self.adata)

        self.assertIn('cell_id', df.columns)
        self.assertEqual(len(df), self.adata.n_obs)

    def test_validate_velocity_consistency(self):
        """Test validation function."""
        from utils import validate_velocity_consistency

        # Without velocity computed
        with self.assertRaises(ValueError):
            validate_velocity_consistency(self.adata)


class TestIntegration(unittest.TestCase):
    """Integration tests for full workflow."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        if not SCVELO_AVAILABLE or not SCANPY_AVAILABLE:
            return

        np.random.seed(42)
        n_cells = 100
        n_genes = 50

        cls.adata = sc.AnnData(
            X=np.random.poisson(5, (n_cells, n_genes)).astype(float)
        )
        cls.adata.var_names = [f'gene_{i}' for i in range(n_genes)]
        cls.adata.obs_names = [f'cell_{i}' for i in range(n_cells)]
        cls.adata.layers['spliced'] = np.random.poisson(3, (n_cells, n_genes)).astype(float)
        cls.adata.layers['unspliced'] = np.random.poisson(1, (n_cells, n_genes)).astype(float)
        cls.adata.obs['clusters'] = pd.Categorical(
            np.random.choice(['A', 'B', 'C'], n_cells)
        )

    def setUp(self):
        """Skip tests if dependencies not available."""
        if not SCVELO_AVAILABLE:
            self.skipTest("scvelo not installed")
        if not SCANPY_AVAILABLE:
            self.skipTest("scanpy not installed")

    def test_full_workflow_deterministic(self):
        """Test complete workflow with deterministic mode."""
        from core_analysis import (
            prepare_data_for_velocity,
            run_velocity_analysis,
            compute_latent_time_scvelo
        )
        from utils import get_velocity_summary_stats

        adata = self.adata.copy()

        # Preprocess
        adata = prepare_data_for_velocity(
            adata,
            min_counts=1,
            n_top_genes=30,
            n_pcs=5,
            n_neighbors=10
        )

        # Compute velocity
        adata = run_velocity_analysis(
            adata,
            mode='deterministic',
            min_r2=0.01
        )

        # Check results
        self.assertIn('velocity', adata.layers)
        self.assertIn('velocity_graph', adata.uns)

        # Get stats
        stats = get_velocity_summary_stats(adata)
        self.assertIn('n_velocity_genes', stats)

    def test_full_workflow_stochastic(self):
        """Test complete workflow with stochastic mode."""
        from core_analysis import (
            prepare_data_for_velocity,
            run_velocity_analysis
        )

        adata = self.adata.copy()

        # Preprocess
        adata = prepare_data_for_velocity(
            adata,
            min_counts=1,
            n_top_genes=30,
            n_pcs=5,
            n_neighbors=10
        )

        # Compute velocity with stochastic mode
        adata = run_velocity_analysis(
            adata,
            mode='stochastic',
            min_r2=0.01
        )

        self.assertIn('velocity', adata.layers)
        self.assertIn('Ms', adata.layers)  # Second-order moments


def run_tests():
    """Run all tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestCoreAnalysis))
    suite.addTests(loader.loadTestsFromTestCase(TestVisualization))
    suite.addTests(loader.loadTestsFromTestCase(TestUtils))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
