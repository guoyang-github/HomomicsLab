#!/usr/bin/env python
"""
Unit Tests for SOLO Doublet Detection Module

Run with: python test_solo.py
"""

import unittest
import numpy as np
import pandas as pd
import scanpy as sc
from scipy.sparse import csr_matrix
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../scripts/python'))

from utils import (
    validate_adata_for_solo,
    preprocess_for_solo,
    estimate_expected_doublet_rate,
    optimize_threshold_range,
    estimate_optimal_threshold,
    merge_predictions_with_adata,
    compare_predictions,
    ensemble_doublet_calls,
    create_summary_report
)
from core_analysis import (
    filter_doublets,
    add_predictions_to_adata
)


class TestDataValidation(unittest.TestCase):
    """Test data validation functions."""

    @classmethod
    def setUpClass(cls):
        """Create test data."""
        np.random.seed(42)
        n_cells = 200
        n_genes = 500

        # Create raw count-like data
        X = np.random.poisson(2, size=(n_cells, n_genes))

        cls.adata = sc.AnnData(
            X=csr_matrix(X),
            obs=pd.DataFrame(index=[f'cell_{i}' for i in range(n_cells)]),
            var=pd.DataFrame(index=[f'gene_{i}' for i in range(n_genes)])
        )

    def test_validate_adata_valid(self):
        """Test validation with valid data."""
        result = validate_adata_for_solo(self.adata, require_raw=False)
        self.assertTrue(result)

    def test_validate_adata_too_few_cells(self):
        """Test validation with too few cells."""
        small_adata = self.adata[:50].copy()
        with self.assertRaises(ValueError):
            validate_adata_for_solo(small_adata, min_cells=100)

    def test_validate_adata_wrong_type(self):
        """Test validation with wrong type."""
        with self.assertRaises(TypeError):
            validate_adata_for_solo("not anndata")

    def test_validate_adata_large_sparse_matrix(self):
        """Test validation on large sparse matrix doesn't OOM."""
        # Create a matrix with >1M non-zero entries to trigger sampling path
        n_cells = 10000
        n_genes = 1000
        X = np.random.poisson(3, size=(n_cells, n_genes))
        large_adata = sc.AnnData(
            X=csr_matrix(X),
            obs=pd.DataFrame(index=[f'cell_{i}' for i in range(n_cells)]),
            var=pd.DataFrame(index=[f'gene_{i}' for i in range(n_genes)])
        )
        # Should complete without excessive memory use
        result = validate_adata_for_solo(large_adata, require_raw=True)
        self.assertTrue(result)


class TestPreprocessing(unittest.TestCase):
    """Test preprocessing functions."""

    @classmethod
    def setUpClass(cls):
        """Create test data."""
        np.random.seed(42)
        n_cells = 200
        n_genes = 500
        X = np.random.poisson(2, size=(n_cells, n_genes))

        # Mix human and mouse MT gene names
        var_names = [f'gene_{i}' for i in range(n_genes)]
        var_names[0] = 'MT-ATP6'   # human
        var_names[1] = 'mt-Co1'    # mouse
        var_names[2] = 'MT-CO2'    # human
        var_names[3] = 'mt-ND1'    # mouse

        cls.adata = sc.AnnData(
            X=csr_matrix(X),
            obs=pd.DataFrame(index=[f'cell_{i}' for i in range(n_cells)]),
            var=pd.DataFrame(index=var_names)
        )

    def test_preprocess_mt_human_and_mouse(self):
        """Test that both human and mouse MT genes are detected."""
        adata = preprocess_for_solo(self.adata.copy(), inplace=False)
        mt_genes = adata.var['mt'].sum()
        self.assertEqual(mt_genes, 4)

    def test_preprocess_filtering(self):
        """Test basic filtering works."""
        adata = preprocess_for_solo(
            self.adata.copy(),
            min_genes=1,
            min_cells=1,
            inplace=False
        )
        self.assertGreaterEqual(adata.n_obs, 1)
        self.assertGreaterEqual(adata.n_vars, 1)

    def test_preprocess_max_genes_filter(self):
        """Test max_genes QC filter."""
        adata = preprocess_for_solo(
            self.adata.copy(),
            min_genes=1,
            min_cells=1,
            max_genes=10,
            inplace=False
        )
        # Most cells should have more than 10 genes expressed, so many are filtered
        self.assertLess(adata.n_obs, self.adata.n_obs)


class TestDoubletRateEstimation(unittest.TestCase):
    """Test doublet rate estimation functions."""

    def test_estimate_expected_rate_10x(self):
        """Test 10x doublet rate estimation."""
        rate = estimate_expected_doublet_rate(10000, method='10x')
        self.assertGreater(rate, 0)
        self.assertLess(rate, 0.5)

    def test_estimate_expected_rate_dropseq(self):
        """Test Drop-seq rate estimation."""
        rate = estimate_expected_doublet_rate(5000, method='dropseq')
        self.assertGreater(rate, 0)

    def test_rate_capped(self):
        """Test that rate is capped at reasonable maximum."""
        rate = estimate_expected_doublet_rate(100000, method='10x')
        self.assertLessEqual(rate, 0.5)


