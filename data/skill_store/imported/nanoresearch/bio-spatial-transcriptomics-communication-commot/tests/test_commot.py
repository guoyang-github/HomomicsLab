"""
Unit tests for COMMOT spatial communication analysis skill.

Tests the wrapper functions in scripts/python/.
"""

import unittest
import numpy as np
import pandas as pd
from scipy import sparse
import scanpy as sc
from anndata import AnnData

# Import functions to test
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts' / 'python'))

from core_analysis import (
    prepare_data,
    check_spatial_units,
    create_custom_lr_database,
    get_top_lr_pairs,
    export_results,
    run_commot,
)

from visualization import (
    plot_communication_strength,
    plot_lr_expression,
    plot_top_lr_pairs,
    create_figure_grid,
)


# ============================================================================
# Test Data Setup
# ============================================================================

def create_test_adata(n_spots=100, n_genes=200, spatial_key='spatial'):
    """Create minimal test AnnData with spatial coordinates (sparse matrix)."""
    np.random.seed(42)

    # Create sparse count matrix (~20% density)
    density = 0.2
    nnz = max(1, int(n_spots * n_genes * density))
    row_idx = np.random.randint(0, n_spots, nnz)
    col_idx = np.random.randint(0, n_genes, nnz)
    data = np.random.poisson(5, nnz)
    counts = sparse.csr_matrix((data, (row_idx, col_idx)), shape=(n_spots, n_genes))

    # Create AnnData
    adata = AnnData(X=counts)
    # Build var_names as a list first, then assign as Index
    var_names = [f'GENE_{i}' for i in range(n_genes)]

    # Add marker genes by replacing names in the list
    marker_genes = ['TGFB1', 'TGFBR1', 'TGFBR2', 'IL6', 'IL6R', 'IL6ST']
    for i, gene in enumerate(marker_genes):
        if i < n_genes:
            var_names[i] = gene

    adata.var_names = pd.Index(var_names)
    adata.obs_names = [f'SPOT_{i}' for i in range(n_spots)]

    # Add spatial coordinates (grid layout)
    grid_size = int(np.ceil(np.sqrt(n_spots)))
    x = np.repeat(np.arange(grid_size), grid_size)[:n_spots]
    y = np.tile(np.arange(grid_size), grid_size)[:n_spots]
    adata.obsm[spatial_key] = np.column_stack([x * 100, y * 100])

    # Add cluster annotations
    adata.obs['cluster'] = pd.Categorical(
        np.random.choice(['A', 'B', 'C'], n_spots)
    )

    return adata


def add_mock_commot_results(adata, database_name='cellchat', lr_pairs=None):
    """Add mock COMMOT results to adata for testing."""
    if lr_pairs is None:
        lr_pairs = ['TGFB1-TGFBR1_TGFBR2', 'IL6-IL6R_IL6ST', 'CXCL12-CXCR4']

    n_spots = adata.n_obs

    # Sender summary
    adata.obsm[f'commot-{database_name}-sum-sender'] = pd.DataFrame(
        np.random.rand(n_spots, len(lr_pairs)),
        columns=[f's-{p}' for p in lr_pairs],
        index=adata.obs_names,
    )

    # Receiver summary
    adata.obsm[f'commot-{database_name}-sum-receiver'] = pd.DataFrame(
        np.random.rand(n_spots, len(lr_pairs)),
        columns=[f'r-{p}' for p in lr_pairs],
        index=adata.obs_names,
    )

    return adata


# ============================================================================
# Tests for core_analysis.py
# ============================================================================

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
        adata.X[0, :] = 0  # Make first spot empty

        adata_prep = prepare_data(adata, min_counts=10, normalize=False, log1p=False)
        self.assertLess(adata_prep.n_obs, adata.n_obs)

    def test_prepare_data_missing_spatial(self):
        """Test error for missing spatial coordinates."""
        adata = create_test_adata()
        del adata.obsm['spatial']

        with self.assertRaises(ValueError) as context:
            prepare_data(adata)
        self.assertIn('spatial', str(context.exception).lower())

    def test_check_spatial_units(self):
        """Test spatial unit checking."""
        adata = create_test_adata()

        # Should not raise
        try:
            check_spatial_units(adata, spatial_key='spatial')
        except Exception as e:
            self.fail(f"check_spatial_units raised {e} unexpectedly!")


