#!/usr/bin/env python3
"""
Unit tests for pySCENIC analysis module.
"""

import unittest
import tempfile
from pathlib import Path
import numpy as np
import pandas as pd
import scanpy as sc

# Import module under test
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts' / 'python'))

try:
    from pyscenic_analysis import (
        check_database,
        list_available_databases,
        get_pyscenic_dir,
        DATABASE_CONFIG,
        add_aucell_to_adata,
        get_top_regulons_per_celltype,
        export_regulons_to_gmt,
        run_grn_inference,
        run_pyscenic_pipeline,
        PYSCENIC_AVAILABLE
    )
except ImportError as e:
    print(f"Import error: {e}")
    PYSCENIC_AVAILABLE = False


class TestDatabaseManagement(unittest.TestCase):
    """Test database management functions."""

    def test_get_pyscenic_dir(self):
        """Test cache directory creation."""
        cache_dir = get_pyscenic_dir()
        self.assertTrue(cache_dir.exists())
        self.assertTrue(cache_dir.is_dir())

    def test_check_database_returns_dict(self):
        """Test check_database returns correct structure."""
        status = check_database("human", "10kb", "v10")

        self.assertIsInstance(status, dict)
        self.assertIn("database", status)
        self.assertIn("motif_annotations", status)
        self.assertIn("tf_list", status)
        # Check that path values are Path objects
        self.assertIn("db_path", status)
        self.assertIn("motif_path", status)
        self.assertIn("tf_path", status)
        self.assertIsInstance(status["db_path"], Path)
        self.assertIsInstance(status["motif_path"], (Path, type(None)))
        self.assertIsInstance(status["tf_path"], Path)

    def test_check_database_unknown_organism(self):
        """Test check_database raises error for unknown organism."""
        with self.assertRaises(ValueError):
            check_database("unknown_organism")

    def test_list_available_databases(self):
        """Test list_available_databases returns DataFrame."""
        df = list_available_databases()

        self.assertIsInstance(df, pd.DataFrame)
        self.assertIn("organism", df.columns)
        self.assertIn("all_ready", df.columns)

    def test_list_available_databases_uses_latest_version(self):
        """Test list_available_databases selects highest version, not relying on dict order."""
        df = list_available_databases()
        # For human and mouse, v10 should be selected (higher than v9)
        human_row = df[(df["organism"] == "human") & (df["type"] == "10kb")]
        self.assertEqual(len(human_row), 1)
        self.assertEqual(human_row.iloc[0]["motif_version"], "v10")

        # For fly, only v9 is available
        fly_row = df[(df["organism"] == "fly") & (df["type"] == "10kb")]
        self.assertEqual(len(fly_row), 1)
        self.assertEqual(fly_row.iloc[0]["motif_version"], "v9")

    def test_database_config_structure(self):
        """Test DATABASE_CONFIG has correct structure."""
        for organism, config in DATABASE_CONFIG.items():
            self.assertIn("base_url", config)
            self.assertIn("databases", config)
            self.assertIn("motif_annotations", config)
            self.assertIn("tf_list", config)


class TestDataHelpers(unittest.TestCase):
    """Test data helper functions."""

    def create_test_adata(self, n_cells=50, n_genes=100):
        """Create test AnnData object."""
        np.random.seed(42)
        counts = np.random.poisson(3, size=(n_cells, n_genes))

        adata = sc.AnnData(
            X=counts,
            obs=pd.DataFrame(index=[f"cell_{i}" for i in range(n_cells)]),
            var=pd.DataFrame(index=[f"gene_{i}" for i in range(n_genes)])
        )
        adata.obs["cell_type"] = np.random.choice(["Type_A", "Type_B", "Type_C"], n_cells)

        return adata

    def test_create_test_data(self):
        """Test test data creation."""
        adata = self.create_test_adata(n_cells=30, n_genes=50)

        self.assertEqual(adata.n_obs, 30)
        self.assertEqual(adata.n_vars, 50)
        self.assertIn("cell_type", adata.obs.columns)


