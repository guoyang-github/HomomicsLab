"""
Unit Tests for scGen Perturbation Analysis Skill
================================================

Comprehensive test suite for the scGen wrapper functions.
"""

import unittest
import numpy as np
import pandas as pd
import scanpy as sc
import sys
import os
from unittest.mock import Mock, patch, MagicMock

# Add scripts to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts', 'python'))

from core_analysis import (
    check_scgen_dependencies,
    validate_perturbation_data,
    preprocess_for_scgen,
    setup_scgen_anndata,
    train_scgen_model,
    predict_perturbation,
    batch_correction,
    get_latent_representation,
    extract_perturbation_vector,
    run_complete_scgen_pipeline,
    decode_latent
)
from visualization import (
    plot_regression_mean,
    plot_regression_variance,
    plot_binary_classifier,
    plot_latent_space,
    plot_perturbation_vector,
    binary_classifier_scores
)
from utils import (
    balancer,
    extractor,
    get_condition_statistics,
    evaluate_prediction_accuracy,
    compare_perturbation_vectors,
    create_prediction_report,
    merge_predictions,
    check_gpu_availability,
    get_recommended_hvg_number,
    subsample_data
)


class TestCoreAnalysis(unittest.TestCase):
    """Test core analysis functions."""

    def setUp(self):
        """Create test data."""
        np.random.seed(42)
        n_cells = 200
        n_genes = 500

        self.adata = sc.AnnData(
            X=np.random.lognormal(3, 1, (n_cells, n_genes)),
            obs=pd.DataFrame({
                'condition': ['control'] * 100 + ['stimulated'] * 100,
                'cell_type': np.random.choice(['CD4T', 'CD8T', 'B', 'NK'], n_cells)
            }, index=[f"cell_{i}" for i in range(n_cells)]),
            var=pd.DataFrame(index=[f"GENE_{i}" for i in range(n_genes)])
        )

    @patch('core_analysis.scgen')
    @patch('core_analysis.torch')
    def test_check_scgen_dependencies(self, mock_torch, mock_scgen):
        """Test dependency checking."""
        result = check_scgen_dependencies()
        self.assertTrue(result)

    def test_validate_perturbation_data_valid(self):
        """Test data validation with valid data."""
        result = validate_perturbation_data(
            self.adata,
            condition_key='condition',
            cell_type_key='cell_type'
        )
        self.assertIn('n_cells', result)
        self.assertEqual(result['n_cells'], 200)
        self.assertEqual(result['n_conditions'], 2)

    def test_validate_perturbation_data_missing_key(self):
        """Test validation with missing key."""
        with self.assertRaises(ValueError) as context:
            validate_perturbation_data(
                self.adata,
                condition_key='nonexistent'
            )
        self.assertIn("not found", str(context.exception))

    def test_validate_perturbation_data_single_condition(self):
        """Test validation with single condition."""
        adata_single = self.adata.copy()
        adata_single.obs['condition'] = 'control'
        with self.assertRaises(ValueError) as context:
            validate_perturbation_data(adata_single, condition_key='condition')
        self.assertIn("at least 2 conditions", str(context.exception))

    def test_preprocess_for_scgen(self):
        """Test preprocessing."""
        adata_copy = self.adata.copy()
        result = preprocess_for_scgen(
            adata_copy,
            n_top_genes=100,
            flavor='seurat'
        )
        self.assertIn('highly_variable', result.var.columns)

    @patch('core_analysis.scgen')
    def test_setup_scgen_anndata(self, mock_scgen):
        """Test AnnData setup."""
        mock_scgen.SCGEN.setup_anndata = Mock()

        adata_copy = self.adata.copy()
        result = setup_scgen_anndata(
            adata_copy,
            batch_key='condition',
            labels_key='cell_type'
        )
        mock_scgen.SCGEN.setup_anndata.assert_called_once()

    @patch('core_analysis.scgen')
    @patch('core_analysis.torch')
    def test_train_scgen_model(self, mock_torch, mock_scgen):
        """Test model training."""
        mock_model = Mock()
        mock_scgen.SCGEN.return_value = mock_model

        model = train_scgen_model(
            self.adata,
            max_epochs=10,
            batch_size=32
        )

        mock_scgen.SCGEN.assert_called_once()
        mock_model.train.assert_called_once()

    @patch('core_analysis.scgen')
    def test_predict_perturbation(self, mock_scgen):
        """Test perturbation prediction."""
        mock_model = Mock()
        mock_predicted = Mock()
        mock_predicted.n_obs = 50
        mock_model.predict.return_value = (mock_predicted, np.random.randn(100))

        result, delta = predict_perturbation(
            mock_model,
            ctrl_key='control',
            stim_key='stimulated'
        )

        mock_model.predict.assert_called_once()
        self.assertEqual(result.n_obs, 50)

    def test_predict_perturbation_exclusive_args(self):
        """Test prediction with both args provided."""
        mock_model = Mock()
        with self.assertRaises(ValueError) as context:
            predict_perturbation(
                mock_model,
                ctrl_key='control',
                stim_key='stim',
                adata_to_predict=self.adata,
                celltype_to_predict='CD4T'
            )
        self.assertIn("not both", str(context.exception))

    @patch('core_analysis.scgen')
    def test_batch_correction(self, mock_scgen):
        """Test batch correction."""
        mock_model = Mock()
        mock_corrected = Mock()
        mock_corrected.n_obs = 200
        mock_corrected.n_vars = 500
        mock_model.batch_removal.return_value = mock_corrected

        result = batch_correction(mock_model)

        mock_model.batch_removal.assert_called_once()
        self.assertEqual(result.n_obs, 200)

    def test_get_latent_representation(self):
        """Test latent representation extraction."""
        mock_model = Mock()
        mock_latent = np.random.randn(200, 100)
        mock_model.get_latent_representation.return_value = mock_latent

        result = get_latent_representation(mock_model)

        self.assertEqual(result.shape, (200, 100))

    @patch('core_analysis.torch')
    def test_decode_latent(self, mock_torch):
        """Test latent decoding."""
        mock_model = Mock()
        mock_torch.Tensor.return_value = Mock()
        mock_model.module.generative.return_value = {"px": Mock()}

        latent = np.random.randn(50, 100)
        result = decode_latent(mock_model, latent)

        mock_model.module.generative.assert_called_once()

    @patch('core_analysis.train_scgen_model')
    @patch('core_analysis.setup_scgen_anndata')
    @patch('core_analysis.preprocess_for_scgen')
    @patch('core_analysis.validate_perturbation_data')
    def test_run_complete_pipeline(self, mock_validate, mock_preprocess, mock_setup, mock_train):
        """Test complete pipeline."""
        mock_model = Mock()
        mock_model.batch_removal.return_value = Mock()
        mock_model.predict.return_value = (Mock(), np.random.randn(100))
        mock_train.return_value = mock_model

        results = run_complete_scgen_pipeline(
            self.adata,
            condition_key='condition',
            ctrl_key='control',
            stim_key='stimulated'
        )

        self.assertIn('model', results)
        self.assertIn('predicted', results)
        self.assertIn('delta', results)


