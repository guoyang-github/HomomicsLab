#!/usr/bin/env python3
"""
Unit tests for SpaGCN analysis module.
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
    from core_analysis import (
        prepare_data,
        calculate_adjacency_matrix,
        search_optimal_l,
        search_optimal_resolution,
        run_spagcn,
        refine_domains,
        identify_svgs,
        find_meta_gene
    )
    from visualization import (
        plot_spatial_domains,
        plot_gene_expression,
        plot_domain_heatmap
    )
    from utils import (
        find_neighbor_clusters,
        get_domain_expression,
        get_top_genes_per_domain
    )
    SPAGCN_AVAILABLE = True
except ImportError:
    SPAGCN_AVAILABLE = False


class TestDataPreparation(unittest.TestCase):
    """Test data preparation functions."""

    def create_test_anndata(self, n_obs=50, n_vars=100, is_spatial=True):
        """Create test AnnData object."""
        np.random.seed(42)

        counts = np.random.poisson(5, size=(n_obs, n_vars))
        obs_names = [f"obs_{i}" for i in range(n_obs)]
        var_names = [f"gene_{i}" for i in range(n_vars)]

        if is_spatial:
            obs = pd.DataFrame({
                'array_row': np.random.randint(0, 20, n_obs),
                'array_col': np.random.randint(0, 20, n_obs),
                'x_pixel': np.random.randint(0, 2000, n_obs),
                'y_pixel': np.random.randint(0, 2000, n_obs)
            }, index=obs_names)
        else:
            obs = pd.DataFrame(index=obs_names)

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
        self.assertIn('array_row', adata.obs.columns)

    def test_prepare_data(self):
        """Test data preparation."""
        adata = self.create_test_anndata(n_obs=50, n_vars=100)

        adata_prep = prepare_data(
            adata,
            min_cells=1,
            min_genes=1,
            n_top_genes=50
        )

        self.assertLessEqual(adata_prep.n_vars, 50)
        self.assertTrue('highly_variable' in adata_prep.var.columns or adata_prep.n_vars <= 50)

    def test_prepare_data_no_hvg(self):
        """Test preparation without HVG selection."""
        adata = self.create_test_anndata(n_obs=50, n_vars=100)

        adata_prep = prepare_data(
            adata,
            hvg_selection=False
        )

        self.assertEqual(adata_prep.n_vars, 100)


@unittest.skipUnless(SPAGCN_AVAILABLE, "SpaGCN not installed")
class TestAdjacencyMatrix(unittest.TestCase):
    """Test adjacency matrix calculation."""

    def create_spatial_data(self, n_spots=30):
        """Create spatial test data."""
        np.random.seed(42)

        counts = np.random.poisson(5, size=(n_spots, 50))

        # Create grid coordinates
        coords = []
        for i in range(5):
            for j in range(6):
                if len(coords) < n_spots:
                    coords.append((i, j, i*100, j*100))

        obs = pd.DataFrame(
            coords,
            columns=['array_row', 'array_col', 'x_pixel', 'y_pixel'],
            index=[f"spot_{i}" for i in range(n_spots)]
        )

        return ad.AnnData(X=counts, obs=obs)

    def test_calculate_adjacency_no_histology(self):
        """Test adjacency without histology."""
        adata = self.create_spatial_data()

        adj = calculate_adjacency_matrix(
            adata,
            x_column="array_col",
            y_column="array_row",
            histology=False
        )

        self.assertEqual(adj.shape, (30, 30))
        self.assertTrue(np.all(adj >= 0))
        self.assertTrue(np.allclose(np.diag(adj), 0))

    def test_adjacency_symmetry(self):
        """Test adjacency matrix is symmetric."""
        adata = self.create_spatial_data()

        adj = calculate_adjacency_matrix(
            adata,
            x_column="array_col",
            y_column="array_row",
            histology=False
        )

        self.assertTrue(np.allclose(adj, adj.T))


@unittest.skipUnless(SPAGCN_AVAILABLE, "SpaGCN not installed")
class TestParameterSearch(unittest.TestCase):
    """Test parameter search functions."""

    def create_test_data_with_adj(self):
        """Create test data with adjacency."""
        np.random.seed(42)

        n_spots = 20
        counts = np.random.poisson(5, size=(n_spots, 50))

        coords = []
        for i in range(4):
            for j in range(5):
                coords.append((i, j))

        obs = pd.DataFrame(
            coords,
            columns=['array_row', 'array_col'],
            index=[f"spot_{i}" for i in range(n_spots)]
        )

        adata = ad.AnnData(X=counts, obs=obs)
        adata = prepare_data(adata, min_cells=1, min_genes=1)

        adj = calculate_adjacency_matrix(adata, histology=False)

        return adata, adj

    def test_search_optimal_l(self):
        """Test l parameter search."""
        adata, adj = self.create_test_data_with_adj()

        l = search_optimal_l(adj, target_p=0.5, start=0.01, end=100)

        # l should be found or None if out of range
        if l is not None:
            self.assertIsInstance(l, float)
            self.assertGreater(l, 0)


class TestVisualization(unittest.TestCase):
    """Test visualization functions."""

    def create_test_data_with_domains(self):
        """Create test data with domain labels."""
        np.random.seed(42)

        n_spots = 30
        counts = np.random.poisson(5, size=(n_spots, 50))

        obs = pd.DataFrame({
            'array_row': np.random.randint(0, 10, n_spots),
            'array_col': np.random.randint(0, 10, n_spots),
            'x_pixel': np.random.randint(0, 1000, n_spots),
            'y_pixel': np.random.randint(0, 1000, n_spots),
            'domain': np.random.choice([0, 1, 2], n_spots)
        }, index=[f"spot_{i}" for i in range(n_spots)])

        return ad.AnnData(X=counts, obs=obs, var=pd.DataFrame(index=[f"gene_{i}" for i in range(50)]))

    def test_plot_spatial_domains(self):
        """Test domain plotting."""
        adata = self.create_test_data_with_domains()

        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir) / "test_domains.png"

            fig = plot_spatial_domains(
                adata,
                domain_column="domain",
                x_column="x_pixel",
                y_column="y_pixel",
                save_path=str(save_path),
                show=False
            )

            self.assertIsNotNone(fig)
            self.assertTrue(save_path.exists())

    def test_plot_gene_expression(self):
        """Test gene expression plotting."""
        adata = self.create_test_data_with_domains()

        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir) / "test_gene.png"

            fig = plot_gene_expression(
                adata,
                gene="gene_0",
                x_column="x_pixel",
                y_column="y_pixel",
                save_path=str(save_path),
                show=False
            )

            self.assertIsNotNone(fig)
            self.assertTrue(save_path.exists())


class TestUtils(unittest.TestCase):
    """Test utility functions."""

    def create_test_data_with_domains(self):
        """Create test data."""
        np.random.seed(42)

        n_spots = 30
        n_genes = 20
        counts = np.random.poisson(5, size=(n_spots, n_genes))

        # Create domains with distinct expression patterns
        domain_labels = np.repeat([0, 1, 2], 10)
        for i, d in enumerate([0, 1, 2]):
            mask = domain_labels == d
            counts[mask, d*5:(d+1)*5] += 10

        obs = pd.DataFrame({
            'domain': domain_labels,
            'array_row': np.random.randint(0, 10, n_spots),
            'array_col': np.random.randint(0, 10, n_spots)
        }, index=[f"spot_{i}" for i in range(n_spots)])

        return ad.AnnData(
            X=counts,
            obs=obs,
            var=pd.DataFrame(index=[f"gene_{i}" for i in range(n_genes)])
        )

    def test_get_domain_expression(self):
        """Test domain expression extraction."""
        adata = self.create_test_data_with_domains()

        df = get_domain_expression(adata, domain_column="domain")

        self.assertEqual(df.shape[0], 3)  # 3 domains
        self.assertEqual(df.shape[1], 20)  # 20 genes

    def test_get_top_genes_per_domain(self):
        """Test top genes per domain."""
        adata = self.create_test_data_with_domains()

        top_genes = get_top_genes_per_domain(adata, domain_column="domain", n_genes=3)

        self.assertEqual(len(top_genes), 3)
        self.assertEqual(len(top_genes[0]), 3)


@unittest.skipUnless(SPAGCN_AVAILABLE, "SpaGCN not installed")
class TestMoranI(unittest.TestCase):
    """Test Moran's I calculation."""

    def create_spatial_data(self, n_spots=30, n_genes=20):
        """Create test data with spatial structure."""
        np.random.seed(42)
        counts = np.random.poisson(5, size=(n_spots, n_genes))

        # Create grid coordinates
        coords = []
        for i in range(5):
            for j in range(6):
                if len(coords) < n_spots:
                    coords.append((i, j))

        obs = pd.DataFrame(
            coords,
            columns=['array_row', 'array_col'],
            index=[f"spot_{i}" for i in range(n_spots)]
        )

        return ad.AnnData(X=counts, obs=obs,
                         var=pd.DataFrame(index=[f"gene_{i}" for i in range(n_genes)]))

    def test_calculate_moran_i(self):
        """Test Moran's I for a single gene."""
        from utils import calculate_moran_i

        adata = self.create_spatial_data(n_spots=20, n_genes=5)

        mi = calculate_moran_i(adata, gene="gene_0")

        self.assertIsInstance(mi, float)
        self.assertTrue(-1.0 <= mi <= 1.0)

    def test_calculate_moran_i_invalid_gene(self):
        """Test Moran's I with invalid gene name."""
        from utils import calculate_moran_i

        adata = self.create_spatial_data(n_spots=20, n_genes=5)

        with self.assertRaises(ValueError):
            calculate_moran_i(adata, gene="nonexistent_gene")

    def test_calculate_moran_i_genes(self):
        """Test Moran's I for multiple genes."""
        from utils import calculate_moran_i_genes

        adata = self.create_spatial_data(n_spots=20, n_genes=5)

        df = calculate_moran_i_genes(adata, n_top=3)

        self.assertEqual(len(df), 3)
        self.assertIn('gene', df.columns)
        self.assertIn('moran_i', df.columns)
        self.assertTrue(all(-1.0 <= v <= 1.0 for v in df['moran_i']))