class TestDatabaseFunctions(unittest.TestCase):
    """Tests for database functions."""

    def test_create_custom_lr_database(self):
        """Test custom database creation."""
        df = create_custom_lr_database(
            ligands=['TGFB1', 'IL6'],
            receptors=['TGFBR1_TGFBR2', 'IL6R_IL6ST'],
            pathways=['TGFb', 'IL6'],
        )

        self.assertEqual(len(df), 2)
        self.assertIn('ligand', df.columns)
        self.assertIn('receptor', df.columns)
        self.assertIn('pathway_name', df.columns)

    def test_create_custom_lr_database_no_pathways(self):
        """Test custom database without pathways."""
        df = create_custom_lr_database(
            ligands=['TGFB1', 'IL6'],
            receptors=['TGFBR1_TGFBR2', 'IL6R_IL6ST'],
        )

        self.assertEqual(len(df), 2)
        self.assertIn('pathway_name', df.columns)

    def test_create_custom_lr_database_mismatched_lengths(self):
        """Test error for mismatched lengths."""
        with self.assertRaises(ValueError):
            create_custom_lr_database(
                ligands=['TGFB1', 'IL6'],
                receptors=['TGFBR1_TGFBR2'],  # Missing one
            )


class TestResultAccess(unittest.TestCase):
    """Tests for result access functions."""

    def setUp(self):
        """Set up test data with mock COMMOT results."""
        self.adata = create_test_adata()
        self.adata = add_mock_commot_results(self.adata, database_name='cellchat')

    def test_get_top_lr_pairs(self):
        """Test getting top LR pairs."""
        df_top = get_top_lr_pairs(self.adata, n=3, database_name='cellchat')

        self.assertEqual(len(df_top), 3)
        self.assertIn('lr_pair', df_top.columns)
        self.assertIn('total', df_top.columns)
        # Verify lr_pair names do NOT have 's-' prefix
        for pair in df_top['lr_pair']:
            self.assertFalse(pair.startswith('s-'))
            self.assertFalse(pair.startswith('r-'))

    def test_get_top_lr_pairs_sender_only(self):
        """Test getting top pairs with only sender data."""
        del self.adata.obsm['commot-cellchat-sum-receiver']

        df_top = get_top_lr_pairs(self.adata, n=2, database_name='cellchat')
        self.assertEqual(len(df_top), 2)

    def test_get_top_lr_pairs_alignment(self):
        """Test that sender and receiver are correctly aligned by pair name."""
        n = self.adata.n_obs
        # Create asymmetric data: only sender has pair1, only receiver has pair2
        self.adata.obsm['commot-cellchat-sum-sender'] = pd.DataFrame(
            {'s-Pair1': np.ones(n)},
            index=self.adata.obs_names
        )
        self.adata.obsm['commot-cellchat-sum-receiver'] = pd.DataFrame(
            {'r-Pair2': np.ones(n) * 2},
            index=self.adata.obs_names
        )

        df_top = get_top_lr_pairs(self.adata, n=10, database_name='cellchat')
        # Should have both Pair1 and Pair2
        pairs = set(df_top['lr_pair'].tolist())
        self.assertIn('Pair1', pairs)
        self.assertIn('Pair2', pairs)
        # Pair1 should have sender_total > 0 and receiver_total == 0
        row1 = df_top[df_top['lr_pair'] == 'Pair1'].iloc[0]
        self.assertGreater(row1['sender_total'], 0)
        self.assertEqual(row1['receiver_total'], 0.0)
        # Pair2 should have sender_total == 0 and receiver_total > 0
        row2 = df_top[df_top['lr_pair'] == 'Pair2'].iloc[0]
        self.assertEqual(row2['sender_total'], 0.0)
        self.assertGreater(row2['receiver_total'], 0)