class TestThresholdOptimization(unittest.TestCase):
    """Test threshold optimization functions."""

    @classmethod
    def setUpClass(cls):
        """Create mock predictions."""
        np.random.seed(42)
        cls.predictions = pd.DataFrame({
            'doublet': np.concatenate([
                np.random.beta(2, 5, 800),   # Singlets
                np.random.beta(5, 2, 200)    # Doublets
            ]),
            'singlet': np.concatenate([
                np.random.beta(5, 2, 800),
                np.random.beta(2, 5, 200)
            ])
        })

    def test_optimize_threshold_range(self):
        """Test threshold range optimization."""
        thresholds = [0.3, 0.5, 0.7]
        result = optimize_threshold_range(self.predictions, thresholds)

        self.assertIsInstance(result, pd.DataFrame)
        self.assertEqual(len(result), len(thresholds))
        self.assertIn('threshold', result.columns)
        self.assertIn('n_doublets', result.columns)

    def test_threshold_results_sorted(self):
        """Test that higher thresholds give fewer doublets."""
        thresholds = [0.3, 0.5, 0.7]
        result = optimize_threshold_range(self.predictions, thresholds)

        # Higher threshold should give fewer doublets
        self.assertGreaterEqual(
            result.loc[result['threshold'] == 0.3, 'n_doublets'].values[0],
            result.loc[result['threshold'] == 0.7, 'n_doublets'].values[0]
        )

    def test_estimate_optimal_threshold_quantile(self):
        """Test quantile-based threshold estimation."""
        thresh = estimate_optimal_threshold(self.predictions, method='quantile')
        self.assertGreater(thresh, 0)
        self.assertLess(thresh, 1)

    def test_estimate_optimal_threshold_otsu_fallback(self):
        """Test Otsu method falls back to quantile when skimage unavailable."""
        thresh = estimate_optimal_threshold(self.predictions, method='otsu')
        self.assertGreater(thresh, 0)
        self.assertLess(thresh, 1)


class TestCoreAnalysis(unittest.TestCase):
    """Test core analysis functions."""

    @classmethod
    def setUpClass(cls):
        """Create test data and predictions."""
        np.random.seed(42)
        n_cells = 100
        n_genes = 200
        X = np.random.poisson(2, size=(n_cells, n_genes))

        cls.adata = sc.AnnData(
            X=csr_matrix(X),
            obs=pd.DataFrame(index=[f'cell_{i}' for i in range(n_cells)]),
            var=pd.DataFrame(index=[f'gene_{i}' for i in range(n_genes)])
        )

        cls.predictions = pd.DataFrame({
            'singlet': np.random.uniform(0.3, 0.9, n_cells),
            'doublet': np.random.uniform(0.1, 0.7, n_cells),
            'prediction_label': np.random.choice(['singlet', 'doublet'], n_cells),
            'prediction': np.random.choice([0, 1], n_cells)
        }, index=cls.adata.obs_names)
        # Ensure probabilities sum to ~1
        row_sums = cls.predictions[['singlet', 'doublet']].sum(axis=1)
        cls.predictions['singlet'] /= row_sums
        cls.predictions['doublet'] /= row_sums

    def test_filter_doublets_with_label_column(self):
        """Test filter using prediction_label column."""
        adata_clean = filter_doublets(
            self.adata, self.predictions, inplace=False
        )
        self.assertIsInstance(adata_clean, sc.AnnData)
        self.assertLessEqual(adata_clean.n_obs, self.adata.n_obs)

    def test_filter_doublets_with_numeric_column(self):
        """Test filter using numeric prediction column."""
        preds = self.predictions.copy()
        preds.drop('prediction_label', axis=1, inplace=True)
        adata_clean = filter_doublets(self.adata, preds, inplace=False)
        self.assertIsInstance(adata_clean, sc.AnnData)

    def test_filter_doublets_with_score_only(self):
        """Test filter using only doublet score."""
        preds = pd.DataFrame({'doublet': self.predictions['doublet']})
        adata_clean = filter_doublets(self.adata, preds, threshold=0.5, inplace=False)
        self.assertIsInstance(adata_clean, sc.AnnData)

    def test_filter_doublets_inplace(self):
        """Test inplace filtering returns filtered result."""
        adata_copy = self.adata.copy()
        n_before = adata_copy.n_obs
        result = filter_doublets(adata_copy, self.predictions, inplace=True)
        # inplace=True returns the filtered result (slicing creates new object)
        self.assertLessEqual(result.n_obs, n_before)
        # Original should be unchanged since AnnData slicing always returns a new object
        self.assertEqual(adata_copy.n_obs, n_before)

    def test_add_predictions_to_adata(self):
        """Test adding predictions to AnnData."""
        adata = self.adata.copy()
        add_predictions_to_adata(adata, self.predictions, doublet_threshold=0.5)

        self.assertIn('solo_doublet_score', adata.obs.columns)
        self.assertIn('solo_singlet_score', adata.obs.columns)
        self.assertIn('solo_prediction', adata.obs.columns)
        self.assertEqual(adata.uns['solo_threshold'], 0.5)

    def test_add_predictions_without_label(self):
        """Test adding predictions when no label column exists."""
        adata = self.adata.copy()
        preds = self.predictions[['singlet', 'doublet']].copy()
        add_predictions_to_adata(adata, preds, doublet_threshold=0.5)

        self.assertIn('solo_prediction', adata.obs.columns)
        self.assertTrue(
            set(adata.obs['solo_prediction'].unique()).issubset({'singlet', 'doublet'})
        )


