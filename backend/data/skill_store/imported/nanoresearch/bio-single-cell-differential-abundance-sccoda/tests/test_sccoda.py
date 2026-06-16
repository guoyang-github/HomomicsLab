#!/usr/bin/env python3
"""Unit tests for scCODA differential abundance analysis.

Tests cover:
- Data preparation functions
- Core analysis workflow
- Utility functions
- Visualization functions
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd
import scanpy as sc
from anndata import AnnData

# Add parent directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../scripts/python'))

from data_preparation import (
    prepare_sccoda_data,
    check_data_requirements,
    from_cell_counts_df,
    subset_sccoda_data,
    get_composition_summary,
)
from utils import (
    validate_sccoda_data,
    summarize_results,
    get_significant_cell_types,
    export_results,
    create_analysis_report,
)


class TestDataPreparation(unittest.TestCase):
    """Test data preparation functions."""

    def setUp(self):
        """Create test data."""
        np.random.seed(42)
        n_cells = 200
        n_genes = 50

        self.adata = AnnData(
            X=np.random.lognormal(3, 1, (n_cells, n_genes)),
            obs=pd.DataFrame({
                'cell_type': np.random.choice(['A', 'B', 'C', 'D'], n_cells),
                'sample_id': np.random.choice(['s1', 's2', 's3', 's4'], n_cells),
                'condition': np.random.choice(['ctrl', 'treat'], n_cells),
                'batch': np.random.choice(['A', 'B'], n_cells),
            }, index=[f"cell_{i}" for i in range(n_cells)]),
            var=pd.DataFrame(index=[f"gene_{i}" for i in range(n_genes)])
        )

    def test_prepare_sccoda_data(self):
        """Test compositional data preparation."""
        sccoda_data = prepare_sccoda_data(
            self.adata,
            sample_key='sample_id',
            cell_type_key='cell_type',
            condition_key='condition',
            covariate_columns=['batch']
        )

        # Check dimensions
        self.assertEqual(sccoda_data.n_obs, 4)  # 4 samples
        self.assertEqual(sccoda_data.n_vars, 4)  # 4 cell types

        # Check covariates
        self.assertIn('condition', sccoda_data.obs.columns)
        self.assertIn('batch', sccoda_data.obs.columns)

    def test_prepare_sccoda_data_missing_column(self):
        """Test error handling for missing columns."""
        with self.assertRaises(ValueError):
            prepare_sccoda_data(
                self.adata,
                sample_key='nonexistent',
                cell_type_key='cell_type'
            )

    def test_check_data_requirements(self):
        """Test data validation."""
        sccoda_data = prepare_sccoda_data(
            self.adata,
            sample_key='sample_id',
            cell_type_key='cell_type'
        )

        checks = check_data_requirements(sccoda_data, verbose=False)

        self.assertIn('pass', checks)
        self.assertIn('warnings', checks)
        self.assertIn('errors', checks)
        self.assertIn('diagnostics', checks)

    def test_from_cell_counts_df(self):
        """Test creating data from cell counts DataFrame."""
        counts_df = pd.DataFrame({
            'A': [100, 150],
            'B': [50, 60],
            'C': [30, 40],
            'condition': ['ctrl', 'treat']
        }, index=['s1', 's2'])

        sccoda_data = from_cell_counts_df(
            counts_df,
            covariate_columns=['condition']
        )

        self.assertEqual(sccoda_data.n_obs, 2)
        self.assertEqual(sccoda_data.n_vars, 3)
        self.assertIn('condition', sccoda_data.obs.columns)

    def test_subset_sccoda_data(self):
        """Test subsetting compositional data."""
        sccoda_data = prepare_sccoda_data(
            self.adata,
            sample_key='sample_id',
            cell_type_key='cell_type'
        )

        # Subset by samples
        subset = subset_sccoda_data(sccoda_data, samples=['s1', 's2'])
        self.assertEqual(subset.n_obs, 2)

        # Subset by cell types
        subset = subset_sccoda_data(sccoda_data, cell_types=['A', 'B'])
        self.assertEqual(subset.n_vars, 2)

    def test_get_composition_summary(self):
        """Test composition summary statistics."""
        sccoda_data = prepare_sccoda_data(
            self.adata,
            sample_key='sample_id',
            cell_type_key='cell_type'
        )

        summary = get_composition_summary(sccoda_data)

        self.assertIn('total_count', summary.columns)
        self.assertIn('mean_proportion', summary.columns)
        self.assertIn('cv', summary.columns)
        self.assertEqual(len(summary), 4)  # 4 cell types


class TestUtils(unittest.TestCase):
    """Test utility functions."""

    def setUp(self):
        """Create test data and mock results."""
        np.random.seed(42)

        # Create simple compositional data
        self.sccoda_data = AnnData(
            X=np.array([
                [100, 50, 30, 20],  # ctrl1
                [120, 45, 35, 15],  # ctrl2
                [80, 60, 25, 25],   # treat1
                [90, 55, 30, 25],   # treat2
            ], dtype='float64'),
            obs=pd.DataFrame({
                'condition': ['ctrl', 'ctrl', 'treat', 'treat']
            }, index=['s1', 's2', 's3', 's4']),
            var=pd.DataFrame(index=['A', 'B', 'C', 'D'])
        )

        # Create mock results
        self.mock_results = Mock()
        self.mock_results.effect_df = pd.DataFrame({
            'Final Parameter': [0.0, 0.5, 0.0, 0.0],
            'log2-fold change': [0.0, 1.2, 0.0, 0.0],
            'Inclusion probability': [0.1, 0.8, 0.2, 0.1],
        }, index=pd.MultiIndex.from_tuples([
            ('condition', 'A'), ('condition', 'B'),
            ('condition', 'C'), ('condition', 'D')
        ], names=['Covariate', 'Cell Type']))

        self.mock_results.intercept_df = pd.DataFrame({
            'Final Parameter': [2.0, 1.5, 1.0, 0.5],
        }, index=['A', 'B', 'C', 'D'])

        self.mock_results.model_specs = {
            'formula': 'condition',
            'reference': 0,
            'threshold_prob': 0.5,
        }

        self.mock_results.sampling_stats = {
            'chain_length': 10000,
            'num_burnin': 2500,
            'acc_rate': 0.65,
            'duration': 45.0,
            'y_hat': np.zeros((4, 4)),
        }

    def test_validate_sccoda_data(self):
        """Test data validation function."""
        validation = validate_sccoda_data(
            self.sccoda_data,
            min_samples=4,
            min_cell_types=4
        )

        self.assertIn('valid', validation)
        self.assertIn('diagnostics', validation)
        self.assertTrue(validation['valid'])

    def test_summarize_results(self):
        """Test result summarization."""
        summary = summarize_results(self.mock_results, extended=False)

        self.assertIn('intercept_df', summary)
        self.assertIn('effect_df', summary)
        self.assertIn('credible_effects', summary)
        self.assertIn('statistics', summary)

        stats = summary['statistics']
        self.assertEqual(stats['n_credible_effects'], 1)
        self.assertEqual(stats['formula'], 'condition')

    def test_get_significant_cell_types(self):
        """Test extracting significant cell types."""
        # Setup mock credible_effects
        credible_series = pd.Series(
            [False, True, False, False],
            index=pd.MultiIndex.from_tuples([
                ('condition', 'A'), ('condition', 'B'),
                ('condition', 'C'), ('condition', 'D')
            ], names=['Covariate', 'Cell Type'])
        )
        self.mock_results.credible_effects.return_value = credible_series

        significant = get_significant_cell_types(self.mock_results)

        self.assertEqual(significant, ['B'])

    def test_export_results(self):
        """Test result export."""
        with tempfile.TemporaryDirectory() as tmpdir:
            export_results(
                self.mock_results,
                output_dir=tmpdir,
                prefix='test',
                export_raw=False
            )

            # Check that files were created
            self.assertTrue(os.path.exists(os.path.join(tmpdir, 'test_effects.csv')))
            self.assertTrue(os.path.exists(os.path.join(tmpdir, 'test_intercepts.csv')))
            self.assertTrue(os.path.exists(os.path.join(tmpdir, 'test_diagnostics.txt')))

    def test_create_analysis_report(self):
        """Test report generation."""
        # Setup mock credible_effects
        credible_series = pd.Series(
            [False, True, False, False],
            index=pd.MultiIndex.from_tuples([
                ('condition', 'A'), ('condition', 'B'),
                ('condition', 'C'), ('condition', 'D')
            ], names=['Covariate', 'Cell Type'])
        )
        self.mock_results.credible_effects.return_value = credible_series

        report = create_analysis_report(self.mock_results)

        self.assertIn('scCODA', report)
        self.assertIn('Model Specifications', report)
        self.assertIn('MCMC Diagnostics', report)


class TestVisualization(unittest.TestCase):
    """Test visualization functions (without displaying)."""

    def setUp(self):
        """Create mock results."""
        self.mock_results = Mock()
        self.mock_results.effect_df = pd.DataFrame({
            'Final Parameter': [0.0, 0.5, 0.0, 0.0],
            'log2-fold change': [0.0, 1.2, 0.0, 0.0],
            'Inclusion probability': [0.1, 0.8, 0.2, 0.1],
        }, index=pd.MultiIndex.from_tuples([
            ('condition', 'A'), ('condition', 'B'),
            ('condition', 'C'), ('condition', 'D')
        ], names=['Covariate', 'Cell Type']))

        self.mock_results.model_specs = {'threshold_prob': 0.5}

        credible_series = pd.Series(
            [False, True, False, False],
            index=pd.MultiIndex.from_tuples([
                ('condition', 'A'), ('condition', 'B'),
                ('condition', 'C'), ('condition', 'D')
            ], names=['Covariate', 'Cell Type'])
        )
        self.mock_results.credible_effects.return_value = credible_series

        self.sccoda_data = AnnData(
            X=np.array([[100, 50, 30, 20], [120, 45, 35, 15]], dtype='float64'),
            obs=pd.DataFrame({'condition': ['ctrl', 'treat']}, index=['s1', 's2']),
            var=pd.DataFrame(index=['A', 'B', 'C', 'D'])
        )

    def test_plot_effect_barplot(self):
        """Test effect barplot."""
        from visualization import plot_effect_barplot

        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = os.path.join(tmpdir, 'effects.png')
            fig, ax = plot_effect_barplot(
                self.mock_results,
                save_path=save_path,
                show=False
            )
            self.assertTrue(os.path.exists(save_path))
            plt.close()

    def test_plot_credible_effects(self):
        """Test credible effects plot."""
        from visualization import plot_credible_effects

        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = os.path.join(tmpdir, 'credible.png')
            fig, ax = plot_credible_effects(
                self.mock_results,
                save_path=save_path,
                show=False
            )
            self.assertTrue(os.path.exists(save_path))
            plt.close()

    def test_plot_fold_changes(self):
        """Test fold change plot."""
        from visualization import plot_fold_changes

        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = os.path.join(tmpdir, 'foldchanges.png')
            fig, ax = plot_fold_changes(
                self.mock_results,
                save_path=save_path,
                show=False
            )
            self.assertTrue(os.path.exists(save_path))
            plt.close()


class TestCoreAnalysis(unittest.TestCase):
    """Test core analysis functions (with mocking)."""

    @patch('core_analysis.mod.CompositionalAnalysis')
    def test_run_sccoda_analysis(self, mock_model_class):
        """Test scCODA analysis wrapper."""
        from core_analysis import run_sccoda_analysis

        # Setup mock
        mock_model = Mock()
        mock_model_class.return_value = mock_model

        mock_results = Mock()
        mock_results.sampling_stats = {'acc_rate': 0.65, 'duration': 30.0}
        mock_model.sample_hmc.return_value = mock_results

        # Create test data
        data = AnnData(
            X=np.array([[100, 50], [80, 60]], dtype='float64'),
            obs=pd.DataFrame({'condition': ['ctrl', 'treat']}, index=['s1', 's2']),
            var=pd.DataFrame(index=['A', 'B'])
        )

        # Run analysis
        results = run_sccoda_analysis(
            data,
            formula='condition',
            reference_cell_type='automatic',
            num_results=1000,
            num_burnin=250,
            verbose=False
        )

        # Verify
        mock_model_class.assert_called_once()
        mock_model.sample_hmc.assert_called_once()
        self.assertEqual(results, mock_results)


if __name__ == '__main__':
    # Import matplotlib here to avoid issues if not available
    import matplotlib.pyplot as plt
    plt.switch_backend('Agg')  # Use non-interactive backend

    unittest.main()
