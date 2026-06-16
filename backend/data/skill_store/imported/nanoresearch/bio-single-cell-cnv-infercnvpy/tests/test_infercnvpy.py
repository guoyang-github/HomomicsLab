#!/usr/bin/env python3
"""
Unit tests for infercnvpy analysis module.
"""

import unittest
import tempfile
from pathlib import Path
import numpy as np
import pandas as pd
import scanpy as sc
from anndata import AnnData

# Import module under test
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts' / 'python'))

try:
    from infercnv_analysis import (
        add_gene_positions,
        run_infercnv_pipeline,
        cluster_by_cnv,
        identify_cnv_regions,
        summarize_cnv_by_chromosome,
        export_cnv_results,
        calculate_cnv_score,
        INFERCNVPY_AVAILABLE
    )
except ImportError as e:
    print(f"Import error: {e}")
    INFERCNVPY_AVAILABLE = False


def _create_test_anndata(n_cells=50, n_genes=200):
    """Module-level helper to create test AnnData."""
    np.random.seed(42)

    counts = np.random.poisson(5, size=(n_cells, n_genes))

    genes = []
    chromosomes = []
    starts = []
    ends = []

    for i in range(n_genes):
        chr_num = (i // 50) + 1
        genes.append(f"GENE_{i}")
        chromosomes.append(f"chr{chr_num}")
        starts.append(i * 10000)
        ends.append((i + 1) * 10000)

    adata = sc.AnnData(
        X=counts,
        obs=pd.DataFrame({
            'cell_type': np.random.choice(['Tumor', 'Normal', 'T_cell'], n_cells),
            'sample': np.random.choice(['S1', 'S2'], n_cells)
        }, index=[f"cell_{i}" for i in range(n_cells)]),
        var=pd.DataFrame({
            'chromosome': chromosomes,
            'start': starts,
            'end': ends
        }, index=genes)
    )

    return adata


class TestDataHelpers(unittest.TestCase):
    """Test data helper functions."""

    def create_test_anndata(self, n_cells=50, n_genes=200):
        """Create test AnnData with required structure."""
        np.random.seed(42)

        # Create expression matrix
        counts = np.random.poisson(5, size=(n_cells, n_genes))

        # Create gene names with chromosomal positions
        genes = []
        chromosomes = []
        starts = []
        ends = []

        for i in range(n_genes):
            chr_num = (i // 50) + 1  # 50 genes per chromosome
            genes.append(f"GENE_{i}")
            chromosomes.append(f"chr{chr_num}")
            starts.append(i * 10000)
            ends.append((i + 1) * 10000)

        adata = sc.AnnData(
            X=counts,
            obs=pd.DataFrame({
                'cell_type': np.random.choice(['Tumor', 'Normal', 'T_cell'], n_cells),
                'sample': np.random.choice(['S1', 'S2'], n_cells)
            }, index=[f"cell_{i}" for i in range(n_cells)]),
            var=pd.DataFrame({
                'chromosome': chromosomes,
                'start': starts,
                'end': ends
            }, index=genes)
        )

        return adata

    def test_create_test_data(self):
        """Test test data creation."""
        adata = self.create_test_anndata(n_cells=30, n_genes=100)

        self.assertEqual(adata.n_obs, 30)
        self.assertEqual(adata.n_vars, 100)
        self.assertIn("cell_type", adata.obs.columns)
        self.assertIn("chromosome", adata.var.columns)
        self.assertIn("start", adata.var.columns)
        self.assertIn("end", adata.var.columns)

    @unittest.skipUnless(INFERCNVPY_AVAILABLE, "infercnvpy not installed")
    def test_add_gene_positions_from_dataframe(self):
        """Test add_gene_positions with custom DataFrame."""
        adata = self.create_test_anndata(n_cells=20, n_genes=50)

        gene_pos = pd.DataFrame({
            "chromosome": [f"chr{(i // 10) + 1}" for i in range(50)],
            "start": [i * 1000 for i in range(50)],
            "end": [(i + 1) * 1000 for i in range(50)]
        }, index=[f"GENE_{i}" for i in range(50)])

        result = add_gene_positions(adata, gene_positions=gene_pos)
        self.assertIsInstance(result, AnnData)
        self.assertIn("chromosome", result.var.columns)
        self.assertIn("start", result.var.columns)
        self.assertIn("end", result.var.columns)

    @unittest.skipUnless(INFERCNVPY_AVAILABLE, "infercnvpy not installed")
    def test_add_gene_positions_validates_columns(self):
        """Test add_gene_positions rejects DataFrame with missing columns."""
        adata = self.create_test_anndata(n_cells=10, n_genes=20)

        # Missing 'end' column
        bad_pos = pd.DataFrame({
            "chromosome": ["chr1"] * 20,
            "start": [100] * 20
        }, index=[f"GENE_{i}" for i in range(20)])

        with self.assertRaises(ValueError) as ctx:
            add_gene_positions(adata, gene_positions=bad_pos)

        self.assertIn("missing required columns", str(ctx.exception).lower())

    @unittest.skipUnless(INFERCNVPY_AVAILABLE, "infercnvpy not installed")
    def test_add_gene_positions_returns_adata_not_none(self):
        """Test add_gene_positions always returns AnnData regardless of inplace."""
        adata = self.create_test_anndata(n_cells=10, n_genes=20)
        gene_pos = pd.DataFrame({
            "chromosome": ["chr1"] * 20,
            "start": [100] * 20,
            "end": [200] * 20
        }, index=[f"GENE_{i}" for i in range(20)])

        result_inplace = add_gene_positions(adata, gene_positions=gene_pos, inplace=True)
        result_copy = add_gene_positions(adata, gene_positions=gene_pos, inplace=False)

        self.assertIsInstance(result_inplace, AnnData)
        self.assertIsInstance(result_copy, AnnData)
        self.assertIsNotNone(result_inplace)
        self.assertIsNotNone(result_copy)


@unittest.skipUnless(INFERCNVPY_AVAILABLE, "infercnvpy not installed")
class TestCNVInference(unittest.TestCase):
    """Test CNV inference functions."""

    def create_test_anndata(self, n_cells=50, n_genes=200):
        """Create test AnnData."""
        np.random.seed(42)

        counts = np.random.poisson(5, size=(n_cells, n_genes))

        genes = []
        chromosomes = []
        starts = []
        ends = []

        for i in range(n_genes):
            chr_num = (i // 50) + 1
            genes.append(f"GENE_{i}")
            chromosomes.append(f"chr{chr_num}")
            starts.append(i * 10000)
            ends.append((i + 1) * 10000)

        adata = sc.AnnData(
            X=counts,
            obs=pd.DataFrame({
                'cell_type': np.random.choice(['Tumor', 'Normal'], n_cells),
            }, index=[f"cell_{i}" for i in range(n_cells)]),
            var=pd.DataFrame({
                'chromosome': chromosomes,
                'start': starts,
                'end': ends
            }, index=genes)
        )

        return adata

    def test_infercnv_pipeline(self):
        """Test CNV inference pipeline."""
        adata = self.create_test_anndata(n_cells=50, n_genes=200)

        run_infercnv_pipeline(
            adata,
            reference_key="cell_type",
            reference_cat="Normal",
            key_added="cnv"
        )

        # Check results stored
        self.assertIn("X_cnv", adata.obsm)
        self.assertIn("cnv", adata.uns)
        self.assertIn("chr_pos", adata.uns["cnv"])

    def test_infercnv_pipeline_validates_reference_cat(self):
        """Test pipeline validates reference_cat exists in data."""
        adata = self.create_test_anndata(n_cells=20, n_genes=100)

        with self.assertRaises(ValueError) as ctx:
            run_infercnv_pipeline(
                adata,
                reference_key="cell_type",
                reference_cat="NonExistent"
            )

        self.assertIn("not found", str(ctx.exception).lower())

    def test_cluster_by_cnv(self):
        """Test clustering by CNV."""
        adata = self.create_test_anndata(n_cells=50, n_genes=200)

        # First run CNV inference
        run_infercnv_pipeline(
            adata,
            reference_key="cell_type",
            reference_cat="Normal"
        )

        # Then cluster
        cluster_by_cnv(adata, key="cnv", resolution=0.5)

        # Check cluster assignments
        self.assertIn("cnv_leiden", adata.obs.columns)

    def test_cluster_by_cnv_caps_n_pcs(self):
        """Test clustering caps n_pcs to available dimensions."""
        adata = self.create_test_anndata(n_cells=20, n_genes=50)

        run_infercnv_pipeline(
            adata,
            reference_key="cell_type",
            reference_cat="Normal",
            window_size=10,
            step=5
        )

        # CNV matrix will have very few windows; n_pcs=50 should be capped
        cluster_by_cnv(adata, key="cnv", n_pcs=50, resolution=0.5)
        self.assertIn("cnv_leiden", adata.obs.columns)

    def test_identify_cnv_regions(self):
        """Test CNV region identification."""
        adata = self.create_test_anndata(n_cells=50, n_genes=200)

        run_infercnv_pipeline(
            adata,
            reference_key="cell_type",
            reference_cat="Normal"
        )

        regions = identify_cnv_regions(adata, key="cnv", threshold=0.3)

        self.assertIsInstance(regions, pd.DataFrame)
        if not regions.empty:
            self.assertIn("chromosome", regions.columns)
            self.assertIn("mean_cnv", regions.columns)
            self.assertIn("abs_mean_cnv", regions.columns)
            self.assertIn("n_cells_altered", regions.columns)
            self.assertIn("n_cells_amp", regions.columns)
            self.assertIn("n_cells_del", regions.columns)
            self.assertIn("n_amp_events", regions.columns)
            self.assertIn("n_del_events", regions.columns)

    def test_summarize_cnv_by_chromosome(self):
        """Test CNV summarization by chromosome."""
        adata = self.create_test_anndata(n_cells=30, n_genes=150)

        run_infercnv_pipeline(
            adata,
            reference_key="cell_type",
            reference_cat="Normal"
        )

        # Without groupby
        summary_all = summarize_cnv_by_chromosome(adata, key="cnv")
        self.assertIsInstance(summary_all, pd.DataFrame)
        self.assertIn("chromosome", summary_all.columns)
        self.assertIn("mean_cnv", summary_all.columns)
        self.assertTrue(all(summary_all["group"] == "all"))

        # With groupby
        summary_grouped = summarize_cnv_by_chromosome(
            adata, key="cnv", groupby="cell_type"
        )
        self.assertIsInstance(summary_grouped, pd.DataFrame)
        self.assertIn("group", summary_grouped.columns)
        self.assertGreater(summary_grouped["group"].nunique(), 0)

    def test_calculate_cnv_score_cell_level(self):
        """Test cell-level CNV score calculation."""
        adata = self.create_test_anndata(n_cells=30, n_genes=150)

        run_infercnv_pipeline(
            adata,
            reference_key="cell_type",
            reference_cat="Normal"
        )

        calculate_cnv_score(adata, method="cell", key_added="cnv_score")
        self.assertIn("cnv_score", adata.obs.columns)
        self.assertEqual(len(adata.obs["cnv_score"]), adata.n_obs)

    def test_calculate_cnv_score_cluster_level(self):
        """Test cluster-level CNV score calculation."""
        adata = self.create_test_anndata(n_cells=30, n_genes=150)

        run_infercnv_pipeline(
            adata,
            reference_key="cell_type",
            reference_cat="Normal"
        )
        cluster_by_cnv(adata, key="cnv", resolution=0.5)

        calculate_cnv_score(
            adata, method="cluster", groupby="cnv_leiden", key_added="cluster_cnv_score"
        )
        self.assertIn("cluster_cnv_score", adata.obs.columns)
        # All cells in same cluster should have same score
        for cluster in adata.obs["cnv_leiden"].unique():
            scores = adata.obs.loc[adata.obs["cnv_leiden"] == cluster, "cluster_cnv_score"]
            self.assertEqual(scores.nunique(), 1)

    def test_export_cnv_results(self):
        """Test CNV result export."""
        adata = self.create_test_anndata(n_cells=20, n_genes=100)

        run_infercnv_pipeline(
            adata,
            reference_key="cell_type",
            reference_cat="Normal"
        )
        cluster_by_cnv(adata, key="cnv", resolution=0.5)

        with tempfile.TemporaryDirectory() as tmpdir:
            export_cnv_results(adata, output_dir=tmpdir, key="cnv", prefix="test")

            # Check expected files exist with correct naming
            self.assertTrue((Path(tmpdir) / "test_infercnv_matrix.csv.gz").exists())
            self.assertTrue((Path(tmpdir) / "test_infercnv_chr_pos.csv").exists())
            self.assertTrue((Path(tmpdir) / "test_infercnv_cell_metadata.csv").exists())


class TestErrors(unittest.TestCase):
    """Test error handling."""

    @unittest.skipUnless(INFERCNVPY_AVAILABLE, "infercnvpy not installed")
    def test_missing_positions(self):
        """Test error when gene positions missing."""
        adata = sc.AnnData(
            X=np.random.poisson(5, (20, 100)),
            obs=pd.DataFrame({'cell_type': ['Tumor'] * 20})
        )

        with self.assertRaises(ValueError) as context:
            run_infercnv_pipeline(adata, "cell_type", "Normal")

        self.assertIn("Gene positions not found", str(context.exception))

    @unittest.skipUnless(INFERCNVPY_AVAILABLE, "infercnvpy not installed")
    def test_calculate_cnv_score_missing_groupby(self):
        """Test error when groupby column missing for cluster method."""
        adata = _create_test_anndata(n_cells=10, n_genes=50)
        # Simulate CNV results without actually running infercnv
        adata.obsm["X_cnv"] = np.random.randn(adata.n_obs, 10)

        with self.assertRaises(ValueError) as ctx:
            calculate_cnv_score(adata, method="cluster", groupby="nonexistent")

        self.assertIn("not found", str(ctx.exception).lower())


if __name__ == '__main__':
    print(f"infercnvpy available: {INFERCNVPY_AVAILABLE}")
    print("Running tests...\n")
    unittest.main(verbosity=2)
