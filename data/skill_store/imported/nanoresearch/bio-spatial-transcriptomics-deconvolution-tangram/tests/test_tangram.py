"""
Unit tests for Tangram spatial transcriptomics deconvolution skill.

Tests cover:
- Data preparation functions
- Mapping functions (mock tests)
- Gene projection
- Cell annotation projection
- Deconvolution result extraction
- Visualization functions
- Integration workflow

Author: Yang Guo
Date: 2026-04-03
"""

import sys
import os
import unittest
from unittest.mock import Mock, patch, MagicMock
import numpy as np
import pandas as pd
import warnings

# Add scripts/python to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts', 'python'))

# Suppress warnings during tests
warnings.filterwarnings('ignore')


class TestDataPreparation(unittest.TestCase):
    """Test data preparation functions."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_adata_sc = Mock()
        self.mock_adata_sp = Mock()

        # Mock basic AnnData properties
        self.mock_adata_sc.copy = Mock(return_value=self.mock_adata_sc)
        self.mock_adata_sp.copy = Mock(return_value=self.mock_adata_sp)
        self.mock_adata_sc.var_names = ['gene1', 'gene2', 'gene3']
        self.mock_adata_sp.var_names = ['gene1', 'gene2', 'gene4']

    @patch('core_analysis.check_tangram_installed')
    def test_prepare_data_basic(self, mock_check):
        """Test basic data preparation."""
        mock_tg = Mock()
        mock_check.return_value = mock_tg

        # Set up pp_adatas to add uns attribute
        def mock_pp_adatas(adata_sc, adata_sp, genes=None, gene_to_lowercase=True):
            adata_sc.uns = {'training_genes': ['gene1', 'gene2'], 'overlap_genes': ['gene1', 'gene2']}
            adata_sp.uns = {'training_genes': ['gene1', 'gene2'], 'overlap_genes': ['gene1', 'gene2']}

        mock_tg.pp_adatas.side_effect = mock_pp_adatas

        from core_analysis import prepare_data

        adata_sc, adata_sp = prepare_data(
            self.mock_adata_sc,
            self.mock_adata_sp,
            genes=None,
            copy=True,
        )

        mock_tg.pp_adatas.assert_called_once()
        self.assertIsNotNone(adata_sc)
        self.assertIsNotNone(adata_sp)

    @patch('core_analysis.check_tangram_installed')
    def test_prepare_data_with_genes(self, mock_check):
        """Test data preparation with gene list."""
        mock_tg = Mock()
        mock_check.return_value = mock_tg

        # Set up pp_adatas to add uns attribute
        def mock_pp_adatas(adata_sc, adata_sp, genes=None, gene_to_lowercase=True):
            adata_sc.uns = {'training_genes': ['gene1', 'gene2'], 'overlap_genes': ['gene1', 'gene2']}
            adata_sp.uns = {'training_genes': ['gene1', 'gene2'], 'overlap_genes': ['gene1', 'gene2']}

        mock_tg.pp_adatas.side_effect = mock_pp_adatas

        from core_analysis import prepare_data

        adata_sc, adata_sp = prepare_data(
            self.mock_adata_sc,
            self.mock_adata_sp,
            genes=['gene1', 'gene2'],
            gene_to_lowercase=True,
        )

        mock_tg.pp_adatas.assert_called_once()


class TestMappingFunctions(unittest.TestCase):
    """Test mapping functions."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_adata_sc = Mock()
        self.mock_adata_sp = Mock()
        self.mock_adata_map = Mock()

        # Set up return values
        self.mock_adata_map.X = np.random.rand(10, 20)
        self.mock_adata_map.n_obs = 10
        self.mock_adata_map.obs_names = [f'cell_{i}' for i in range(10)]
        self.mock_adata_map.var_names = [f'spot_{i}' for i in range(20)]

    @patch('core_analysis.check_tangram_installed')
    def test_map_cells_to_space_clusters_mode(self, mock_check):
        """Test cell mapping in clusters mode."""
        mock_tg = Mock()
        mock_tg.map_cells_to_space.return_value = self.mock_adata_map
        mock_check.return_value = mock_tg

        from core_analysis import map_cells_to_space

        # Mock torch import to avoid dependency
        with patch('core_analysis.torch'):
            result = map_cells_to_space(
                adata_sc=self.mock_adata_sc,
                adata_sp=self.mock_adata_sp,
                mode='clusters',
                cluster_label='cell_type',
                num_epochs=100,
                device='cpu',
            )

        self.assertIsNotNone(result)
        mock_tg.map_cells_to_space.assert_called_once()

    @patch('core_analysis.check_tangram_installed')
    def test_map_cells_to_space_cells_mode(self, mock_check):
        """Test cell mapping in cells mode."""
        mock_tg = Mock()
        mock_tg.map_cells_to_space.return_value = self.mock_adata_map
        mock_check.return_value = mock_tg

        from core_analysis import map_cells_to_space

        # Mock torch import to avoid dependency
        with patch('core_analysis.torch'):
            result = map_cells_to_space(
                adata_sc=self.mock_adata_sc,
                adata_sp=self.mock_adata_sp,
                mode='cells',
                num_epochs=100,
                device='cpu',
            )

        self.assertIsNotNone(result)

    def test_map_cells_to_space_invalid_mode(self):
        """Test that invalid mode raises error."""
        from core_analysis import map_cells_to_space

        with self.assertRaises(ValueError):
            map_cells_to_space(
                adata_sc=self.mock_adata_sc,
                adata_sp=self.mock_adata_sp,
                mode='invalid_mode',
            )

    def test_map_cells_to_space_missing_cluster_label(self):
        """Test that clusters mode without cluster_label raises error."""
        from core_analysis import map_cells_to_space

        with self.assertRaises(ValueError):
            map_cells_to_space(
                adata_sc=self.mock_adata_sc,
                adata_sp=self.mock_adata_sp,
                mode='clusters',
                cluster_label=None,
            )