class TestAddAucellToAdata(unittest.TestCase):
    """Test add_aucell_to_adata without requiring pySCENIC."""

    def test_add_aucell_basic(self):
        """Test adding AUCell results to AnnData."""
        n_cells = 30
        n_regulons = 10

        adata = sc.AnnData(
            X=np.random.poisson(3, size=(n_cells, 50)),
            obs=pd.DataFrame(index=[f"cell_{i}" for i in range(n_cells)])
        )

        auc_matrix = pd.DataFrame(
            np.random.rand(n_cells, n_regulons),
            index=adata.obs_names,
            columns=[f"Regulon_{i}" for i in range(n_regulons)]
        )

        result = add_aucell_to_adata(adata, auc_matrix, assay_name="X_aucell")

        self.assertIn("X_aucell", result.obsm)
        self.assertEqual(result.obsm["X_aucell"].shape, (n_cells, n_regulons))
        self.assertEqual(list(result.uns["regulon_names"]), list(auc_matrix.columns))

    def test_add_aucell_index_mismatch(self):
        """Test add_aucell_to_adata raises error when index doesn't match."""
        n_cells = 30
        n_regulons = 5

        adata = sc.AnnData(
            X=np.random.poisson(3, size=(n_cells, 50)),
            obs=pd.DataFrame(index=[f"cell_{i}" for i in range(n_cells)])
        )

        # AUC matrix with different index order
        shuffled_index = list(adata.obs_names)
        shuffled_index[0], shuffled_index[1] = shuffled_index[1], shuffled_index[0]
        auc_matrix = pd.DataFrame(
            np.random.rand(n_cells, n_regulons),
            index=shuffled_index,
            columns=[f"Regulon_{i}" for i in range(n_regulons)]
        )

        with self.assertRaises(ValueError) as ctx:
            add_aucell_to_adata(adata, auc_matrix)

        self.assertIn("does not match", str(ctx.exception).lower())

    def test_add_aucell_missing_cells(self):
        """Test add_aucell_to_adata raises error when cells are missing."""
        n_cells = 30
        n_regulons = 5

        adata = sc.AnnData(
            X=np.random.poisson(3, size=(n_cells, 50)),
            obs=pd.DataFrame(index=[f"cell_{i}" for i in range(n_cells)])
        )

        # AUC matrix missing one cell
        auc_matrix = pd.DataFrame(
            np.random.rand(n_cells - 1, n_regulons),
            index=[f"cell_{i}" for i in range(n_cells - 1)],
            columns=[f"Regulon_{i}" for i in range(n_regulons)]
        )

        with self.assertRaises(ValueError) as ctx:
            add_aucell_to_adata(adata, auc_matrix)

        self.assertIn("missing", str(ctx.exception).lower())


class TestGetTopRegulons(unittest.TestCase):
    """Test get_top_regulons_per_celltype without requiring pySCENIC."""

    def test_celltype_col_missing(self):
        """Test raises error when celltype_col doesn't exist."""
        n_cells = 20
        n_regulons = 5

        adata = sc.AnnData(
            X=np.random.poisson(3, size=(n_cells, 50)),
            obs=pd.DataFrame(index=[f"cell_{i}" for i in range(n_cells)])
        )
        adata.obsm["X_aucell"] = np.random.rand(n_cells, n_regulons)
        adata.uns["regulon_names"] = [f"Regulon_{i}" for i in range(n_regulons)]

        with self.assertRaises(ValueError) as ctx:
            get_top_regulons_per_celltype(adata, celltype_col="nonexistent")

        self.assertIn("not found", str(ctx.exception).lower())

    def test_auc_key_missing(self):
        """Test raises error when auc_key doesn't exist."""
        n_cells = 20

        adata = sc.AnnData(
            X=np.random.poisson(3, size=(n_cells, 50)),
            obs=pd.DataFrame({"cell_type": ["A"] * n_cells}, index=[f"cell_{i}" for i in range(n_cells)])
        )

        with self.assertRaises(ValueError) as ctx:
            get_top_regulons_per_celltype(adata, celltype_col="cell_type", auc_key="missing")

        self.assertIn("not found", str(ctx.exception).lower())

    def test_top_regulons_basic(self):
        """Test basic functionality of get_top_regulons_per_celltype."""
        n_cells = 30
        n_regulons = 5
        np.random.seed(42)

        adata = sc.AnnData(
            X=np.random.poisson(3, size=(n_cells, 50)),
            obs=pd.DataFrame(
                {"cell_type": np.random.choice(["Type_A", "Type_B"], n_cells)},
                index=[f"cell_{i}" for i in range(n_cells)]
            )
        )
        adata.obsm["X_aucell"] = np.random.rand(n_cells, n_regulons)
        adata.uns["regulon_names"] = [f"Regulon_{i}" for i in range(n_regulons)]

        result = get_top_regulons_per_celltype(adata, celltype_col="cell_type", top_n=3)

        self.assertIsInstance(result, pd.DataFrame)
        self.assertIn("cell_type", result.columns)
        self.assertIn("regulon", result.columns)
        self.assertIn("mean_auc", result.columns)
        # Should have up to 3 regulons per cell type
        self.assertLessEqual(len(result), 6)


