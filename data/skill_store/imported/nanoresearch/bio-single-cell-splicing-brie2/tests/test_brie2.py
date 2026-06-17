"""
Unit tests for BRIE2 splicing analysis skill.
"""

import unittest
import numpy as np
import pandas as pd
import scanpy as sc
from anndata import AnnData
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts' / 'python'))

from core_analysis import (
    filter_splicing_data,
    get_psi_values,
    compare_cell_groups,
    validate_adata_for_brie,
)
from visualization import (
    plot_psi_distribution,
    plot_psi_heatmap,
    plot_volcano,
    plot_psi_trajectory,
    plot_splicing_summary,
)
from utils import (
    prepare_cell_features,
    summarize_splicing_results,
    check_brie_installation,
)


def create_test_adata(n_cells=50, n_events=20, with_layers=True):
    """Create test AnnData with splicing data."""
    np.random.seed(42)

    adata = sc.AnnData(
        X=np.random.beta(2, 2, (n_cells, n_events)),
        obs=pd.DataFrame({
            'cell_type': np.random.choice(['A', 'B'], n_cells),
            'pseudotime': np.random.uniform(0, 1, n_cells)
        }, index=[f'cell_{i}' for i in range(n_cells)]),
        var=pd.DataFrame({
            'GeneID': [f'gene_{i}' for i in range(n_events)],
        }, index=[f'event_{i}' for i in range(n_events)])
    )

    if with_layers:
        adata.layers['isoform1'] = np.random.poisson(10, (n_cells, n_events))
        adata.layers['isoform2'] = np.random.poisson(5, (n_cells, n_events))
        adata.layers['ambiguous'] = np.random.poisson(2, (n_cells, n_events))
        adata.layers['psi'] = adata.X.copy()

    return adata


class TestValidation(unittest.TestCase):
    """Test data validation functions."""

    def test_validate_valid_adata(self):
        """Test validation with valid data."""
        adata = create_test_adata()
        self.assertTrue(validate_adata_for_brie(adata))

    def test_validate_missing_layer(self):
        """Test validation with missing layer."""
        adata = create_test_adata()
        del adata.layers['isoform1']
        with self.assertRaises(ValueError):
            validate_adata_for_brie(adata)

    def test_validate_mismatched_shapes(self):
        """Test validation with mismatched layer shapes."""
        adata = create_test_adata()
        # Try to set mismatched shape (anndata will raise error on assignment)
        with self.assertRaises(ValueError):
            adata.layers['isoform1'] = np.random.poisson(10, (50, 10))  # Wrong shape


class TestFiltering(unittest.TestCase):
    """Test data filtering functions."""

    def test_filter_splicing_data(self):
        """Test splicing data filtering."""
        adata = create_test_adata(n_cells=100, n_events=50)

        # This test will pass even without brie installed
        # because we're just checking the interface
        try:
            import brie
            filtered = filter_splicing_data(
                adata,
                min_counts=50,
                min_cells_uniq=20
            )
            self.assertIsInstance(filtered, AnnData)
        except ImportError:
            self.skipTest("brie not installed")

    def test_filter_returns_adata(self):
        """Test that filtering returns AnnData."""
        adata = create_test_adata()

        try:
            filtered = filter_splicing_data(adata, copy=True)
            self.assertIsInstance(filtered, AnnData)
        except ImportError:
            self.skipTest("brie not installed")


class TestPSIExtraction(unittest.TestCase):
    """Test PSI value extraction."""

    def test_get_psi_values(self):
        """Test PSI extraction."""
        adata = create_test_adata()
        psi_df = get_psi_values(adata, with_confidence=False)

        self.assertEqual(psi_df.shape, (adata.n_obs, adata.n_vars))
        self.assertEqual(list(psi_df.index), list(adata.obs_names))
        self.assertEqual(list(psi_df.columns), list(adata.var_names))

    def test_get_psi_subset(self):
        """Test PSI extraction for event subset."""
        adata = create_test_adata()
        events = ['event_0', 'event_1', 'event_2']
        psi_df = get_psi_values(adata, events=events)

        self.assertEqual(psi_df.shape[1], 3)
        self.assertEqual(list(psi_df.columns), events)


