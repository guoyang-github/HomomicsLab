"""Unit tests for CellTypist annotation skill.

Comprehensive test suite for the CellTypist wrapper functions.
"""

import unittest
import numpy as np
import pandas as pd
import scanpy as sc
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add scripts to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../scripts/python'))

from core_analysis import (
    validate_celltypist_input,
    get_available_models,
    download_celltypist_model,
    load_celltypist_model,
    annotate_cells,
    add_predictions_to_adata,
    run_celltypist_annotation,
    filter_by_confidence,
    get_model_info,
    train_celltypist_model,
    compare_models,
)
from utils import (
    create_test_data,
    prepare_data_for_celltypist,
    get_model_catalog,
    recommend_model,
    summarize_annotations,
    check_gene_overlap,
    export_annotations,
    create_annotation_report,
)


class TestCoreAnalysis(unittest.TestCase):
    """Test core analysis functions."""

    def setUp(self):
        """Create test data."""
        np.random.seed(42)
        self.adata = sc.AnnData(
            X=np.random.lognormal(3, 1, (100, 500)),
            obs=pd.DataFrame(index=[f"cell_{i}" for i in range(100)]),
            var=pd.DataFrame(index=[f"GENE_{i}" for i in range(500)])
        )

    def test_validate_input(self):
        """Test input validation."""
        result = validate_celltypist_input(self.adata)

        self.assertIn('valid', result)
        self.assertIn('n_cells', result)
        self.assertIn('n_genes', result)
        self.assertTrue(result['valid'])

    def test_validate_input_empty(self):
        """Test validation with empty data."""
        empty_adata = sc.AnnData(X=np.zeros((0, 10)))
        result = validate_celltypist_input(empty_adata)

        self.assertFalse(result['valid'])
        self.assertTrue(len(result['errors']) > 0)

    def test_validate_input_ensembl(self):
        """Test validation detects ENSEMBL IDs."""
        adata = sc.AnnData(
            X=np.random.lognormal(3, 1, (10, 10)),
            var=pd.DataFrame(index=[f"ENSG00000{i}" for i in range(10)])
        )
        result = validate_celltypist_input(adata)
        self.assertTrue(any('ENSEMBL' in w for w in result['warnings']))

    def test_validate_input_raw_counts(self):
        """Test validation detects raw counts."""
        adata = sc.AnnData(
            X=np.random.poisson(50, (10, 10)).astype(float)
        )
        result = validate_celltypist_input(adata)
        self.assertTrue(any('raw counts' in w.lower() for w in result['warnings']))

    @patch('core_analysis.celltypist.models.models_description')
    def test_get_available_models(self, mock_models_desc):
        """Test getting available models."""
        mock_models_desc.return_value = pd.DataFrame({
            'model_name': ['Immune_All_Low.pkl', 'Immune_All_High.pkl']
        })

        models = get_available_models()
        self.assertIsInstance(models, pd.DataFrame)

    @patch('core_analysis.celltypist.models.Model.load')
    @patch('core_analysis.celltypist.models.download_models')
    def test_download_model(self, mock_download, mock_load):
        """Test model downloading."""
        mock_load.side_effect = [Exception("Not found"), None]

        download_celltypist_model('Immune_All_Low.pkl')
        mock_download.assert_called_once()

    @patch('core_analysis.celltypist.models.Model.load')
    def test_load_model(self, mock_load):
        """Test model loading."""
        load_celltypist_model('Immune_All_Low.pkl')
        mock_load.assert_called_once()

    @patch('core_analysis.celltypist.annotate')
    def test_annotate_cells(self, mock_annotate):
        """Test cell annotation."""
        mock_predictions = Mock()
        mock_predictions.cell_count = 100
        mock_annotate.return_value = mock_predictions

        result = annotate_cells(
            self.adata,
            model='Immune_All_Low.pkl',
            majority_voting=False
        )

        self.assertIsNotNone(result)
        mock_annotate.assert_called_once()

    def test_add_predictions_to_adata(self):
        """Test adding predictions to AnnData."""
        mock_predictions = Mock()
        mock_adata = self.adata.copy()
        # Simulate what to_adata() would add
        mock_adata.obs['celltypist_predicted_labels'] = ['TypeA'] * 100
        mock_adata.obs['celltypist_conf_score'] = np.random.uniform(0, 1, 100)

        mock_predictions.to_adata.return_value = mock_adata

        result = add_predictions_to_adata(mock_predictions)
        self.assertIsInstance(result, sc.AnnData)
        self.assertIn('celltypist_label', result.obs.columns)

    def test_add_predictions_majority_voting(self):
        """Test adding predictions with majority voting column."""
        mock_predictions = Mock()
        mock_adata = self.adata.copy()
        mock_adata.obs['celltypist_predicted_labels'] = ['TypeA'] * 100
        mock_adata.obs['celltypist_majority_voting'] = ['TypeB'] * 100
        mock_adata.obs['celltypist_conf_score'] = np.random.uniform(0, 1, 100)

        mock_predictions.to_adata.return_value = mock_adata

        result = add_predictions_to_adata(mock_predictions)
        # celltypist_label should prefer majority_voting
        self.assertTrue((result.obs['celltypist_label'] == 'TypeB').all())

    def test_filter_by_confidence(self):
        """Test confidence filtering."""
        adata = self.adata.copy()
        adata.obs['conf_score'] = np.random.uniform(0, 1, adata.n_obs)
        adata.obs['celltypist_label'] = ['Type1'] * 50 + ['Type2'] * 50

        result = filter_by_confidence(adata, threshold=0.5)

        self.assertIn('celltypist_label_filtered', result.obs.columns)

    def test_filter_by_confidence_missing_col(self):
        """Test confidence filtering with missing columns."""
        adata = self.adata.copy()
        with self.assertRaises(ValueError):
            filter_by_confidence(adata)

    @patch('core_analysis.celltypist.models.Model.load')
    def test_get_model_info(self, mock_load):
        """Test getting model info."""
        mock_model = Mock()
        mock_model.cell_types = ['A', 'B']
        mock_model.features = ['gene1', 'gene2']
        mock_model.description = 'Test model'
        mock_load.return_value = mock_model

        info = get_model_info('Immune_All_Low.pkl')
        self.assertEqual(info['n_cell_types'], 2)

    @patch('core_analysis.celltypist.train')
    def test_train_celltypist_model(self, mock_train):
        """Test training custom model."""
        mock_model = Mock()
        mock_model.write = Mock()
        mock_train.return_value = mock_model

        result = train_celltypist_model(
            self.adata,
            labels='cell_type',
            model_file='test_model.pkl'
        )

        self.assertIsNotNone(result)
        mock_model.write.assert_called_once_with('test_model.pkl')

    @patch('core_analysis.annotate_cells')
    def test_compare_models(self, mock_annotate):
        """Test comparing multiple models."""
        mock_predictions = Mock()
        mock_freq = pd.Series({'A': 50, 'B': 50})
        mock_predictions.summary_frequency.return_value = mock_freq
        mock_annotate.return_value = mock_predictions

        result = compare_models(self.adata, ['Model1', 'Model2'])
        self.assertEqual(len(result), 2)
        self.assertIn('top_cell_type', result.columns)