class TestUtils(unittest.TestCase):
    """Test utility functions."""

    def setUp(self):
        """Create test data."""
        np.random.seed(42)
        n_cells = 100
        n_genes = 200

        self.adata = sc.AnnData(
            X=np.random.lognormal(3, 1, (n_cells, n_genes)),
            obs=pd.DataFrame({
                'condition': ['control'] * 50 + ['stimulated'] * 50,
                'cell_type': np.random.choice(['CD4T', 'CD8T'], n_cells)
            }, index=[f"cell_{i}" for i in range(n_cells)]),
            var=pd.DataFrame(index=[f"GENE_{i}" for i in range(n_genes)])
        )

    def test_balancer(self):
        """Test cell type balancing."""
        balanced = balancer(self.adata, cell_type_key='cell_type')

        # Check that cell types are balanced
        counts = balanced.obs['cell_type'].value_counts()
        self.assertEqual(counts.iloc[0], counts.iloc[1])

    def test_extractor(self):
        """Test data extraction."""
        result = extractor(
            self.adata,
            cell_type='CD4T',
            condition_key='condition',
            cell_type_key='cell_type',
            ctrl_key='control',
            stim_key='stimulated'
        )

        self.assertEqual(len(result), 4)
        self.assertIsInstance(result[0], sc.AnnData)

    def test_get_condition_statistics(self):
        """Test condition statistics."""
        stats = get_condition_statistics(
            self.adata,
            condition_key='condition',
            cell_type_key='cell_type'
        )

        self.assertIsInstance(stats, pd.DataFrame)
        self.assertIn('n_cells', stats.columns)

    def test_get_condition_statistics_no_celltype(self):
        """Test condition statistics without cell type."""
        stats = get_condition_statistics(
            self.adata,
            condition_key='condition'
        )

        self.assertIsInstance(stats, pd.DataFrame)
        self.assertEqual(len(stats), 2)  # 2 conditions

    def test_evaluate_prediction_accuracy(self):
        """Test prediction accuracy evaluation."""
        adata_pred = self.adata[:50].copy()
        adata_real = self.adata[50:].copy()

        metrics = evaluate_prediction_accuracy(
            adata_pred,
            adata_real,
            condition_key='condition'
        )

        self.assertIn('pearson_all', metrics)
        self.assertIn('r2_all', metrics)

    def test_compare_perturbation_vectors(self):
        """Test vector comparison."""
        delta1 = np.random.randn(100)
        delta2 = np.random.randn(100)

        comparison = compare_perturbation_vectors(delta1, delta2)

        self.assertIn('cosine_similarity', comparison)
        self.assertIn('pearson_r', comparison)

    def test_create_prediction_report(self):
        """Test report creation."""
        mock_model = Mock()
        mock_model.module.n_hidden = 800
        mock_model.module.n_latent = 100
        mock_model.module.n_layers = 2

        predicted = self.adata[:50].copy()
        delta = np.random.randn(100)

        report = create_prediction_report(
            mock_model,
            self.adata,
            predicted,
            delta,
            ctrl_key='control',
            stim_key='stimulated'
        )

        self.assertIn("scGen Prediction Report", report)
        self.assertIn("800", report)

    def test_merge_predictions(self):
        """Test merging predictions."""
        ctrl = self.adata[:30].copy()
        real = self.adata[30:60].copy()
        pred = self.adata[60:].copy()

        merged = merge_predictions(ctrl, real, pred)

        self.assertEqual(merged.n_obs, 90)
        self.assertIn('condition', merged.obs.columns)

    def test_check_gpu_availability(self):
        """Test GPU check."""
        result = check_gpu_availability()
        self.assertIsInstance(result, bool)

    def test_get_recommended_hvg_number(self):
        """Test HVG recommendation."""
        n_hvg = get_recommended_hvg_number(n_cells=5000, n_genes=20000)
        self.assertEqual(n_hvg, 5000)

        n_hvg = get_recommended_hvg_number(n_cells=500, n_genes=5000)
        self.assertEqual(n_hvg, 2000)

    def test_subsample_data(self):
        """Test data subsampling."""
        subsampled = subsample_data(self.adata, target_cells=50)
        self.assertEqual(subsampled.n_obs, 50)

    def test_subsample_data_stratified(self):
        """Test stratified subsampling."""
        subsampled = subsample_data(
            self.adata,
            target_cells=50,
            condition_key='condition'
        )
        self.assertEqual(subsampled.n_obs, 50)
        # Check stratification
        counts = subsampled.obs['condition'].value_counts()
        self.assertEqual(counts['control'], 25)
        self.assertEqual(counts['stimulated'], 25)