class TestGeneProjection(unittest.TestCase):
    """Test gene projection functions."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_adata_map = Mock()
        self.mock_adata_sc = Mock()

        self.mock_adata_ge = Mock()
        self.mock_adata_ge.var = Mock()
        self.mock_adata_ge.var.__getitem__ = Mock(return_value=pd.Series([True, False]))

    @patch('core_analysis.check_tangram_installed')
    def test_project_genes(self, mock_check):
        """Test gene projection."""
        mock_tg = Mock()
        mock_tg.project_genes.return_value = self.mock_adata_ge
        mock_check.return_value = mock_tg

        from core_analysis import project_genes

        result = project_genes(
            adata_map=self.mock_adata_map,
            adata_sc=self.mock_adata_sc,
            cluster_label=None,
            scale=True,
        )

        self.assertIsNotNone(result)
        mock_tg.project_genes.assert_called_once()

    @patch('core_analysis.check_tangram_installed')
    def test_compare_spatial_geneexp(self, mock_check):
        """Test gene expression comparison."""
        mock_tg = Mock()
        mock_df = pd.DataFrame({
            'score': [0.8, 0.9, 0.7],
            'is_training': [True, True, False],
            'sparsity_sp': [0.1, 0.2, 0.3],
        })
        mock_tg.compare_spatial_geneexp.return_value = mock_df
        mock_check.return_value = mock_tg

        from core_analysis import compare_spatial_geneexp

        mock_adata_ge = Mock()
        mock_adata_sp = Mock()

        result = compare_spatial_geneexp(
            adata_ge=mock_adata_ge,
            adata_sp=mock_adata_sp,
            adata_sc=None,
        )

        self.assertIsNotNone(result)
        self.assertIn('score', result.columns)


class TestCellAnnotation(unittest.TestCase):
    """Test cell annotation projection functions."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_adata_map = Mock()
        self.mock_adata_sp = Mock()

        # Mock obsm for projections
        self.mock_df_pred = pd.DataFrame(
            np.random.rand(10, 3),
            columns=['Type1', 'Type2', 'Type3']
        )
        self.mock_adata_sp.obsm = {'tangram_ct_pred': self.mock_df_pred}
        self.mock_adata_sp.obs_names = [f'spot_{i}' for i in range(10)]

    @patch('core_analysis.check_tangram_installed')
    def test_project_cell_annotations(self, mock_check):
        """Test cell annotation projection."""
        mock_tg = Mock()
        mock_check.return_value = mock_tg

        from core_analysis import project_cell_annotations

        project_cell_annotations(
            adata_map=self.mock_adata_map,
            adata_sp=self.mock_adata_sp,
            annotation='cell_type',
        )

        mock_tg.project_cell_annotations.assert_called_once()

    def test_extract_deconvolution_results(self):
        """Test extraction of deconvolution results."""
        from core_analysis import extract_deconvolution_results

        result = extract_deconvolution_results(
            adata_sp=self.mock_adata_sp,
            annotation_key='tangram_ct_pred',
            normalize=True,
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.shape, (10, 3))
        self.assertListEqual(list(result.columns), ['Type1', 'Type2', 'Type3'])

    def test_extract_deconvolution_results_missing_key(self):
        """Test extraction with missing key raises error."""
        from core_analysis import extract_deconvolution_results

        with self.assertRaises(KeyError):
            extract_deconvolution_results(
                adata_sp=self.mock_adata_sp,
                annotation_key='missing_key',
            )