class TestUtils(unittest.TestCase):
    """Test utility functions."""

    def setUp(self):
        """Create test data."""
        np.random.seed(42)
        self.adata = sc.AnnData(
            X=np.random.lognormal(3, 1, (100, 500)),
            obs=pd.DataFrame(index=[f"cell_{i}" for i in range(100)]),
            var=pd.DataFrame(index=[f"GENE_{i}" for i in range(500)])
        )

    def test_create_test_data(self):
        """Test test data creation."""
        adata = create_test_data(n_cells=50, n_genes=100, n_cell_types=3)

        self.assertEqual(adata.n_obs, 50)
        self.assertEqual(adata.n_vars, 100)
        self.assertIn('true_cell_type', adata.obs.columns)

    def test_prepare_data(self):
        """Test data preparation."""
        # Use high lambda to ensure max > 50 so heuristic detects raw counts
        raw_adata = sc.AnnData(
            X=np.random.poisson(100, (50, 100)).astype(float)
        )

        result = prepare_data_for_celltypist(
            raw_adata,
            normalize=True,
            log_transform=True
        )

        # Check that data is log-normalized
        self.assertFalse(float(result.X.max()).is_integer())

    def test_prepare_data_already_normalized(self):
        """Test data preparation skips already-normalized data."""
        norm_adata = sc.AnnData(
            X=np.random.lognormal(0, 1, (50, 100))
        )
        result = prepare_data_for_celltypist(norm_adata)
        # Should skip normalization for log-normalized data
        self.assertFalse(float(result.X.max()).is_integer())

    def test_get_model_catalog(self):
        """Test model catalog."""
        catalog = get_model_catalog()

        self.assertIn('human', catalog)
        self.assertIn('mouse', catalog)
        self.assertIn('Immune_All_Low.pkl', catalog['human'])

    def test_recommend_model(self):
        """Test model recommendation."""
        model = recommend_model(tissue='immune', species='human', resolution='low')
        self.assertEqual(model, 'Immune_All_Low.pkl')

        model = recommend_model(tissue='intestine', species='human', resolution='high')
        self.assertEqual(model, 'Cells_Intestinal_Training.pkl')

    def test_summarize_annotations(self):
        """Test annotation summary."""
        adata = self.adata.copy()
        adata.obs['celltypist_label'] = ['Type1'] * 30 + ['Type2'] * 70
        adata.obs['celltypist_conf_score'] = np.random.uniform(0.5, 1.0, 100)

        summary = summarize_annotations(adata)

        self.assertIsInstance(summary, pd.DataFrame)
        self.assertEqual(len(summary), 2)
        self.assertIn('mean_confidence', summary.columns)

    def test_summarize_annotations_fallback(self):
        """Test summary with fallback column names."""
        adata = self.adata.copy()
        adata.obs['predicted_labels'] = ['Type1'] * 50 + ['Type2'] * 50
        # No conf_score column

        summary = summarize_annotations(adata, label_col='predicted_labels')
        self.assertEqual(len(summary), 2)
        # Should not have confidence columns
        self.assertNotIn('mean_confidence', summary.columns)

    def test_export_annotations(self):
        """Test exporting annotations."""
        adata = self.adata.copy()
        adata.obs['celltypist_label'] = ['Type1'] * 50 + ['Type2'] * 50
        adata.obs['celltypist_conf_score'] = np.random.uniform(0, 1, 100)

        export_annotations(adata, 'test_export.csv')
        self.assertTrue(os.path.exists('test_export.csv'))

        # Check content
        df = pd.read_csv('test_export.csv')
        self.assertIn('cell_barcode', df.columns)
        self.assertIn('celltypist_label', df.columns)
        os.remove('test_export.csv')

    def test_create_annotation_report(self):
        """Test creating annotation report."""
        adata = self.adata.copy()
        adata.obs['celltypist_label'] = ['Type1'] * 50 + ['Type2'] * 50
        adata.obs['celltypist_conf_score'] = np.random.uniform(0, 1, 100)

        report = create_annotation_report(adata, model_name='TestModel')
        self.assertIn('CellTypist Annotation Report', report)
        self.assertIn('TestModel', report)

    @patch('utils.celltypist.models.Model.load')
    def test_check_gene_overlap(self, mock_load):
        """Test gene overlap check."""
        mock_model = Mock()
        mock_model.features = ['GENE_0', 'GENE_1', 'GENE_2', 'MISSING']
        mock_load.return_value = mock_model

        result = check_gene_overlap(self.adata, 'Immune_All_Low.pkl')
        self.assertIn('overlap_fraction', result)
        self.assertGreater(result['n_overlap'], 0)