@unittest.skipUnless(SPAGCN_AVAILABLE, "SpaGCN not installed")
class TestIntegration(unittest.TestCase):
    """Integration tests requiring SpaGCN."""

    def test_full_workflow(self):
        """Test complete SpaGCN workflow."""
        import random
        import torch

        # Create test data
        np.random.seed(42)
        random.seed(42)
        torch.manual_seed(42)

        n_spots = 50
        counts = np.random.poisson(5, size=(n_spots, 100))

        # Create grid coordinates
        coords = []
        for i in range(10):
            for j in range(5):
                if len(coords) < n_spots:
                    coords.append((i, j))

        obs = pd.DataFrame(
            coords,
            columns=['array_row', 'array_col'],
            index=[f"spot_{i}" for i in range(n_spots)]
        )

        adata = ad.AnnData(X=counts, obs=obs)

        # Preprocess
        adata_prep = prepare_data(adata, min_cells=1, min_genes=1)

        # Calculate adjacency
        adj = calculate_adjacency_matrix(adata_prep, histology=False)

        # Search l
        l = search_optimal_l(adj, target_p=0.5, start=0.01, end=50)
        self.assertIsNotNone(l)

        # Search resolution for 3 clusters
        resolution = search_optimal_resolution(
            adata_prep, adj, l=l, target_clusters=3, max_epochs=5
        )
        self.assertIsNotNone(resolution)

        # Run SpaGCN
        domains = run_spagcn(adata_prep, adj, l=l, resolution=resolution, max_epochs=20)

        self.assertEqual(len(domains), n_spots)
        self.assertGreaterEqual(len(set(domains)), 1)


if __name__ == '__main__':
    print(f"SpaGCN available: {SPAGCN_AVAILABLE}")
    print("Running tests...\n")
    unittest.main(verbosity=2)