class TestEvaluationFunctions(unittest.TestCase):
    """Test evaluation and cross-validation functions."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_adata_sc = Mock()
        self.mock_adata_sp = Mock()

    @patch('core_analysis.check_tangram_installed')
    def test_cross_val(self, mock_check):
        """Test cross-validation."""
        mock_tg = Mock()
        cv_dict = {'avg_test_score': 0.8, 'avg_train_score': 0.9}
        mock_tg.cross_val.return_value = cv_dict
        mock_check.return_value = mock_tg

        from core_analysis import cross_val

        result = cross_val(
            adata_sc=self.mock_adata_sc,
            adata_sp=self.mock_adata_sp,
            mode='clusters',
            cluster_label='cell_type',
            cv_mode='loo',
            return_gene_pred=False,
        )

        self.assertIsNotNone(result)
        self.assertIn('avg_test_score', result)

    @patch('core_analysis.check_tangram_installed')
    def test_eval_metric(self, mock_check):
        """Test evaluation metrics."""
        mock_tg = Mock()
        metric_dict = {
            'avg_test_score': 0.8,
            'avg_train_score': 0.9,
            'sp_sparsity_score': 0.85,
            'auc_score': 0.75,
        }
        auc_coords = (([0, 0.5, 1], [0, 0.5, 1]), ([0.1, 0.5, 0.9], [0.2, 0.5, 0.8]))
        mock_tg.eval_metric.return_value = (metric_dict, auc_coords)
        mock_check.return_value = mock_tg

        from core_analysis import eval_metric

        mock_df = pd.DataFrame({
            'score': [0.8, 0.9],
            'is_training': [True, False],
            'sparsity_sp': [0.1, 0.2],
        })

        metrics, coords = eval_metric(mock_df, test_genes=None)

        self.assertIsNotNone(metrics)
        self.assertIn('auc_score', metrics)


class TestUtilityFunctions(unittest.TestCase):
    """Test utility functions."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_adata_map = Mock()
        self.mock_df_scores = pd.DataFrame({
            'train_score': [0.8, 0.9, 0.7, 0.85],
            'sparsity_sc': [0.1, 0.2, 0.3, 0.15],
            'sparsity_sp': [0.15, 0.25, 0.35, 0.2],
            'sparsity_diff': [0.05, 0.05, 0.05, 0.05],
        })
        self.mock_adata_map.uns = {'train_genes_df': self.mock_df_scores}

    def test_get_training_scores(self):
        """Test getting training scores."""
        from core_analysis import get_training_scores

        result = get_training_scores(self.mock_adata_map)

        self.assertIsNotNone(result)
        self.assertEqual(len(result), 4)
        self.assertIn('train_score', result.columns)

    def test_get_training_scores_missing_key(self):
        """Test getting training scores with missing key."""
        from core_analysis import get_training_scores

        mock_adata = Mock()
        mock_adata.uns = {}

        with self.assertRaises(KeyError):
            get_training_scores(mock_adata)

    def test_check_mapping_quality(self):
        """Test mapping quality check."""
        from core_analysis import check_mapping_quality

        result = check_mapping_quality(self.mock_adata_map, min_score=0.5)

        self.assertIsNotNone(result)
        self.assertIn('avg_score', result)
        self.assertIn('passes_threshold', result)
        self.assertEqual(result['n_training_genes'], 4)


