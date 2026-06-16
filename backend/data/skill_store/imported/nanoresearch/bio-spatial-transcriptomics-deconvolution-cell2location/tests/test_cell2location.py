#!/usr/bin/env python3
"""
Unit tests for cell2location analysis module.
"""

import unittest
import tempfile
from pathlib import Path
import numpy as np
import pandas as pd
import scanpy as sc
import anndata as ad

# Import module under test
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts' / 'python'))

try:
    from core_analysis import prepare_data, estimate_cell_type_proportions, extract_proportions
    from visualization import normalize_proportions
    from utils import validate_inputs, filter_low_quality_spots, estimate_optimal_epochs
except ImportError as e:
    print(f"Import error: {e}")
    raise

try:
    import cell2location
    CELL2LOCATION_AVAILABLE = True
except ImportError:
    CELL2LOCATION_AVAILABLE = False


class TestDataPreparation(unittest.TestCase):
    """Test data preparation functions."""

    def create_test_anndata(self, n_obs=50, n_vars=100, is_spatial=False):
        """Create test AnnData object."""
        np.random.seed(42)

        counts = np.random.poisson(5, size=(n_obs, n_vars))
        obs_names = [f"obs_{i}" for i in range(n_obs)]
        var_names = [f"gene_{i}" for i in range(n_vars)]

        if is_spatial:
            obs = pd.DataFrame({
                'array_row': np.random.randint(0, 20, n_obs),
                'array_col': np.random.randint(0, 20, n_obs)
            }, index=obs_names)
        else:
            obs = pd.DataFrame({
                'cell_type': np.random.choice(['A', 'B', 'C'], n_obs)
            }, index=obs_names)

        return ad.AnnData(
            X=counts,
            obs=obs,
            var=pd.DataFrame(index=var_names)
        )

    def test_create_test_data(self):
        """Test test data creation."""
        adata = self.create_test_anndata(n_obs=30, n_vars=50)

        self.assertEqual(adata.n_obs, 30)
        self.assertEqual(adata.n_vars, 50)
        self.assertIn('cell_type', adata.obs.columns)

    def test_prepare_data_returns_copies(self):
        """Test prepare_data returns copies, not modifying originals."""
        spatial = self.create_test_anndata(n_obs=30, n_vars=50, is_spatial=True)
        ref = self.create_test_anndata(n_obs=50, n_vars=50, is_spatial=False)
        original_spatial_genes = list(spatial.var_names)
        original_ref_genes = list(ref.var_names)

        spatial_prep, ref_prep = prepare_data(
            spatial, ref, cell_type_key='cell_type', min_common_genes=10
        )

        # Originals should be unchanged
        self.assertEqual(list(spatial.var_names), original_spatial_genes)
        self.assertEqual(list(ref.var_names), original_ref_genes)
        # Returns should be different objects
        self.assertIsNot(spatial_prep, spatial)
        self.assertIsNot(ref_prep, ref)

    def test_prepare_data_common_genes(self):
        """Test prepare_data finds common genes."""
        # Create data with overlapping genes
        genes_common = [f"gene_{i}" for i in range(50)]
        genes_spatial_only = [f"spatial_{i}" for i in range(10)]
        genes_ref_only = [f"ref_{i}" for i in range(10)]

        spatial = self.create_test_anndata(n_obs=30, n_vars=60)
        spatial.var_names = genes_common + genes_spatial_only

        ref = self.create_test_anndata(n_obs=50, n_vars=60, is_spatial=False)
        ref.var_names = genes_common + genes_ref_only

        spatial_prep, ref_prep = prepare_data(
            spatial, ref,
            cell_type_key='cell_type',
            min_common_genes=40
        )

        self.assertEqual(spatial_prep.n_vars, 50)
        self.assertEqual(ref_prep.n_vars, 50)

    def test_prepare_data_missing_cell_type_key(self):
        """Test error when cell_type_key is missing."""
        spatial = self.create_test_anndata(n_obs=30, n_vars=50, is_spatial=True)
        ref = self.create_test_anndata(n_obs=50, n_vars=50, is_spatial=False)

        with self.assertRaises(ValueError) as context:
            prepare_data(spatial, ref, cell_type_key='nonexistent')

        self.assertIn('nonexistent', str(context.exception))

    def test_prepare_data_insufficient_genes(self):
        """Test error when insufficient common genes."""
        spatial = self.create_test_anndata(n_obs=30, n_vars=10)
        ref = self.create_test_anndata(n_obs=50, n_vars=10, is_spatial=False)

        # Make genes different
        spatial.var_names = [f"spatial_{i}" for i in range(10)]
        ref.var_names = [f"ref_{i}" for i in range(10)]

        with self.assertRaises(ValueError) as context:
            prepare_data(spatial, ref, cell_type_key='cell_type', min_common_genes=5)

        self.assertIn('common genes', str(context.exception))