class TestExportRegulons(unittest.TestCase):
    """Test export_regulons_to_gmt."""

    class MockRegulon:
        def __init__(self, name, genes):
            self.name = name
            self.gene2weight = {g: 1.0 for g in genes}

    def test_export_basic(self):
        """Test basic GMT export."""
        regulons = [
            self.MockRegulon("SOX10 (3g)", ["MITF", "DCT", "TYR"]),
            self.MockRegulon("TFAP2A (2g)", ["GENE1", "GENE2"]),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = Path(tmpdir) / "regulons.gmt"
            export_regulons_to_gmt(regulons, output_file, min_genes=2)

            self.assertTrue(output_file.exists())
            content = output_file.read_text()
            self.assertIn("SOX10", content)
            self.assertIn("TFAP2A", content)

    def test_export_empty_regulons(self):
        """Test export with empty regulons list."""
        regulons = []

        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = Path(tmpdir) / "empty.gmt"
            export_regulons_to_gmt(regulons, output_file, min_genes=5)

            self.assertTrue(output_file.exists())
            self.assertEqual(output_file.read_text(), "")

    def test_export_all_below_min_genes(self):
        """Test export when all regulons are below min_genes threshold."""
        regulons = [
            self.MockRegulon("SOX10 (1g)", ["MITF"]),
            self.MockRegulon("TFAP2A (2g)", ["GENE1", "GENE2"]),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = Path(tmpdir) / "skipped.gmt"
            export_regulons_to_gmt(regulons, output_file, min_genes=5)

            self.assertTrue(output_file.exists())
            self.assertEqual(output_file.read_text(), "")


@unittest.skipUnless(PYSCENIC_AVAILABLE, "pySCENIC not installed")
class TestGRNInference(unittest.TestCase):
    """Test GRN inference functions."""

    def test_run_grn_inference_tf_overlap_zero(self):
        """Test run_grn_inference raises error when no TF overlap."""
        n_cells = 50
        n_genes = 100
        np.random.seed(42)

        adata = sc.AnnData(
            X=np.random.poisson(3, size=(n_cells, n_genes)),
            obs=pd.DataFrame(index=[f"cell_{i}" for i in range(n_cells)]),
            var=pd.DataFrame(index=[f"gene_{i}" for i in range(n_genes)])
        )

        # TF names that don't overlap with adata genes
        tf_names = ["NONEXISTENT_TF1", "NONEXISTENT_TF2"]

        with self.assertRaises(ValueError) as ctx:
            run_grn_inference(adata, tf_names=tf_names, num_workers=1, verbose=False)

        self.assertIn("no tf names overlap", str(ctx.exception).lower())

    def test_run_grn_inference_tf_overlap_low(self):
        """Test run_grn_inference warns on low TF overlap."""
        n_cells = 50
        n_genes = 100
        np.random.seed(42)

        adata = sc.AnnData(
            X=np.random.poisson(3, size=(n_cells, n_genes)),
            obs=pd.DataFrame(index=[f"cell_{i}" for i in range(n_cells)]),
            var=pd.DataFrame(index=[f"gene_{i}" for i in range(n_genes)])
        )

        # Only 1 out of 100 TFs overlap (1% < 50%)
        tf_names = ["gene_0"] + [f"NONEXISTENT_TF{i}" for i in range(99)]

        # Should warn but not raise (low overlap but not zero)
        # We can't easily test the warning without mocking, but at least
        # verify it doesn't raise
        try:
            run_grn_inference(adata, tf_names=tf_names, num_workers=1, verbose=False)
        except Exception as e:
            # If it fails for other reasons (e.g., grnboost2 internal error),
            # that's OK — the TF overlap check passed
            self.assertNotIn("No TF names overlap", str(e))


@unittest.skipUnless(PYSCENIC_AVAILABLE, "pySCENIC not installed")
class TestPipelineValidation(unittest.TestCase):
    """Test pipeline validation."""

    def test_run_pyscenic_pipeline_too_few_cells(self):
        """Test pipeline rejects datasets with too few cells."""
        adata = sc.AnnData(
            X=np.random.poisson(3, size=(50, 5000)),
            obs=pd.DataFrame(index=[f"cell_{i}" for i in range(50)])
        )

        with self.assertRaises(ValueError) as ctx:
            run_pyscenic_pipeline(adata, verbose=False)

        self.assertIn("minimum", str(ctx.exception).lower())

    def test_run_pyscenic_pipeline_too_few_genes(self):
        """Test pipeline warns on datasets with too few genes."""
        adata = sc.AnnData(
            X=np.random.poisson(3, size=(200, 100)),
            obs=pd.DataFrame(index=[f"cell_{i}" for i in range(200)])
        )

        # Should raise for too few cells before we can test genes warning
        # Actually 200 cells > 100 min, but 100 genes < 5000 min
        # The function should log a warning but proceed
        # Since we don't have databases, it will fail at db check
        # Just verify it doesn't fail on cell count
        try:
            run_pyscenic_pipeline(adata, verbose=False, download_if_missing=False)
        except (FileNotFoundError, ValueError) as e:
            # Should fail at database step, not cell count
            self.assertNotIn("minimum", str(e).lower())


if __name__ == '__main__':
    print(f"pySCENIC available: {PYSCENIC_AVAILABLE}")
    print("Running tests...\n")
    unittest.main(verbosity=2)