class TestVisualization(unittest.TestCase):
    """Test visualization functions."""

    def setUp(self):
        """Create test data with CellTypist predictions."""
        np.random.seed(42)
        self.adata = sc.AnnData(
            X=np.random.lognormal(3, 1, (100, 500)),
            obs=pd.DataFrame({
                'celltypist_label': ['T cell'] * 50 + ['B cell'] * 50,
                'celltypist_conf_score': np.random.uniform(0.3, 1.0, 100),
                'leiden': ['0'] * 30 + ['1'] * 30 + ['2'] * 40,
            }, index=[f"cell_{i}" for i in range(100)]),
            var=pd.DataFrame(index=[f"GENE_{i}" for i in range(500)])
        )
        self.adata.obsm['X_umap'] = np.random.randn(100, 2)

    @patch('visualization.plt.show')
    @patch('visualization.plt.savefig')
    def test_plot_confidence_distribution(self, mock_savefig, mock_show):
        """Test confidence distribution plot."""
        from visualization import plot_confidence_distribution
        plot_confidence_distribution(self.adata)
        mock_show.assert_called_once()

    @patch('visualization.plt.show')
    @patch('visualization.plt.savefig')
    def test_plot_confidence_distribution_save(self, mock_savefig, mock_show):
        """Test confidence distribution plot with save."""
        from visualization import plot_confidence_distribution
        plot_confidence_distribution(self.adata, save='test_conf.png')
        mock_savefig.assert_called_once()

    @patch('visualization.plt.show')
    @patch('visualization.plt.savefig')
    def test_plot_celltype_proportions(self, mock_savefig, mock_show):
        """Test cell type proportions plot."""
        from visualization import plot_celltype_proportions
        plot_celltype_proportions(self.adata)
        mock_show.assert_called_once()

    @patch('visualization.plt.show')
    @patch('visualization.plt.savefig')
    def test_plot_celltype_proportions_groupby(self, mock_savefig, mock_show):
        """Test grouped proportions plot."""
        from visualization import plot_celltype_proportions
        self.adata.obs['sample'] = ['A'] * 50 + ['B'] * 50
        plot_celltype_proportions(self.adata, groupby='sample')
        mock_show.assert_called_once()

    @patch('visualization.plt.show')
    @patch('visualization.plt.savefig')
    def test_plot_prediction_heatmap(self, mock_savefig, mock_show):
        """Test prediction heatmap."""
        from visualization import plot_prediction_heatmap
        plot_prediction_heatmap(self.adata, cluster_col='leiden')
        mock_show.assert_called_once()

    @patch('visualization.plt.show')
    @patch('visualization.plt.savefig')
    def test_plot_prediction_heatmap_missing_cluster(self, mock_savefig, mock_show):
        """Test heatmap with missing cluster column raises error."""
        from visualization import plot_prediction_heatmap
        with self.assertRaises(ValueError):
            plot_prediction_heatmap(self.adata, cluster_col='nonexistent')

    @patch('visualization.plt.show')
    @patch('visualization.plt.savefig')
    def test_plot_annotation_summary(self, mock_savefig, mock_show):
        """Test comprehensive annotation summary plot."""
        from visualization import plot_annotation_summary
        plot_annotation_summary(self.adata, output_dir='./test_plots')
        mock_savefig.assert_called_once()

    @patch('visualization.plt.show')
    @patch('visualization.plt.savefig')
    def test_plot_umap_with_predictions(self, mock_savefig, mock_show):
        """Test UMAP plot with predictions."""
        from visualization import plot_umap_with_predictions
        plot_umap_with_predictions(self.adata)
        mock_show.assert_called_once()

    @patch('visualization.plt.show')
    @patch('visualization.plt.savefig')
    def test_plot_umap_auto_compute(self, mock_savefig, mock_show):
        """Test UMAP plot auto-computes UMAP when missing."""
        from visualization import plot_umap_with_predictions
        # Use smaller values to avoid overflow in HVG computation
        adata_no_umap = sc.AnnData(
            X=np.random.lognormal(0, 0.5, (50, 200)),
            obs=pd.DataFrame({
                'celltypist_label': ['T cell'] * 25 + ['B cell'] * 25,
                'celltypist_conf_score': np.random.uniform(0.3, 1.0, 50),
            }, index=[f"cell_{i}" for i in range(50)]),
            var=pd.DataFrame(index=[f"GENE_{i}" for i in range(200)])
        )
        # Should not raise - auto-computes UMAP
        plot_umap_with_predictions(adata_no_umap)
        mock_show.assert_called_once()

    def test_plot_celltypist_dotplot_no_adata(self):
        """Test dotplot error when predictions lack adata."""
        from visualization import plot_celltypist_dotplot
        mock_predictions = Mock()
        del mock_predictions.adata  # Ensure no adata attribute
        with patch('builtins.print') as mock_print:
            plot_celltypist_dotplot(mock_predictions)
            # Should print an error about incorrect input
            printed = ' '.join([str(c) for c in mock_print.call_args_list])
            self.assertIn('error', printed.lower())