class TestMergePredictions(unittest.TestCase):
    """Test merge_predictions_with_adata."""

    @classmethod
    def setUpClass(cls):
        np.random.seed(42)
        n_cells = 50
        n_genes = 100
        X = np.random.poisson(2, size=(n_cells, n_genes))
        cls.adata = sc.AnnData(
            X=csr_matrix(X),
            obs=pd.DataFrame(index=[f'cell_{i}' for i in range(n_cells)]),
            var=pd.DataFrame(index=[f'gene_{i}' for i in range(n_genes)])
        )

    def test_merge_with_aligned_index(self):
        """Test merge when predictions index matches adata."""
        preds = pd.DataFrame({
            'doublet': np.random.uniform(0, 1, 50),
            'singlet': np.random.uniform(0, 1, 50)
        }, index=self.adata.obs_names)

        merged = merge_predictions_with_adata(self.adata, preds, prefix='solo')
        self.assertIn('solo_doublet_score', merged.obs.columns)

    def test_merge_with_reordered_index(self):
        """Test merge reorders predictions to match adata index."""
        shuffled_names = list(self.adata.obs_names)
        np.random.shuffle(shuffled_names)
        preds = pd.DataFrame({
            'doublet': np.random.uniform(0, 1, 50),
            'singlet': np.random.uniform(0, 1, 50)
        }, index=shuffled_names)

        merged = merge_predictions_with_adata(self.adata, preds, prefix='solo')
        self.assertIn('solo_doublet_score', merged.obs.columns)
        # Values should be aligned with adata index, not preds index
        pd.testing.assert_index_equal(merged.obs.index, self.adata.obs.index)


class TestComparisonFunctions(unittest.TestCase):
    """Test comparison functions."""

    @classmethod
    def setUpClass(cls):
        """Create mock predictions."""
        np.random.seed(42)

        cls.solo_preds = pd.DataFrame({
            'doublet': np.random.uniform(0, 1, 100),
            'singlet': np.random.uniform(0, 1, 100)
        })
        cls.solo_preds['prediction'] = (cls.solo_preds['doublet'] > 0.5).astype(int)

        cls.other_preds = pd.DataFrame({
            'prediction': np.random.choice([0, 1], 100)
        })

    def test_compare_predictions_structure(self):
        """Test comparison result structure."""
        comparison = compare_predictions(
            self.solo_preds,
            self.other_preds,
            other_name='test_method'
        )

        self.assertIn('agreement', comparison)
        self.assertIn('confusion_matrix', comparison)
        self.assertIn('both_doublet', comparison)
        self.assertIn('both_singlet', comparison)

    def test_ensemble_doublet_calls(self):
        """Test ensemble of multiple methods."""
        preds_dict = {
            'solo': self.solo_preds,
            'other': self.other_preds
        }
        ensemble = ensemble_doublet_calls(preds_dict)

        self.assertIn('ensemble_score', ensemble.columns)
        self.assertIn('ensemble_prediction', ensemble.columns)
        self.assertIn('ensemble_label', ensemble.columns)
        self.assertEqual(len(ensemble), 100)

    def test_ensemble_with_weights(self):
        """Test ensemble with custom weights."""
        preds_dict = {
            'solo': self.solo_preds,
            'other': self.other_preds
        }
        weights = {'solo': 0.7, 'other': 0.3}
        ensemble = ensemble_doublet_calls(preds_dict, weights=weights)

        self.assertIn('ensemble_score', ensemble.columns)
        self.assertEqual(len(ensemble), 100)


class TestReportGeneration(unittest.TestCase):
    """Test summary report generation."""

    @classmethod
    def setUpClass(cls):
        np.random.seed(42)
        cls.predictions = pd.DataFrame({
            'doublet': np.concatenate([
                np.random.beta(2, 5, 800),
                np.random.beta(5, 2, 200)
            ])
        })

    def test_create_summary_report_structure(self):
        """Test report contains expected sections."""
        report = create_summary_report(self.predictions, threshold=0.5)
        self.assertIn('SOLO Doublet Detection Report', report)
        self.assertIn('Total cells analyzed', report)
        self.assertIn('Predicted doublets', report)

    def test_create_summary_report_saves_file(self):
        """Test report can be saved to file."""
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            path = f.name
        try:
            create_summary_report(self.predictions, threshold=0.5, output_path=path)
            self.assertTrue(os.path.exists(path))
            with open(path, 'r') as f:
                content = f.read()
            self.assertIn('SOLO Doublet Detection Report', content)
        finally:
            os.unlink(path)


if __name__ == '__main__':
    unittest.main(verbosity=2)