class TestProportionExtraction(unittest.TestCase):
    """Test proportion extraction functions."""

    def create_mock_results(self):
        """Create mock cell2location results."""
        np.random.seed(42)

        n_spots = 30
        cell_types = ['T_cell', 'B_cell', 'Macrophage']

        # Create mock proportions (use unnormalized random data for testing)
        q05_props = np.random.rand(n_spots, 3) * 10  # Unnormalized counts
        q50_props = np.random.rand(n_spots, 3) * 10
        q95_props = np.random.rand(n_spots, 3) * 10

        obs = pd.DataFrame(index=[f"spot_{i}" for i in range(n_spots)])

        adata = ad.AnnData(
            X=np.random.poisson(10, size=(n_spots, 100)),
            obs=obs,
            var=pd.DataFrame(index=[f"gene_{i}" for i in range(100)])
        )

        # Add mock cell2location results to obsm
        adata.obsm['q05_cell_abundance_w_sf'] = pd.DataFrame(
            q05_props,
            index=adata.obs_names,
            columns=[f"q05_cell_abundance_w_sf_{ct}" for ct in cell_types]
        )
        adata.obsm['q50_cell_abundance_w_sf'] = pd.DataFrame(
            q50_props,
            index=adata.obs_names,
            columns=[f"q50_cell_abundance_w_sf_{ct}" for ct in cell_types]
        )

        return adata

    def test_estimate_cell_type_proportions(self):
        """Test proportion extraction."""
        adata = self.create_mock_results()

        props = estimate_cell_type_proportions(adata, q_threshold=0.05, normalize=True)

        self.assertEqual(props.shape[0], 30)  # 30 spots
        self.assertEqual(props.shape[1], 3)   # 3 cell types
        self.assertIn('T_cell', props.columns)

        # Check normalization (rows sum to ~1)
        row_sums = props.sum(axis=1)
        self.assertTrue(np.allclose(row_sums, 1.0, atol=0.01))

    def test_estimate_cell_type_proportions_not_normalized(self):
        """Test proportion extraction without normalization."""
        adata = self.create_mock_results()

        props = estimate_cell_type_proportions(adata, q_threshold=0.05, normalize=False)

        # Without normalization, sums can vary
        self.assertFalse(np.allclose(props.sum(axis=1), 1.0))

    def test_estimate_cell_type_proportions_all_zero_row(self):
        """Test normalization handles all-zero rows gracefully."""
        adata = self.create_mock_results()
        # Set one row to all zeros
        adata.obsm['q05_cell_abundance_w_sf'].iloc[0, :] = 0

        props = estimate_cell_type_proportions(adata, q_threshold=0.05, normalize=True)

        # All-zero row should remain all zeros after normalization
        self.assertTrue(np.allclose(props.iloc[0].values, 0.0))
        # Other rows should still sum to 1
        self.assertTrue(np.allclose(props.iloc[1:].sum(axis=1), 1.0))

    def test_extract_proportions(self):
        """Test extract_proportions function."""
        adata = self.create_mock_results()

        df, cell_types = extract_proportions(adata, key='q05_cell_abundance_w_sf')

        self.assertEqual(len(cell_types), 3)
        self.assertIn('T_cell', cell_types)
        self.assertEqual(df.shape, (30, 3))

    def test_extract_proportions_missing_key(self):
        """Test error when key is missing."""
        adata = self.create_mock_results()

        with self.assertRaises(KeyError) as context:
            extract_proportions(adata, key='nonexistent_key')

        self.assertIn('nonexistent_key', str(context.exception))