class TestVisualizationFunctions(unittest.TestCase):
    """Test visualization functions with mocks."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_adata_map = Mock()
        self.mock_adata_sp = Mock()

        # Mock uns for training scores
        self.mock_df_scores = pd.DataFrame({
            'train_score': [0.8, 0.9, 0.7],
            'sparsity_sc': [0.1, 0.2, 0.3],
            'sparsity_sp': [0.15, 0.25, 0.35],
            'sparsity_diff': [0.05, 0.05, 0.05],
        })
        self.mock_adata_map.uns = {'train_genes_df': self.mock_df_scores}

        # Mock obsm for projections
        self.mock_df_pred = pd.DataFrame(
            np.random.rand(10, 3),
            columns=['Type1', 'Type2', 'Type3']
        )
        self.mock_adata_sp.obsm = {'tangram_ct_pred': self.mock_df_pred}
        self.mock_adata_sp.obs_names = [f'spot_{i}' for i in range(10)]
        self.mock_adata_sp.uns = {}

    @patch('visualization.check_tangram_installed')
    @patch('matplotlib.figure.Figure.savefig')
    def test_plot_training_scores(self, mock_savefig, mock_check):
        """Test training scores plot."""
        mock_tg = Mock()
        mock_check.return_value = mock_tg

        from visualization import plot_training_scores

        fig = plot_training_scores(self.mock_adata_map, save_path='test.png')

        self.assertIsNotNone(fig)
        mock_savefig.assert_called_once()

    @patch('matplotlib.figure.Figure.savefig')
    def test_plot_cell_type_map(self, mock_savefig):
        """Test cell type map plot."""
        from visualization import plot_cell_type_map

        # Need both tangram_ct_pred and spatial
        self.mock_adata_sp.obsm = {
            'tangram_ct_pred': self.mock_df_pred,
            'spatial': np.random.rand(10, 2)
        }

        fig = plot_cell_type_map(
            self.mock_adata_sp,
            'Type1',
            save_path='test.png'
        )

        self.assertIsNotNone(fig)
        mock_savefig.assert_called()

    def test_plot_cell_type_map_missing_key(self):
        """Test cell type map with missing key raises error."""
        from visualization import plot_cell_type_map

        mock_adata = Mock()
        mock_adata.obsm = {}

        with self.assertRaises(KeyError):
            plot_cell_type_map(mock_adata, 'Type1')

    @patch('visualization.plt.scatter')
    @patch('matplotlib.figure.Figure.savefig')
    def test_plot_annotation_comparison(self, mock_savefig, mock_scatter):
        """Test annotation comparison plot."""
        from visualization import plot_annotation_comparison

        self.mock_adata_sp.obsm = {'tangram_ct_pred': self.mock_df_pred, 'spatial': np.random.rand(10, 2)}

        fig = plot_annotation_comparison(
            self.mock_adata_sp,
            cell_types=['Type1', 'Type2'],
            n_cols=2,
            save_path='test.png'
        )

        self.assertIsNotNone(fig)


class TestIntegration(unittest.TestCase):
    """Integration tests for complete workflow."""

    @patch('core_analysis.check_tangram_installed')
    def test_full_workflow_mock(self, mock_check):
        """Test complete workflow with mocks."""
        mock_tg = Mock()

        # Set up mock return values
        mock_adata_map = Mock()
        mock_adata_map.X = np.random.rand(5, 10)
        mock_adata_map.n_obs = 5
        mock_adata_map.obs_names = ['c1', 'c2', 'c3', 'c4', 'c5']
        mock_adata_map.var_names = ['s1', 's2', 's3', 's4', 's5', 's6', 's7', 's8', 's9', 's10']
        mock_adata_map.uns = {
            'train_genes_df': pd.DataFrame({
                'train_score': [0.8, 0.9],
                'sparsity_sc': [0.1, 0.2],
                'sparsity_sp': [0.15, 0.25],
                'sparsity_diff': [0.05, 0.05],
            })
        }

        mock_tg.map_cells_to_space.return_value = mock_adata_map
        mock_tg.project_genes.return_value = Mock()
        mock_tg.compare_spatial_geneexp.return_value = pd.DataFrame({
            'score': [0.8, 0.9],
            'is_training': [True, False],
            'sparsity_sp': [0.1, 0.2],
        })
        mock_tg.cross_val.return_value = {'avg_test_score': 0.8, 'avg_train_score': 0.9}

        # Set up pp_adatas side_effect to add uns attribute
        def mock_pp_adatas(adata_sc, adata_sp, genes=None, gene_to_lowercase=True):
            adata_sc.uns = {'training_genes': ['gene1', 'gene2'], 'overlap_genes': ['gene1', 'gene2']}
            adata_sp.uns = {'training_genes': ['gene1', 'gene2'], 'overlap_genes': ['gene1', 'gene2']}

        mock_tg.pp_adatas.side_effect = mock_pp_adatas

        mock_check.return_value = mock_tg

        from core_analysis import (
            prepare_data,
            map_cells_to_space,
            project_genes,
            compare_spatial_geneexp,
            cross_val,
        )

        # Create mock AnnDatas
        mock_adata_sc = Mock()
        mock_adata_sp = Mock()

        # Run workflow
        adata_sc, adata_sp = prepare_data(mock_adata_sc, mock_adata_sp)

        # Mock torch for map_cells_to_space
        with patch('core_analysis.torch'):
            adata_map = map_cells_to_space(adata_sc, adata_sp, mode='clusters', cluster_label='cell_type')

        adata_ge = project_genes(adata_map, adata_sc)
        df_compare = compare_spatial_geneexp(adata_ge, adata_sp)
        cv_result = cross_val(adata_sc, adata_sp, mode='clusters', cluster_label='cell_type')

        # Verify results
        self.assertIsNotNone(adata_map)
        self.assertIsNotNone(df_compare)
        # cross_val returns cv_dict directly when return_gene_pred=False
        self.assertIn('avg_test_score', cv_result)


class TestErrorHandling(unittest.TestCase):
    """Test error handling and edge cases."""

    def test_import_error(self):
        """Test handling of missing tangram import."""
        with patch.dict('sys.modules', {'tangram': None}):
            with self.assertRaises(ImportError):
                from core_analysis import check_tangram_installed
                check_tangram_installed()

    def test_empty_projections(self):
        """Test handling of empty projections."""
        from core_analysis import extract_deconvolution_results

        mock_adata = Mock()
        mock_adata.obsm = {'tangram_ct_pred': pd.DataFrame()}
        mock_adata.obs_names = []

        result = extract_deconvolution_results(mock_adata, normalize=True)
        self.assertEqual(len(result), 0)


if __name__ == '__main__':
    # Run tests
    unittest.main(verbosity=2)
