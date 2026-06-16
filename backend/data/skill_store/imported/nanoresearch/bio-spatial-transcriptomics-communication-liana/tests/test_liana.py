#!/usr/bin/env python
"""
Unit Tests for LIANA+ Cell-Cell Communication Module

Run with: python tests/test_liana.py
"""

import unittest
import numpy as np
import pandas as pd
import scanpy as sc
from scipy.sparse import csr_matrix
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../scripts/python'))

from core_analysis import (
    get_top_interactions, summarize_by_cell_pair, export_results
)
from utils import validate_anndata, filter_cell_types, subset_cell_types, get_interaction_matrix


class TestDataPreparation(unittest.TestCase):
    """Test data preparation and validation functions."""

    @classmethod
    def setUpClass(cls):
        np.random.seed(42)
        n_cells = 100
        n_genes = 200
        X = np.random.poisson(2, size=(n_cells, n_genes))

        cls.adata = sc.AnnData(
            X=csr_matrix(X),
            obs=pd.DataFrame({
                'cell_type': np.random.choice(['A', 'B', 'C'], n_cells),
                'condition': np.random.choice(['ctrl', 'test'], n_cells)
            }, index=[f'cell_{i}' for i in range(n_cells)]),
            var=pd.DataFrame(index=[f'gene_{i}' for i in range(n_genes)])
        )

    def test_validate_anndata_valid(self):
        self.assertTrue(validate_anndata(self.adata, require_cell_types=True))

    def test_validate_anndata_missing_column(self):
        adata_no_ct = self.adata.copy()
        del adata_no_ct.obs['cell_type']
        with self.assertRaises(ValueError):
            validate_anndata(adata_no_ct, require_cell_types=True)

    def test_validate_anndata_empty(self):
        empty = sc.AnnData(X=csr_matrix((0, 10)))
        with self.assertRaises(ValueError):
            validate_anndata(empty)

    def test_filter_cell_types(self):
        filtered = filter_cell_types(self.adata, min_cells=5, min_expr_genes=1)
        self.assertIsInstance(filtered, sc.AnnData)
        self.assertLessEqual(filtered.n_obs, self.adata.n_obs)

    def test_subset_cell_types(self):
        subset = subset_cell_types(self.adata, cell_types=['A', 'B'])
        self.assertTrue(all(subset.obs['cell_type'].isin(['A', 'B'])))


class TestResultProcessing(unittest.TestCase):
    """Test result processing functions."""

    @classmethod
    def setUpClass(cls):
        np.random.seed(42)
        cls.mock_results = pd.DataFrame({
            'source': ['A'] * 20 + ['B'] * 20 + ['C'] * 10,
            'target': np.random.choice(['A', 'B', 'C'], 50),
            'ligand': [f'L{i}' for i in range(50)],
            'receptor': [f'R{i}' for i in range(50)],
            'magnitude_rank': np.random.uniform(0, 1, 50),
            'specificity_rank': np.random.uniform(0, 1, 50),
            'ligand_props': np.random.uniform(0.1, 1, 50),
            'receptor_props': np.random.uniform(0.1, 1, 50)
        })

    def test_get_top_interactions(self):
        top = get_top_interactions(self.mock_results, n=10, by='magnitude_rank')
        self.assertEqual(len(top), 10)

    def test_get_top_interactions_filter_source(self):
        top = get_top_interactions(
            self.mock_results, n=20, source_cells=['A']
        )
        self.assertTrue(all(top['source'] == 'A'))

    def test_get_top_interactions_filter_lr(self):
        top = get_top_interactions(
            self.mock_results, ligand='L0', receptor='R0'
        )
        self.assertEqual(len(top), 1)

    def test_summarize_by_cell_pair_count(self):
        summary = summarize_by_cell_pair(self.mock_results, agg_func='count')
        self.assertIsInstance(summary, pd.DataFrame)
        self.assertGreater(len(summary), 0)

    def test_summarize_by_cell_pair_mean(self):
        summary = summarize_by_cell_pair(
            self.mock_results, agg_func='mean', value_col='magnitude_rank'
        )
        self.assertIsInstance(summary, pd.DataFrame)

    def test_get_interaction_matrix(self):
        matrix = get_interaction_matrix(
            self.mock_results, value_col='magnitude_rank'
        )
        self.assertIsInstance(matrix, pd.DataFrame)
        self.assertIn('A', matrix.index)
        self.assertIn('A', matrix.columns)


class TestExportFunctions(unittest.TestCase):
    """Test export functions."""

    @classmethod
    def setUpClass(cls):
        cls.mock_results = pd.DataFrame({
            'source': ['A', 'B', 'C'],
            'target': ['B', 'C', 'A'],
            'ligand': ['L1', 'L2', 'L3'],
            'receptor': ['R1', 'R2', 'R3'],
            'magnitude_rank': [0.1, 0.2, 0.3]
        })
        cls.temp_csv = '/tmp/test_liana_export.csv'
        cls.temp_tsv = '/tmp/test_liana_export.tsv'

    def test_export_csv(self):
        export_results(self.mock_results, self.temp_csv, format='csv')
        self.assertTrue(os.path.exists(self.temp_csv))
        loaded = pd.read_csv(self.temp_csv)
        self.assertEqual(len(loaded), 3)

    def test_export_tsv(self):
        export_results(self.mock_results, self.temp_tsv, format='tsv')
        self.assertTrue(os.path.exists(self.temp_tsv))
        loaded = pd.read_csv(self.temp_tsv, sep='\t')
        self.assertEqual(len(loaded), 3)

    def test_export_invalid_format(self):
        with self.assertRaises(ValueError):
            export_results(self.mock_results, '/tmp/test.pdf', format='pdf')

    @classmethod
    def tearDownClass(cls):
        for f in [cls.temp_csv, cls.temp_tsv]:
            if os.path.exists(f):
                os.remove(f)


if __name__ == '__main__':
    unittest.main(verbosity=2)