class TestIntegration(unittest.TestCase):
    """Integration tests."""

    def setUp(self):
        """Create test data."""
        np.random.seed(42)
        self.adata = sc.AnnData(
            X=np.random.lognormal(3, 1, (200, 500)),
            obs=pd.DataFrame({
                'sample': ['A'] * 100 + ['B'] * 100
            }, index=[f"cell_{i}" for i in range(200)]),
            var=pd.DataFrame(index=[f"GENE_{i}" for i in range(500)])
        )

    @patch('core_analysis.celltypist.annotate')
    def test_full_pipeline(self, mock_annotate):
        """Test complete annotation pipeline."""
        mock_predictions = Mock()
        mock_adata = self.adata.copy()
        # Simulate to_adata output
        mock_adata.obs['celltypist_predicted_labels'] = ['TypeA'] * 200
        mock_adata.obs['celltypist_conf_score'] = np.random.uniform(0, 1, 200)
        mock_predictions.to_adata.return_value = mock_adata
        mock_annotate.return_value = mock_predictions

        result = run_celltypist_annotation(
            self.adata.copy(),
            model='Immune_All_Low.pkl',
            majority_voting=True
        )

        self.assertIsInstance(result, sc.AnnData)
        self.assertIn('celltypist_label', result.obs.columns)


if __name__ == '__main__':
    unittest.main()