class TestUtils(unittest.TestCase):
    """Test utility functions."""

    def test_validate_inputs_passes(self):
        """Test validate_inputs with valid data."""
        n_obs = 50
        spatial = ad.AnnData(
            X=np.random.poisson(5, size=(n_obs, 100)),
            obs=pd.DataFrame({
                'array_row': np.random.randint(0, 20, n_obs),
                'array_col': np.random.randint(0, 20, n_obs)
            }, index=[f"spot_{i}" for i in range(n_obs)]),
            var=pd.DataFrame(index=[f"gene_{i}" for i in range(100)])
        )
        ref = ad.AnnData(
            X=np.random.poisson(5, size=(n_obs, 100)),
            obs=pd.DataFrame({
                'cell_type': np.random.choice(['A', 'B', 'C'], n_obs)
            }, index=[f"cell_{i}" for i in range(n_obs)]),
            var=pd.DataFrame(index=[f"gene_{i}" for i in range(100)])
        )

        # Should not raise
        validate_inputs(spatial, ref, cell_type_key='cell_type')

    def test_validate_inputs_missing_cell_type(self):
        """Test validate_inputs raises on missing cell_type_key."""
        spatial = ad.AnnData(X=np.random.poisson(5, (10, 10)))
        ref = ad.AnnData(X=np.random.poisson(5, (10, 10)))

        with self.assertRaises(ValueError) as ctx:
            validate_inputs(spatial, ref, cell_type_key='missing')
        self.assertIn('missing', str(ctx.exception))

    def test_validate_inputs_low_cell_count(self):
        """Test validate_inputs raises on cell types with <10 cells."""
        n_obs = 20
        spatial = ad.AnnData(
            X=np.random.poisson(5, size=(n_obs, 10)),
            obs=pd.DataFrame({
                'array_row': np.random.randint(0, 20, n_obs),
            }, index=[f"spot_{i}" for i in range(n_obs)]),
            var=pd.DataFrame(index=[f"gene_{i}" for i in range(10)])
        )
        ref = ad.AnnData(
            X=np.random.poisson(5, size=(n_obs, 10)),
            obs=pd.DataFrame({
                'cell_type': ['A'] * 15 + ['B'] * 5  # B has only 5 cells
            }, index=[f"cell_{i}" for i in range(n_obs)]),
            var=pd.DataFrame(index=[f"gene_{i}" for i in range(10)])
        )

        with self.assertRaises(ValueError) as ctx:
            validate_inputs(spatial, ref, cell_type_key='cell_type')
        self.assertIn('<10 cells', str(ctx.exception))

    def test_validate_inputs_spatial_coords_1d(self):
        """Test validate_inputs raises on 1D spatial coordinates."""
        n_obs = 10
        spatial = ad.AnnData(
            X=np.random.poisson(5, size=(n_obs, 10)),
            obs=pd.DataFrame(index=[f"spot_{i}" for i in range(n_obs)]),
            var=pd.DataFrame(index=[f"gene_{i}" for i in range(10)])
        )
        # 1D spatial coordinates - should fail
        spatial.obsm['spatial'] = np.arange(n_obs)

        ref = ad.AnnData(
            X=np.random.poisson(5, size=(50, 10)),
            obs=pd.DataFrame({
                'cell_type': np.random.choice(['A', 'B', 'C'], 50)
            }, index=[f"cell_{i}" for i in range(50)]),
            var=pd.DataFrame(index=[f"gene_{i}" for i in range(10)])
        )

        with self.assertRaises(ValueError) as ctx:
            validate_inputs(spatial, ref, cell_type_key='cell_type')
        self.assertIn('2D', str(ctx.exception))

    def test_filter_low_quality_spots(self):
        """Test filtering low quality spots."""
        n_obs = 20
        counts = np.zeros((n_obs, 10))
        counts[:15, :] = np.random.poisson(10, size=(15, 10))  # High quality
        counts[15:, :] = np.random.poisson(1, size=(5, 10))    # Low quality

        spatial = ad.AnnData(
            X=counts,
            obs=pd.DataFrame(index=[f"spot_{i}" for i in range(n_obs)]),
            var=pd.DataFrame(index=[f"gene_{i}" for i in range(10)])
        )

        filtered = filter_low_quality_spots(spatial, min_counts=20, min_genes=3)

        self.assertLess(filtered.n_obs, spatial.n_obs)
        self.assertEqual(spatial.n_obs, n_obs)  # Original unchanged

    def test_estimate_optimal_epochs(self):
        """Test epoch recommendation."""
        small = ad.AnnData(X=np.random.poisson(5, (500, 10)))
        medium = ad.AnnData(X=np.random.poisson(5, (3000, 10)))
        large = ad.AnnData(X=np.random.poisson(5, (10000, 10)))
        huge = ad.AnnData(X=np.random.poisson(5, (50000, 10)))

        self.assertEqual(estimate_optimal_epochs(small), 10000)
        self.assertEqual(estimate_optimal_epochs(medium), 20000)
        self.assertEqual(estimate_optimal_epochs(large), 30000)
        self.assertEqual(estimate_optimal_epochs(huge), 50000)


class TestVisualizationUtils(unittest.TestCase):
    """Test visualization utility functions."""

    def test_normalize_proportions(self):
        """Test proportion normalization."""
        props = pd.DataFrame({
            'A': [1, 2, 3],
            'B': [1, 2, 3],
            'C': [1, 2, 3]
        })

        normalized = normalize_proportions(props)

        # Check rows sum to 1
        self.assertTrue(np.allclose(normalized.sum(axis=1), 1.0))

        # Check proportions are maintained
        self.assertTrue(np.allclose(
            normalized['A'].values,
            [1/3, 1/3, 1/3]
        ))

    def test_normalize_proportions_with_zeros(self):
        """Test normalization with all-zero row."""
        props = pd.DataFrame({
            'A': [0, 2, 3],
            'B': [0, 2, 3],
            'C': [0, 2, 3]
        })

        normalized = normalize_proportions(props)

        # All-zero row should remain all zeros
        self.assertTrue(np.allclose(normalized.iloc[0].values, 0.0))
        # Other rows should sum to 1
        self.assertTrue(np.allclose(normalized.iloc[1:].sum(axis=1), 1.0))


@unittest.skipUnless(CELL2LOCATION_AVAILABLE, "cell2location not installed")
class TestCell2locationIntegration(unittest.TestCase):
    """Integration tests requiring cell2location."""

    def test_import_cell2location(self):
        """Test that cell2location package is importable."""
        import cell2location
        self.assertTrue(hasattr(cell2location, 'models'))


if __name__ == '__main__':
    print(f"cell2location available: {CELL2LOCATION_AVAILABLE}")
    print("Running tests...\n")
    unittest.main(verbosity=2)