class TestCellFeatures(unittest.TestCase):
    """Test cell feature preparation."""

    def test_prepare_cell_features_single(self):
        """Test preparing single feature."""
        adata = create_test_adata()
        features, names = prepare_cell_features(
            adata,
            features='pseudotime',
            encode_categorical=False
        )

        self.assertEqual(features.shape, (adata.n_obs, 1))
        self.assertEqual(names, ['pseudotime'])

    def test_prepare_cell_features_categorical(self):
        """Test preparing categorical features."""
        adata = create_test_adata()
        features, names = prepare_cell_features(
            adata,
            features='cell_type',
            encode_categorical=True
        )

        self.assertEqual(features.shape[1], 2)  # Two categories
        self.assertIn('cell_type_A', names)
        self.assertIn('cell_type_B', names)

    def test_prepare_cell_features_invalid(self):
        """Test preparing invalid feature."""
        adata = create_test_adata()
        with self.assertRaises(ValueError):
            prepare_cell_features(adata, features='invalid_column')


class TestGroupComparison(unittest.TestCase):
    """Test group comparison functions."""

    def test_compare_cell_groups(self):
        """Test comparing two cell groups."""
        adata = create_test_adata(n_cells=100)

        results = compare_cell_groups(
            adata,
            group_key='cell_type',
            group1='A',
            group2='B'
        )

        self.assertIsInstance(results, pd.DataFrame)
        self.assertEqual(len(results), adata.n_vars)
        self.assertIn('delta_psi', results.columns)
        self.assertIn('pvalue', results.columns)

    def test_compare_invalid_group_key(self):
        """Test comparing with invalid group key."""
        adata = create_test_adata()
        with self.assertRaises(ValueError):
            compare_cell_groups(adata, group_key='invalid', group1='A', group2='B')


class TestVisualization(unittest.TestCase):
    """Test visualization functions."""

    def test_plot_psi_distribution(self):
        """Test PSI distribution plot."""
        import matplotlib
        matplotlib.use('Agg')

        adata = create_test_adata()
        fig = plot_psi_distribution(adata, n_events=3, figsize=(12, 4))

        self.assertIsNotNone(fig)

    def test_plot_psi_heatmap(self):
        """Test PSI heatmap."""
        import matplotlib
        matplotlib.use('Agg')

        adata = create_test_adata()
        fig = plot_psi_heatmap(adata, n_events=10, groupby='cell_type')

        self.assertIsNotNone(fig)

    def test_plot_volcano(self):
        """Test volcano plot."""
        import matplotlib
        matplotlib.use('Agg')

        # Create mock comparison results
        df = pd.DataFrame({
            'delta_psi': np.random.uniform(-0.5, 0.5, 50),
            'pvalue': np.random.uniform(0.001, 0.1, 50),
            'qvalue': np.random.uniform(0.01, 0.2, 50)
        })

        fig = plot_volcano(df)
        self.assertIsNotNone(fig)

    def test_plot_psi_trajectory(self):
        """Test PSI trajectory plot."""
        import matplotlib
        matplotlib.use('Agg')

        adata = create_test_adata()
        fig = plot_psi_trajectory(
            adata,
            events=['event_0', 'event_1'],
            pseudotime_key='pseudotime'
        )

        self.assertIsNotNone(fig)

    def test_plot_splicing_summary(self):
        """Test splicing summary plot."""
        import matplotlib
        matplotlib.use('Agg')

        adata = create_test_adata()
        fig = plot_splicing_summary(adata, groupby='cell_type', n_events=5)

        self.assertIsNotNone(fig)


class TestSummary(unittest.TestCase):
    """Test summary functions."""

    def test_summarize_splicing_results(self):
        """Test result summarization."""
        adata = create_test_adata()
        summary = summarize_splicing_results(adata)

        self.assertIn('n_cells', summary)
        self.assertIn('n_events', summary)
        self.assertIn('psi_mean', summary)
        self.assertEqual(summary['n_cells'], adata.n_obs)
        self.assertEqual(summary['n_events'], adata.n_vars)

    def test_summarize_with_groups(self):
        """Test summarization with groups."""
        adata = create_test_adata()
        summary = summarize_splicing_results(adata, groupby='cell_type')

        self.assertIn('groups', summary)
        self.assertIn('A', summary['groups'])
        self.assertIn('B', summary['groups'])


class TestInstallation(unittest.TestCase):
    """Test installation checking."""

    def test_check_brie_installation(self):
        """Test installation check."""
        results = check_brie_installation()

        self.assertIn('brie_installed', results)
        self.assertIn('tensorflow', results)
        self.assertIn('pysam', results)


if __name__ == '__main__':
    unittest.main(verbosity=2)
