"""Unit tests for FastCCC cell-cell communication analysis.

Tests for core_analysis, reference_builder, utils, and visualization modules.
"""

import unittest
import numpy as np
import pandas as pd
import scanpy as sc
from anndata import AnnData
import tempfile
import os
import shutil
from unittest.mock import Mock, patch, MagicMock

# Add scripts to path
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'scripts', 'python'))

from core_analysis import (
    check_fastccc_dependencies,
    validate_fastccc_input,
    load_fastccc_results,
    get_significant_interactions,
    analyze_celltype_specific_interactions,
    get_top_interactions,
    summarize_interactions_by_cellpair,
    compare_interactions_across_conditions
)

from utils import (
    check_lr_gene_overlap,
    get_database_info,
    summarize_fastccc_results,
    filter_interactions,
    get_top_cell_pairs,
    estimate_fastccc_runtime,
    prepare_anndata_for_fastccc,
    validate_fastccc_installation
)


class TestCoreAnalysis(unittest.TestCase):
    """Test core analysis functions."""

    def setUp(self):
        """Create test data."""
        np.random.seed(42)
        self.n_cells = 100
        self.n_genes = 200

        self.adata = AnnData(
            X=np.random.poisson(2, (self.n_cells, self.n_genes)),
            obs=pd.DataFrame({
                'cell_type': np.random.choice(['A', 'B', 'C'], self.n_cells),
                'condition': np.random.choice(['ctrl', 'treat'], self.n_cells)
            }, index=[f"cell_{i}" for i in range(self.n_cells)]),
            var=pd.DataFrame(index=[f"GENE_{i}" for i in range(self.n_genes)])
        )

        # Make it sparse
        from scipy.sparse import csr_matrix
        self.adata.X = csr_matrix(self.adata.X)

        # Create mock FastCCC results
        cell_pairs = ['A|A', 'A|B', 'A|C', 'B|A', 'B|B', 'B|C', 'C|A', 'C|B', 'C|C']
        interactions = [f'INT_{i}' for i in range(50)]

        self.mock_results = {
            'interactions_strength': pd.DataFrame(
                np.random.gamma(2, 0.5, (len(cell_pairs), len(interactions))),
                index=cell_pairs,
                columns=interactions
            ),
            'pvals': pd.DataFrame(
                np.random.beta(0.5, 5, (len(cell_pairs), len(interactions))),
                index=cell_pairs,
                columns=interactions
            ),
            'percents_analysis': pd.DataFrame(
                np.random.random((len(cell_pairs), len(interactions))) > 0.3,
                index=cell_pairs,
                columns=interactions
            )
        }

    def test_check_fastccc_dependencies(self):
        """Test dependency checking."""
        result = check_fastccc_dependencies()
        self.assertIsInstance(result, bool)

    def test_validate_fastccc_input(self):
        """Test input validation."""
        validation = validate_fastccc_input(self.adata, groupby='cell_type')

        self.assertTrue(validation['valid'])
        self.assertIn('n_cells', validation)
        self.assertIn('n_genes', validation)
        self.assertIn('n_celltypes', validation)
        self.assertEqual(validation['n_cells'], self.n_cells)

    def test_validate_fastccc_input_no_groupby(self):
        """Test validation with missing groupby column."""
        validation = validate_fastccc_input(self.adata, groupby='nonexistent')

        self.assertFalse(validation['valid'])
        self.assertIn('errors', validation)

    def test_validate_fastccc_input_single_celltype(self):
        """Test validation with only one cell type."""
        adata_single = self.adata.copy()
        adata_single.obs['single_type'] = 'A'

        validation = validate_fastccc_input(adata_single, groupby='single_type')

        self.assertFalse(validation['valid'])

    def test_load_fastccc_results(self):
        """Test loading FastCCC results."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Save mock results
            self.mock_results['interactions_strength'].to_csv(
                os.path.join(tmpdir, 'test_interactions_strength.tsv'), sep='\t'
            )

            # Load results
            loaded = load_fastccc_results(tmpdir, task_id='test')

            self.assertIn('interactions_strength', loaded)

    def test_get_significant_interactions(self):
        """Test extracting significant interactions."""
        sig_df = get_significant_interactions(
            self.mock_results['pvals'],
            self.mock_results['interactions_strength'],
            pval_threshold=0.05
        )

        self.assertIsInstance(sig_df, pd.DataFrame)

    def test_analyze_celltype_specific_interactions(self):
        """Test analyzing specific cell type pair."""
        results = analyze_celltype_specific_interactions(
            self.mock_results['pvals'],
            self.mock_results['interactions_strength'],
            source_celltype='A',
            target_celltype='B',
            pval_threshold=0.05
        )

        self.assertIsInstance(results, pd.DataFrame)
        self.assertIn('significant', results.columns)

    def test_analyze_celltype_specific_interactions_invalid_pair(self):
        """Test with invalid cell pair."""
        with self.assertRaises(ValueError):
            analyze_celltype_specific_interactions(
                self.mock_results['pvals'],
                self.mock_results['interactions_strength'],
                source_celltype='X',
                target_celltype='Y'
            )

    def test_get_top_interactions(self):
        """Test getting top interactions."""
        top = get_top_interactions(
            self.mock_results['interactions_strength'],
            self.mock_results['pvals'],
            n_top=10,
            by='strength'
        )

        self.assertEqual(len(top), 10)
        self.assertIn('strength', top.columns)
        self.assertIn('pvalue', top.columns)

    def test_summarize_interactions_by_cellpair(self):
        """Test summarizing by cell pair."""
        summary = summarize_interactions_by_cellpair(
            self.mock_results['pvals'],
            self.mock_results['interactions_strength'],
            pval_threshold=0.05
        )

        self.assertIsInstance(summary, pd.DataFrame)
        self.assertIn('cell_pair', summary.columns)
        self.assertIn('n_significant', summary.columns)

    def test_compare_interactions_across_conditions(self):
        """Test comparing across conditions."""
        results_dict = {
            'condition1': self.mock_results,
            'condition2': self.mock_results
        }

        comparison = compare_interactions_across_conditions(
            results_dict,
            pval_threshold=0.05
        )

        self.assertIsInstance(comparison, pd.DataFrame)
        self.assertEqual(len(comparison), 2)


class TestUtils(unittest.TestCase):
    """Test utility functions."""

    def setUp(self):
        """Create test data."""
        np.random.seed(42)
        self.adata = AnnData(
            X=np.random.poisson(2, (50, 100)),
            obs=pd.DataFrame({'cell_type': np.random.choice(['A', 'B'], 50)}),
            var=pd.DataFrame(index=[f"GENE_{i}" for i in range(100)])
        )

        from scipy.sparse import csr_matrix
        self.adata.X = csr_matrix(self.adata.X)

        # Create mock results
        cell_pairs = ['A|A', 'A|B', 'B|A', 'B|B']
        interactions = [f'INT_{i}' for i in range(20)]

        self.mock_pvals = pd.DataFrame(
            np.random.beta(0.5, 5, (4, 20)),
            index=cell_pairs,
            columns=interactions
        )
        self.mock_strength = pd.DataFrame(
            np.random.gamma(2, 0.5, (4, 20)),
            index=cell_pairs,
            columns=interactions
        )

    def test_summarize_fastccc_results(self):
        """Test results summarization."""
        summary = summarize_fastccc_results(
            self.mock_pvals,
            self.mock_strength,
            pval_threshold=0.05
        )

        self.assertIn('n_cell_pairs', summary)
        self.assertIn('n_interactions', summary)
        self.assertIn('n_significant', summary)

    def test_filter_interactions(self):
        """Test filtering interactions."""
        pvals_filt, strength_filt = filter_interactions(
            self.mock_pvals,
            self.mock_strength,
            pval_threshold=0.05,
            min_strength=0.5
        )

        self.assertEqual(pvals_filt.shape, self.mock_pvals.shape)

    def test_get_top_cell_pairs(self):
        """Test getting top cell pairs."""
        top = get_top_cell_pairs(
            self.mock_pvals,
            self.mock_strength,
            n_top=3,
            by='n_significant'
        )

        self.assertEqual(len(top), 3)
        self.assertIn('cell_pair', top.columns)

    def test_estimate_fastccc_runtime(self):
        """Test runtime estimation."""
        estimate = estimate_fastccc_runtime(
            n_cells=1000,
            n_celltypes=5,
            use_cauchy=True
        )

        self.assertIn('estimated_total', estimate)
        self.assertIn('notes', estimate)

    def test_prepare_anndata_for_fastccc(self):
        """Test data preparation."""
        # Add cell type with few cells
        adata_test = self.adata.copy()
        adata_test.obs.loc[0:2, 'cell_type'] = 'Rare'

        adata_prep = prepare_anndata_for_fastccc(
            adata_test,
            groupby='cell_type',
            min_cells=5
        )

        # Rare cell type should be removed
        self.assertNotIn('Rare', adata_prep.obs['cell_type'].values)

    def test_validate_fastccc_installation(self):
        """Test installation validation."""
        validation = validate_fastccc_installation()

        self.assertIn('fastccc_installed', validation)
        self.assertIn('scanpy_installed', validation)
        self.assertIsInstance(validation['fastccc_installed'], bool)


class TestVisualization(unittest.TestCase):
    """Test visualization functions."""

    def setUp(self):
        """Create test data."""
        np.random.seed(42)
        cell_pairs = ['A|A', 'A|B', 'B|A', 'B|B']
        interactions = [f'INT_{i}' for i in range(20)]

        self.pvals = pd.DataFrame(
            np.random.beta(0.5, 5, (4, 20)),
            index=cell_pairs,
            columns=interactions
        )
        self.strength = pd.DataFrame(
            np.random.gamma(2, 0.5, (4, 20)),
            index=cell_pairs,
            columns=interactions
        )

    @patch('matplotlib.pyplot.savefig')
    def test_plot_interaction_heatmap(self, mock_savefig):
        """Test interaction heatmap plotting."""
        from visualization import plot_interaction_heatmap

        fig = plot_interaction_heatmap(
            self.pvals,
            self.strength,
            save_path='test.png'
        )

        self.assertIsNotNone(fig)

    @patch('matplotlib.pyplot.savefig')
    def test_plot_significant_interactions_bar(self, mock_savefig):
        """Test bar plot."""
        from visualization import plot_significant_interactions_bar

        fig = plot_significant_interactions_bar(
            self.pvals,
            top_n=3,
            save_path='test.png'
        )

        self.assertIsNotNone(fig)

    @patch('matplotlib.pyplot.savefig')
    def test_plot_pvalue_distribution(self, mock_savefig):
        """Test p-value distribution plot."""
        from visualization import plot_pvalue_distribution

        fig = plot_pvalue_distribution(
            self.pvals,
            save_path='test.png'
        )

        self.assertIsNotNone(fig)


class TestIntegration(unittest.TestCase):
    """Integration tests for the full workflow."""

    def test_full_workflow_mock(self):
        """Test full workflow with mock data."""
        from core_analysis import run_fastccc_pipeline

        # Create test data
        np.random.seed(42)
        adata = AnnData(
            X=np.random.poisson(2, (100, 200)),
            obs=pd.DataFrame({
                'cell_type': np.random.choice(['A', 'B', 'C'], 100)
            }),
            var=pd.DataFrame(index=[f"GENE_{i}" for i in range(200)])
        )
        from scipy.sparse import csr_matrix
        adata.X = csr_matrix(adata.X)

        # Validate input
        validation = validate_fastccc_input(adata, groupby='cell_type')
        self.assertTrue(validation['valid'])

        # Test utility functions
        summary = summarize_fastccc_results(
            pd.DataFrame(np.random.random((5, 10))),
            pd.DataFrame(np.random.random((5, 10)))
        )
        self.assertIn('n_cell_pairs', summary)


if __name__ == '__main__':
    # Run tests
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestCoreAnalysis))
    suite.addTests(loader.loadTestsFromTestCase(TestUtils))
    suite.addTests(loader.loadTestsFromTestCase(TestVisualization))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Exit with error code if tests failed
    exit(0 if result.wasSuccessful() else 1)
