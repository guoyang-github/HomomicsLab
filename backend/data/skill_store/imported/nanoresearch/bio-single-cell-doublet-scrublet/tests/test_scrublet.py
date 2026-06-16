"""Unit tests for Scrublet doublet detection skill."""

import unittest
import numpy as np
import pandas as pd
import scanpy as sc


class TestScrublet(unittest.TestCase):
    """Test Scrublet doublet detection using native API."""

    def setUp(self):
        """Create test data."""
        np.random.seed(42)
        n_cells = 200
        n_genes = 500

        self.adata = sc.AnnData(
            X=np.random.poisson(2, (n_cells, n_genes)),
            obs=pd.DataFrame(index=[f"cell_{i}" for i in range(n_cells)]),
            var=pd.DataFrame(index=[f"GENE_{i}" for i in range(n_genes)])
        )

    def test_scrublet_initialization(self):
        """Test Scrublet class initialization."""
        try:
            import scrublet as scr

            scrub = scr.Scrublet(
                self.adata.X,
                expected_doublet_rate=0.1,
                sim_doublet_ratio=2.0,
                random_state=42
            )

            self.assertIsNotNone(scrub)
            self.assertEqual(scrub.expected_doublet_rate, 0.1)
            self.assertEqual(scrub.sim_doublet_ratio, 2.0)

        except ImportError:
            self.skipTest("scrublet not installed")

    def test_scrub_doublets(self):
        """Test scrub_doublets method."""
        try:
            import scrublet as scr

            scrub = scr.Scrublet(self.adata.X, expected_doublet_rate=0.1)

            doublet_scores, predicted_doublets = scrub.scrub_doublets(
                min_counts=2,
                min_cells=3,
                min_gene_variability_pctl=85,
                n_prin_comps=30,
                verbose=False
            )

            self.assertEqual(len(doublet_scores), self.adata.n_obs)
            self.assertEqual(len(predicted_doublets), self.adata.n_obs)
            self.assertTrue(all(0 <= s <= 1 for s in doublet_scores))
            self.assertTrue(all(isinstance(p, (bool, np.bool_)) for p in predicted_doublets))
            self.assertIsNotNone(scrub.threshold_)

        except ImportError:
            self.skipTest("scrublet not installed")

    def test_call_doublets_manual_threshold(self):
        """Test manual threshold selection."""
        try:
            import scrublet as scr

            scrub = scr.Scrublet(self.adata.X, expected_doublet_rate=0.1)
            scrub.scrub_doublets(verbose=False)

            # Test manual threshold
            scrub.call_doublets(threshold=0.25, verbose=False)
            manual_predictions = scrub.predicted_doublets_

            self.assertEqual(len(manual_predictions), self.adata.n_obs)
            self.assertTrue(all(isinstance(p, (bool, np.bool_)) for p in manual_predictions))

        except ImportError:
            self.skipTest("scrublet not installed")

    def test_expected_doublet_rate_calculation(self):
        """Test expected doublet rate calculation formula."""
        n_cells = 5000
        expected_rate = n_cells / 1000 * 0.008
        self.assertAlmostEqual(expected_rate, 0.04, places=5)

    def test_results_added_to_anndata(self):
        """Test adding results to AnnData."""
        try:
            import scrublet as scr

            scrub = scr.Scrublet(self.adata.X, expected_doublet_rate=0.1)
            doublet_scores, predicted_doublets = scrub.scrub_doublets(verbose=False)

            # Add to AnnData
            self.adata.obs['doublet_score'] = doublet_scores
            self.adata.obs['predicted_doublet'] = predicted_doublets

            self.assertIn('doublet_score', self.adata.obs.columns)
            self.assertIn('predicted_doublet', self.adata.obs.columns)

        except ImportError:
            self.skipTest("scrublet not installed")

    def test_filter_doublets(self):
        """Test filtering doublets from AnnData."""
        self.adata.obs['predicted_doublet'] = np.random.choice([True, False], self.adata.n_obs)

        # Filter
        adata_filtered = self.adata[~self.adata.obs['predicted_doublet']].copy()

        self.assertLessEqual(adata_filtered.n_obs, self.adata.n_obs)
        self.assertEqual(
            adata_filtered.n_obs,
            sum(~self.adata.obs['predicted_doublet'])
        )

    def test_scrublet_attributes(self):
        """Test accessing Scrublet attributes after run."""
        try:
            import scrublet as scr

            scrub = scr.Scrublet(self.adata.X, expected_doublet_rate=0.1)
            scrub.scrub_doublets(verbose=False)

            # Check attributes exist
            self.assertIsNotNone(scrub.doublet_scores_obs_)
            self.assertIsNotNone(scrub.doublet_scores_sim_)
            self.assertIsNotNone(scrub.doublet_parents_)
            self.assertIsNotNone(scrub.threshold_)
            self.assertIsNotNone(scrub.z_scores_)

            # Check shapes
            self.assertEqual(len(scrub.doublet_scores_obs_), self.adata.n_obs)
            self.assertEqual(scrub.doublet_parents_.shape[1], 2)

        except ImportError:
            self.skipTest("scrublet not installed")

    def test_different_preprocessing_params(self):
        """Test with different preprocessing parameters."""
        try:
            import scrublet as scr

            scrub = scr.Scrublet(self.adata.X, expected_doublet_rate=0.1)

            # Test with different parameters (using smaller n_prin_comps to avoid PCA dimension issues)
            doublet_scores, predicted_doublets = scrub.scrub_doublets(
                min_counts=2,
                min_cells=3,
                min_gene_variability_pctl=85,
                n_prin_comps=20,
                log_transform=False,
                mean_center=True,
                normalize_variance=True,
                verbose=False
            )

            self.assertEqual(len(doublet_scores), self.adata.n_obs)

        except ImportError:
            self.skipTest("scrublet not installed")

    def test_approx_neighbors(self):
        """Test with approximate vs exact neighbors."""
        try:
            import scrublet as scr

            # With approximate neighbors
            scrub_approx = scr.Scrublet(self.adata.X[:100], expected_doublet_rate=0.1)
            scores_approx, _ = scrub_approx.scrub_doublets(
                use_approx_neighbors=True,
                verbose=False
            )

            # With exact neighbors
            scrub_exact = scr.Scrublet(self.adata.X[:100], expected_doublet_rate=0.1)
            scores_exact, _ = scrub_exact.scrub_doublets(
                use_approx_neighbors=False,
                verbose=False
            )

            self.assertEqual(len(scores_approx), 100)
            self.assertEqual(len(scores_exact), 100)

        except ImportError:
            self.skipTest("scrublet not installed")