class TestVisualization(unittest.TestCase):
    """Test visualization functions."""

    def setUp(self):
        """Create test data."""
        np.random.seed(42)
        n_cells = 100
        n_genes = 200

        self.adata = sc.AnnData(
            X=np.random.lognormal(3, 1, (n_cells, n_genes)),
            obs=pd.DataFrame({
                'condition': ['control'] * 50 + ['stimulated'] * 50,
                'cell_type': np.random.choice(['CD4T', 'CD8T'], n_cells)
            }, index=[f"cell_{i}" for i in range(n_cells)]),
            var=pd.DataFrame(index=[f"GENE_{i}" for i in range(n_genes)])
        )

        self.delta = np.random.randn(100)

    @patch('visualization.sns.regplot')
    @patch('visualization.plt.subplots')
    def test_plot_regression_mean(self, mock_subplots, mock_regplot):
        """Test regression mean plot."""
        mock_fig = Mock()
        mock_ax = Mock()
        mock_subplots.return_value = (mock_fig, mock_ax)

        mock_model = Mock()
        mock_model.adata_manager.get_state_registry.return_value.original_key = 'condition'

        result = plot_regression_mean(
            mock_model,
            self.adata,
            axis_keys={'x': 'control', 'y': 'stimulated'},
            labels={'x': 'Control', 'y': 'Stimulated'},
            save=False,
            show=False
        )

        mock_subplots.assert_called_once()

    @patch('visualization.sns.regplot')
    @patch('visualization.plt.subplots')
    def test_plot_regression_variance(self, mock_subplots, mock_regplot):
        """Test regression variance plot."""
        mock_fig = Mock()
        mock_ax = Mock()
        mock_subplots.return_value = (mock_fig, mock_ax)

        mock_model = Mock()
        mock_model.adata_manager.get_state_registry.return_value.original_key = 'condition'

        result = plot_regression_variance(
            mock_model,
            self.adata,
            axis_keys={'x': 'control', 'y': 'stimulated'},
            labels={'x': 'Control', 'y': 'Stimulated'},
            save=False,
            show=False
        )

        mock_subplots.assert_called_once()

    @patch('visualization.plt.subplots')
    def test_plot_binary_classifier(self, mock_subplots):
        """Test binary classifier plot."""
        mock_fig = Mock()
        mock_ax = Mock()
        mock_subplots.return_value = (mock_fig, mock_ax)

        mock_model = Mock()
        mock_model.adata_manager.get_state_registry.return_value.original_key = 'condition'
        mock_model.get_latent_representation.return_value = np.random.randn(50, 100)

        plot_binary_classifier(
            mock_model,
            self.adata,
            self.delta,
            ctrl_key='control',
            stim_key='stimulated',
            save=False,
            show=False
        )

        mock_subplots.assert_called_once()

    def test_binary_classifier_scores(self):
        """Test binary classifier scores."""
        mock_model = Mock()
        mock_model.adata_manager.get_state_registry.return_value.original_key = 'condition'
        mock_model.get_latent_representation.return_value = np.random.randn(50, 100)

        dot_cd, dot_stim = binary_classifier_scores(
            mock_model,
            self.adata,
            self.delta,
            ctrl_key='control',
            stim_key='stimulated'
        )

        self.assertEqual(len(dot_cd), 50)
        self.assertEqual(len(dot_stim), 50)

    @patch('visualization.sc.pl.umap')
    @patch('visualization.sc.tl.umap')
    @patch('visualization.sc.pp.neighbors')
    @patch('visualization.plt.subplots')
    def test_plot_latent_space(self, mock_subplots, mock_neighbors, mock_umap, mock_pl_umap):
        """Test latent space plot."""
        mock_fig = Mock()
        mock_ax = Mock()
        mock_subplots.return_value = (mock_fig, mock_ax)

        mock_model = Mock()
        mock_model.get_latent_representation.return_value = np.random.randn(100, 50)

        plot_latent_space(
            mock_model,
            self.adata,
            color_by='condition',
            save=False,
            show=False
        )

        mock_model.get_latent_representation.assert_called_once()

    @patch('visualization.plt.subplots')
    def test_plot_perturbation_vector(self, mock_subplots):
        """Test perturbation vector plot."""
        mock_fig = Mock()
        mock_ax = Mock()
        mock_subplots.return_value = (mock_fig, mock_ax)

        plot_perturbation_vector(
            self.delta,
            top_n=20,
            save=False,
            show=False
        )

        mock_subplots.assert_called_once()