# ============================================================================
# Tests for visualization.py
# ============================================================================

class TestVisualization(unittest.TestCase):
    """Tests for visualization functions."""

    def setUp(self):
        """Set up test data."""
        self.adata = create_test_adata()
        self.adata = add_mock_commot_results(self.adata, database_name='cellchat')

    def test_create_figure_grid(self):
        """Test figure grid creation."""
        fig, axes = create_figure_grid(5, n_cols=2)

        self.assertEqual(len(axes), 5)
        # Check that figure was created with correct size
        self.assertIsNotNone(fig)

    def test_create_figure_grid_single(self):
        """Test figure grid with single plot."""
        fig, axes = create_figure_grid(1, n_cols=1)

        self.assertEqual(len(axes), 1)

    def test_plot_communication_strength(self):
        """Test communication strength plotting."""
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots()
        result = plot_communication_strength(
            self.adata,
            lr_pair='TGFB1-TGFBR1_TGFBR2',
            database_name='cellchat',
            ax=ax,
        )

        self.assertIsNotNone(result)
        plt.close()

    def test_plot_communication_strength_invalid_lr(self):
        """Test error for invalid LR pair."""
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots()
        with self.assertRaises((KeyError, ValueError)):
            plot_communication_strength(
                self.adata,
                lr_pair='INVALID-PAIR',
                database_name='cellchat',
                ax=ax,
            )
        plt.close()

    def test_plot_lr_expression(self):
        """Test LR expression plotting."""
        fig = plot_lr_expression(
            self.adata,
            ligand='TGFB1',
            receptor='TGFBR1',
        )

        self.assertIsNotNone(fig)
        import matplotlib.pyplot as plt
        plt.close()

    def test_plot_lr_expression_missing_gene(self):
        """Test LR expression plotting with missing genes."""
        fig = plot_lr_expression(
            self.adata,
            ligand='NONEXISTENT',
            receptor='ALSO_MISSING',
        )
        self.assertIsNotNone(fig)
        import matplotlib.pyplot as plt
        plt.close()

    def test_plot_top_lr_pairs(self):
        """Test top pairs bar chart."""
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(8, 6))
        result = plot_top_lr_pairs(
            self.adata,
            n=2,
            database_name='cellchat',
            ax=ax,
        )

        self.assertIsNotNone(result)
        plt.close()


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration(unittest.TestCase):
    """Integration tests for complete workflow."""

    def test_complete_workflow_mock(self):
        """Test complete workflow with mock data."""
        # Create data
        adata = create_test_adata(n_spots=50, n_genes=100)

        # Ensure no spot has 0 counts to avoid filtering
        if sparse.issparse(adata.X):
            adata.X.data = np.maximum(adata.X.data, 1)
        else:
            adata.X = np.maximum(adata.X, 1)

        # Prepare
        adata_prep = prepare_data(adata, min_counts=1, normalize=False, log1p=False)
        self.assertIsInstance(adata_prep, AnnData)

        # Create custom database
        df_lr = create_custom_lr_database(
            ligands=['TGFB1', 'IL6'],
            receptors=['TGFBR1_TGFBR2', 'IL6R_IL6ST'],
        )
        self.assertEqual(len(df_lr), 2)

        # Note: Actual COMMOT run requires commot package and compatible numpy
        # Here we just verify the setup
        print("Workflow setup successful")

    def test_run_commot_no_spatial(self):
        """Test that run_commot raises error without spatial coordinates."""
        adata = create_test_adata()
        del adata.obsm['spatial']
        df_lr = create_custom_lr_database(
            ligands=['TGFB1'], receptors=['TGFBR1_TGFBR2']
        )
        with self.assertRaises(ValueError) as ctx:
            run_commot(adata, df_lr, database_name='test')
        self.assertIn('spatial', str(ctx.exception).lower())


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == '__main__':
    unittest.main(verbosity=2)