class TestScrubletVisualization(unittest.TestCase):
    """Test Scrublet visualization methods."""

    def setUp(self):
        """Create test data."""
        np.random.seed(42)
        self.adata = sc.AnnData(
            X=np.random.poisson(2, (100, 200)),
            obs=pd.DataFrame(index=[f"cell_{i}" for i in range(100)]),
            var=pd.DataFrame(index=[f"GENE_{i}" for i in range(200)])
        )

    def test_plot_histogram(self):
        """Test histogram plotting."""
        try:
            import scrublet as scr
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt

            scrub = scr.Scrublet(self.adata.X, expected_doublet_rate=0.1)
            # Use smaller n_prin_comps for small test dataset
            scrub.scrub_doublets(n_prin_comps=15, verbose=False)

            # Should not raise error
            fig, ax = plt.subplots(1, 1, figsize=(8, 3))
            scrub.plot_histogram()
            plt.close()

        except ImportError:
            self.skipTest("scrublet or matplotlib not installed")


class TestDataValidation(unittest.TestCase):
    """Test data validation utilities."""

    def test_sparse_matrix_input(self):
        """Test with sparse matrix input."""
        try:
            import scrublet as scr
            import scipy.sparse

            # Create sparse matrix (use larger dimensions to ensure enough features for PCA)
            sparse_counts = scipy.sparse.csc_matrix(
                np.random.poisson(2, (150, 300))
            )

            scrub = scr.Scrublet(sparse_counts, expected_doublet_rate=0.1)
            # Use smaller n_prin_comps for small test dataset
            scores, predictions = scrub.scrub_doublets(n_prin_comps=15, verbose=False)

            self.assertEqual(len(scores), 150)

        except ImportError:
            self.skipTest("scrublet not installed")

    def test_dense_array_input(self):
        """Test with dense array input."""
        try:
            import scrublet as scr

            # Use larger dimensions to ensure enough features for PCA
            dense_counts = np.random.poisson(2, (150, 300))

            scrub = scr.Scrublet(dense_counts, expected_doublet_rate=0.1)
            # Use smaller n_prin_comps for small test dataset
            scores, predictions = scrub.scrub_doublets(n_prin_comps=15, verbose=False)

            self.assertEqual(len(scores), 150)

        except ImportError:
            self.skipTest("scrublet not installed")


if __name__ == '__main__':
    unittest.main()
