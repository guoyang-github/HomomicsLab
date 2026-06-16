"""
Unit Tests for pertpy Perturbation Analysis Skill
=================================================

Comprehensive test suite for the pertpy wrapper functions.
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
    check_perturbation_data,
    compute_pseudobulk_space,
    compute_centroid_space,
    run_augur_classification,
    calculate_perturbation_distances,
    compute_perturbation_signature,
    run_mixscape_classification,
    assign_guide_rna,
    compare_perturbations,
    run_complete_perturbation_analysis
)
from visualization import (
    plot_augur_results,
    plot_perturbation_distance_heatmap,
    plot_mixscape_results,
    plot_de_volcano,
    plot_distance_dendrogram,
    plot_perturbation_summary
)
from utils import (
    get_perturbation_summary,
    find_high_confidence_perturbations,
    export_de_results,
    get_top_de_genes,
    validate_de_results,
    create_perturbation_report,
    check_dependencies
)


class TestCoreAnalysis(unittest.TestCase):
    """Test core analysis functions."""

    def setUp(self):
        """Create test data."""
        np.random.seed(42)
        n_cells = 100
        n_genes = 200

        self.adata = sc.AnnData(
            X=np.random.lognormal(3, 1, (n_cells, n_genes)),
            obs=pd.DataFrame({
                'perturbation': np.random.choice(['control', 'KO_gene_A', 'KO_gene_B'], n_cells),
                'replicate': np.random.choice(['rep1', 'rep2'], n_cells),
                'cell_type': np.random.choice(['Type1', 'Type2'], n_cells),
                'guide_identity': np.random.choice(['NT', 'gRNA_A', 'gRNA_B'], n_cells)
            }, index=[f"cell_{i}" for i in range(n_cells)]),
            var=pd.DataFrame(index=[f"GENE_{i}" for i in range(n_genes)])
        )

        # Add UMAP embedding
        sc.pp.normalize_total(self.adata)
        sc.pp.log1p(self.adata)
        sc.pp.highly_variable_genes(self.adata, n_top_genes=50, flavor='cell_ranger')
        sc.pp.scale(self.adata)
        sc.tl.pca(self.adata, n_comps=10)
        sc.pp.neighbors(self.adata, n_neighbors=10, n_pcs=10)
        sc.tl.umap(self.adata)

    def test_check_perturbation_data_valid(self):
        """Test data validation with valid data."""
        result = check_perturbation_data(self.adata, perturbation_col='perturbation')
        self.assertTrue(result)

    def test_check_perturbation_data_missing_column(self):
        """Test data validation with missing perturbation column."""
        with self.assertRaises(ValueError) as context:
            check_perturbation_data(self.adata, perturbation_col='nonexistent')
        self.assertIn("not found", str(context.exception))

    def test_check_perturbation_data_single_perturbation(self):
        """Test data validation with single perturbation."""
        adata_single = self.adata.copy()
        adata_single.obs['perturbation'] = 'control'
        with self.assertRaises(ValueError) as context:
            check_perturbation_data(adata_single, perturbation_col='perturbation')
        self.assertIn("at least 2 perturbations", str(context.exception))

    def test_check_perturbation_data_with_control(self):
        """Test data validation with control specified."""
        result = check_perturbation_data(
            self.adata,
            perturbation_col='perturbation',
            control='control'
        )
        self.assertTrue(result)

    def test_check_perturbation_data_invalid_control(self):
        """Test data validation with invalid control."""
        with self.assertRaises(ValueError) as context:
            check_perturbation_data(
                self.adata,
                perturbation_col='perturbation',
                control='nonexistent'
            )
        self.assertIn("not found", str(context.exception))

    @patch('core_analysis.pt.tl.PseudobulkSpace')
    def test_compute_pseudobulk_space(self, mock_ps_class):
        """Test pseudobulk space computation."""
        mock_ps = Mock()
        mock_ps_class.return_value = mock_ps

        # Create mock pseudobulk result
        mock_result = sc.AnnData(
            X=np.random.lognormal(3, 1, (3, 200)),
            obs=pd.DataFrame({
                'perturbation': ['control', 'KO_gene_A', 'KO_gene_B']
            }, index=['ctrl_pb', 'A_pb', 'B_pb']),
            var=pd.DataFrame(index=[f"GENE_{i}" for i in range(200)])
        )
        mock_ps.compute.return_value = mock_result

        result = compute_pseudobulk_space(
            self.adata,
            perturbation_col='perturbation',
            replicate_col='replicate'
        )

        mock_ps.compute.assert_called_once()
        self.assertEqual(result.n_obs, 3)

    @patch('core_analysis.pt.tl.CentroidSpace')
    def test_compute_centroid_space(self, mock_cs_class):
        """Test centroid space computation."""
        mock_cs = Mock()
        mock_cs_class.return_value = mock_cs

        mock_result = sc.AnnData(
            X=np.random.randn(3, 2),
            obs=pd.DataFrame({
                'perturbation': ['control', 'KO_gene_A', 'KO_gene_B']
            }),
        )
        mock_cs.compute.return_value = mock_result

        result = compute_centroid_space(
            self.adata,
            perturbation_col='perturbation',
            embedding_key='X_umap'
        )

        mock_cs.compute.assert_called_once()
        self.assertEqual(result.n_obs, 3)

    def test_compute_centroid_space_missing_embedding(self):
        """Test centroid space with missing embedding."""
        adata_no_embed = self.adata.copy()
        del adata_no_embed.obsm['X_umap']

        with self.assertRaises(ValueError) as context:
            compute_centroid_space(
                adata_no_embed,
                perturbation_col='perturbation',
                embedding_key='X_umap'
            )
        self.assertIn("not found", str(context.exception))

    @patch('core_analysis.pt.tl.Augur')
    def test_run_augur_classification(self, mock_augur_class):
        """Test Augur classification."""
        mock_augur = Mock()
        mock_augur_class.return_value = mock_augur

        mock_augur.load.return_value = self.adata
        mock_augur.predict.return_value = self.adata

        result = run_augur_classification(
            self.adata,
            estimator="random_forest_classifier",
            labels_col="perturbation",
            n_estimators=50
        )

        mock_augur.load.assert_called_once()
        mock_augur.predict.assert_called_once()

    @patch('core_analysis.pt.tl.Distance')
    def test_calculate_perturbation_distances(self, mock_dist_class):
        """Test perturbation distance calculation."""
        mock_dist = Mock()
        mock_dist_class.return_value = mock_dist

        mock_distance_df = pd.DataFrame(
            np.random.rand(3, 3),
            index=['control', 'KO_gene_A', 'KO_gene_B'],
            columns=['control', 'KO_gene_A', 'KO_gene_B']
        )
        mock_dist.pairwise.return_value = mock_distance_df

        result = calculate_perturbation_distances(
            self.adata,
            perturbation_col='perturbation',
            metric='edistance'
        )

        mock_dist.pairwise.assert_called_once()
        self.assertIsInstance(result, pd.DataFrame)
        self.assertEqual(result.shape, (3, 3))

    @patch('core_analysis.pt.tl.Mixscape')
    def test_compute_perturbation_signature(self, mock_mixscape_class):
        """Test perturbation signature computation."""
        mock_ms = Mock()
        mock_mixscape_class.return_value = mock_ms

        adata_copy = self.adata.copy()
        result = compute_perturbation_signature(
            adata_copy,
            perturbation_col='perturbation',
            control='control',
            n_neighbors=10
        )

        mock_ms.perturbation_signature.assert_called_once()

    @patch('core_analysis.pt.tl.Mixscape')
    def test_run_mixscape_classification(self, mock_mixscape_class):
        """Test Mixscape classification."""
        mock_ms = Mock()
        mock_mixscape_class.return_value = mock_ms

        adata_copy = self.adata.copy()
        adata_copy.layers['X_pert'] = adata_copy.X.copy()

        result = run_mixscape_classification(
            adata_copy,
            perturbation_col='perturbation',
            control='control',
            new_class_name='mixscape_class'
        )

        mock_ms.mixscape.assert_called_once()

    def test_run_mixscape_missing_signature(self):
        """Test Mixscape without perturbation signature."""
        with self.assertRaises(ValueError) as context:
            run_mixscape_classification(
                self.adata,
                perturbation_col='perturbation',
                control='control'
            )
        self.assertIn("Perturbation signature not found", str(context.exception))

    @patch('core_analysis.pt.pp.assign_guides_by_threshold')
    def test_assign_guide_rna_threshold(self, mock_assign):
        """Test guide RNA assignment with threshold method."""
        mock_assign.return_value = self.adata

        result = assign_guide_rna(
            self.adata,
            guide_rna_column='guide_identity',
            assignment_method='threshold',
            threshold=5
        )

        mock_assign.assert_called_once()

    @patch('core_analysis.pt.pp.assign_guides_by_mixture')
    def test_assign_guide_rna_mixture(self, mock_assign):
        """Test guide RNA assignment with mixture method."""
        mock_assign.return_value = self.adata

        result = assign_guide_rna(
            self.adata,
            guide_rna_column='guide_identity',
            assignment_method='mixture'
        )

        mock_assign.assert_called_once()

    def test_assign_guide_rna_invalid_method(self):
        """Test guide RNA assignment with invalid method."""
        with self.assertRaises(ValueError) as context:
            assign_guide_rna(
                self.adata,
                guide_rna_column='guide_identity',
                assignment_method='invalid'
            )
        self.assertIn("Unknown assignment method", str(context.exception))


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
                'perturbation': ['control'] * 40 + ['KO_A'] * 35 + ['KO_B'] * 25,
                'replicate': np.random.choice(['rep1', 'rep2'], n_cells)
            }, index=[f"cell_{i}" for i in range(n_cells)]),
            var=pd.DataFrame(index=[f"GENE_{i}" for i in range(n_genes)])
        )

    def test_get_perturbation_summary(self):
        """Test perturbation summary function."""
        summary = get_perturbation_summary(self.adata, perturbation_col='perturbation')

        self.assertIsInstance(summary, pd.DataFrame)
        self.assertIn('cell_count', summary.columns)
        self.assertIn('proportion', summary.columns)
        self.assertEqual(len(summary), 3)

    def test_get_perturbation_summary_missing_column(self):
        """Test summary with missing column."""
        with self.assertRaises(ValueError) as context:
            get_perturbation_summary(self.adata, perturbation_col='nonexistent')
        self.assertIn("not found", str(context.exception))

    def test_find_high_confidence_perturbations(self):
        """Test finding high confidence perturbations."""
        distance_df = pd.DataFrame({
            'control': [0.0, 0.5, 1.5],
            'KO_A': [0.5, 0.0, 1.0],
            'KO_B': [1.5, 1.0, 0.0]
        }, index=['control', 'KO_A', 'KO_B'])

        result = find_high_confidence_perturbations(
            distance_df,
            control='control',
            threshold_percentile=50
        )

        self.assertIsInstance(result, list)
        self.assertIn('KO_B', result)

    def test_find_high_confidence_perturbations_invalid_control(self):
        """Test with invalid control."""
        distance_df = pd.DataFrame({'A': [0.0], 'B': [1.0]})

        with self.assertRaises(ValueError) as context:
            find_high_confidence_perturbations(distance_df, control='nonexistent')
        self.assertIn("not found", str(context.exception))

    def test_get_top_de_genes(self):
        """Test getting top DE genes."""
        de_results = pd.DataFrame({
            'gene': ['A', 'B', 'C', 'D'],
            'log2FoldChange': [2.0, 1.5, -1.0, 0.5],
            'padj': [0.001, 0.01, 0.05, 0.1]
        })

        top_genes = get_top_de_genes(de_results, n_genes=2, sort_by='log2FoldChange')

        self.assertEqual(len(top_genes), 2)
        self.assertEqual(top_genes.iloc[0]['gene'], 'A')

    def test_validate_de_results_valid(self):
        """Test DE results validation with valid data."""
        de_results = pd.DataFrame({
            'log2FoldChange': [1.0, -1.5, 2.0],
            'padj': [0.001, 0.01, 0.05]
        })

        result = validate_de_results(de_results)
        self.assertTrue(result)

    def test_validate_de_results_missing_columns(self):
        """Test DE results validation with missing columns."""
        de_results = pd.DataFrame({'gene': ['A', 'B']})

        with self.assertRaises(ValueError) as context:
            validate_de_results(de_results)
        self.assertIn("Missing columns", str(context.exception))

    def test_create_perturbation_report(self):
        """Test report creation."""
        report = create_perturbation_report(
            self.adata,
            perturbation_col='perturbation'
        )

        self.assertIsInstance(report, str)
        self.assertIn("Perturbation Analysis Report", report)
        self.assertIn("Total Cells", report)

    @patch('utils.warnings')
    def test_validate_de_results_with_nans(self, mock_warnings):
        """Test DE validation with NaN values."""
        de_results = pd.DataFrame({
            'log2FoldChange': [1.0, np.nan, 2.0],
            'padj': [0.001, 0.01, np.nan]
        })

        result = validate_de_results(de_results)
        self.assertTrue(result)

    def test_check_dependencies(self):
        """Test dependency checking."""
        result = check_dependencies()
        self.assertTrue(result)


class TestVisualization(unittest.TestCase):
    """Test visualization functions."""

    def setUp(self):
        """Create test data."""
        np.random.seed(42)
        n_cells = 50
        n_genes = 100

        self.adata = sc.AnnData(
            X=np.random.lognormal(3, 1, (n_cells, n_genes)),
            obs=pd.DataFrame({
                'perturbation': ['control'] * 20 + ['KO_A'] * 15 + ['KO_B'] * 15,
                'mixscape_class': ['control'] * 20 + ['KO_A'] * 10 + ['NP'] * 5 + ['KO_B'] * 12 + ['NP'] * 3
            }, index=[f"cell_{i}" for i in range(n_cells)]),
            var=pd.DataFrame(index=[f"GENE_{i}" for i in range(n_genes)]),
            uns={}
        )

        # Add UMAP
        self.adata.obsm['X_umap'] = np.random.randn(n_cells, 2)

        # Add augur results
        self.adata.uns['augur_results'] = pd.DataFrame({
            'AUC': [0.7, 0.8, 0.6]
        }, index=['control', 'KO_A', 'KO_B'])

        self.distance_df = pd.DataFrame(
            np.random.rand(3, 3),
            index=['control', 'KO_A', 'KO_B'],
            columns=['control', 'KO_A', 'KO_B']
        )

        self.de_results = pd.DataFrame({
            'gene': ['A', 'B', 'C', 'D', 'E'],
            'log2FoldChange': [2.0, 1.5, -1.0, 0.5, -2.5],
            'padj': [0.001, 0.01, 0.05, 0.1, 0.0001]
        })

    @patch('visualization.pt.pl.augur_scatter')
    @patch('visualization.plt.subplots')
    def test_plot_augur_results(self, mock_subplots, mock_augur_plot):
        """Test Augur results plotting."""
        mock_fig = Mock()
        mock_ax = Mock()
        mock_subplots.return_value = (mock_fig, mock_ax)

        result = plot_augur_results(self.adata, key='augur_results')

        mock_subplots.assert_called_once()

    def test_plot_augur_results_missing_key(self):
        """Test Augur plotting with missing results."""
        with self.assertRaises(ValueError) as context:
            plot_augur_results(self.adata, key='nonexistent')
        self.assertIn("not found", str(context.exception))

    @patch('visualization.sns.heatmap')
    @patch('visualization.plt.subplots')
    def test_plot_perturbation_distance_heatmap(self, mock_subplots, mock_heatmap):
        """Test distance heatmap plotting."""
        mock_fig = Mock()
        mock_ax = Mock()
        mock_subplots.return_value = (mock_fig, mock_ax)

        result = plot_perturbation_distance_heatmap(self.distance_df)

        mock_subplots.assert_called_once()
        mock_heatmap.assert_called_once()

    @patch('visualization.pt.pl.mixscape_plot')
    @patch('visualization.plt.subplots')
    def test_plot_mixscape_results(self, mock_subplots, mock_mixscape_plot):
        """Test Mixscape results plotting."""
        mock_fig = Mock()
        mock_ax1 = Mock()
        mock_ax2 = Mock()
        mock_subplots.return_value = (mock_fig, [mock_ax1, mock_ax2])

        result = plot_mixscape_results(self.adata)

        mock_subplots.assert_called_once()
        self.assertEqual(mock_mixscape_plot.call_count, 2)

    def test_plot_mixscape_results_missing_column(self):
        """Test Mixscape plotting with missing column."""
        adata_no_mixscape = self.adata.copy()
        del adata_no_mixscape.obs['mixscape_class']

        with self.assertRaises(ValueError) as context:
            plot_mixscape_results(adata_no_mixscape)
        self.assertIn("not found", str(context.exception))

    @patch('visualization.plt.subplots')
    def test_plot_de_volcano(self, mock_subplots):
        """Test volcano plot."""
        mock_fig = Mock()
        mock_ax = Mock()
        mock_subplots.return_value = (mock_fig, mock_ax)

        result = plot_de_volcano(self.de_results)

        mock_subplots.assert_called_once()
        mock_ax.scatter.assert_called_once()

    @patch('visualization.dendrogram')
    @patch('visualization.linkage')
    @patch('visualization.plt.subplots')
    def test_plot_distance_dendrogram(self, mock_subplots, mock_linkage, mock_dendrogram):
        """Test distance dendrogram plotting."""
        mock_fig = Mock()
        mock_ax = Mock()
        mock_subplots.return_value = (mock_fig, mock_ax)

        result = plot_distance_dendrogram(self.distance_df)

        mock_subplots.assert_called_once()
        mock_linkage.assert_called_once()
        mock_dendrogram.assert_called_once()


class TestIntegration(unittest.TestCase):
    """Integration tests for complete workflow."""

    def setUp(self):
        """Create test data."""
        np.random.seed(42)
        n_cells = 60
        n_genes = 100

        self.adata = sc.AnnData(
            X=np.random.lognormal(3, 1, (n_cells, n_genes)),
            obs=pd.DataFrame({
                'perturbation': ['control'] * 20 + ['KO_A'] * 20 + ['KO_B'] * 20,
                'replicate': ['rep1'] * 30 + ['rep2'] * 30
            }, index=[f"cell_{i}" for i in range(n_cells)]),
            var=pd.DataFrame(index=[f"GENE_{i}" for i in range(n_genes)])
        )

    @patch('core_analysis.pt.tl.Mixscape')
    @patch('core_analysis.pt.tl.Augur')
    def test_complete_analysis_workflow(self, mock_augur_class, mock_mixscape_class):
        """Test complete analysis pipeline."""
        # Setup mocks
        mock_augur = Mock()
        mock_augur_class.return_value = mock_augur
        mock_augur.load.return_value = self.adata
        mock_augur.predict.return_value = self.adata

        mock_ms = Mock()
        mock_mixscape_class.return_value = mock_ms

        adata_copy = self.adata.copy()

        result = run_complete_perturbation_analysis(
            adata_copy,
            perturbation_col='perturbation',
            control='control',
            compute_signature=False,
            run_mixscape=False,
            run_augur=True
        )

        mock_augur.load.assert_called_once()
        mock_augur.predict.assert_called_once()


class TestExport(unittest.TestCase):
    """Test export functions."""

    def setUp(self):
        """Create test data."""
        self.de_results = {
            'KO_A': pd.DataFrame({
                'gene': ['A', 'B', 'C'],
                'log2FoldChange': [1.5, -2.0, 0.5],
                'padj': [0.001, 0.0001, 0.1]
            }),
            'KO_B': pd.DataFrame({
                'gene': ['D', 'E', 'F'],
                'log2FoldChange': [2.0, -1.5, 0.3],
                'padj': [0.01, 0.02, 0.2]
            })
        }

    @patch('utils.pd.DataFrame.to_csv')
    @patch('builtins.print')
    def test_export_de_results(self, mock_print, mock_to_csv):
        """Test DE results export."""
        export_de_results(self.de_results, output_prefix='test_de')

        # Should be called once for each perturbation
        self.assertEqual(mock_to_csv.call_count, 2)

    @patch('utils.pd.DataFrame.to_csv')
    @patch('builtins.print')
    def test_export_de_results_significant_only(self, mock_print, mock_to_csv):
        """Test DE results export with significant only filter."""
        export_de_results(
            self.de_results,
            output_prefix='test_de',
            significant_only=True,
            pval_threshold=0.05
        )

        self.assertEqual(mock_to_csv.call_count, 2)


if __name__ == '__main__':
    unittest.main()