class TestIntegration(unittest.TestCase):
    """Integration tests."""

    def setUp(self):
        """Create test data."""
        np.random.seed(42)
        n_cells = 100
        n_genes = 200

        self.adata = sc.AnnData(
            X=np.random.lognormal(3, 1, (n_cells, n_genes)),
            obs=pd.DataFrame({
                'condition': ['control'] * 50 + ['stimulated'] * 50,
                'cell_type': np.random.choice(['CD4T', 'CD8T'], n_cells)
            }, index=[f"cell_{i}" for i in range(n_cells)]),
            var=pd.DataFrame(index=[f"GENE_{i}" for i in range(n_genes)])
        )

    @patch('core_analysis.predict_perturbation')
    @patch('core_analysis.batch_correction')
    @patch('core_analysis.train_scgen_model')
    @patch('core_analysis.setup_scgen_anndata')
    @patch('core_analysis.preprocess_for_scgen')
    @patch('core_analysis.validate_perturbation_data')
    def test_end_to_end_workflow(self, mock_validate, mock_preprocess, mock_setup, mock_train, mock_correct, mock_predict):
        """Test end-to-end workflow."""
        # Setup mocks
        mock_model = Mock()
        mock_corrected = Mock()
        mock_predicted = Mock()
        mock_delta = np.random.randn(100)

        mock_train.return_value = mock_model
        mock_correct.return_value = mock_corrected
        mock_predict.return_value = (mock_predicted, mock_delta)

        # Run pipeline
        results = run_complete_scgen_pipeline(
            self.adata,
            condition_key='condition',
            ctrl_key='control',
            stim_key='stimulated',
            run_batch_correction=True
        )

        # Verify results
        self.assertIn('model', results)
        self.assertIn('corrected', results)
        self.assertIn('predicted', results)
        self.assertIn('delta', results)

        # Verify all steps were called
        mock_validate.assert_called_once()
        mock_preprocess.assert_called_once()
        mock_setup.assert_called_once()
        mock_train.assert_called_once()
        mock_correct.assert_called_once()
        mock_predict.assert_called_once()


if __name__ == '__main__':
    unittest.main()
