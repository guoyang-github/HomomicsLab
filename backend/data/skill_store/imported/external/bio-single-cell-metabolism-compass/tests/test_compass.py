"""Unit tests for COMPASS metabolic flux analysis.

Tests for core_analysis, utils, and visualization modules.
"""

import unittest
import numpy as np
import pandas as pd
import scanpy as sc
from anndata import AnnData
import tempfile
import os
import shutil
from unittest.mock import Mock, patch, MagicMock

# Add scripts to path
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'scripts', 'python'))

from core_analysis import (
    check_compass_dependencies,
    validate_compass_input,
    prepare_compass_input,
    load_compass_results,
    add_compass_results_to_adata,
    get_available_models,
    analyze_differential_flux,
    summarize_metabolic_activity,
    infer_subsystems,
    run_compass_pipeline
)

from utils import (
    check_gene_overlap,
    recommend_model,
    get_model_catalog,
    summarize_compass_results,
    filter_reactions_by_activity,
    get_top_reactions,
    get_top_metabolites,
    estimate_compass_runtime,
    create_test_data,
    validate_compass_installation,
    create_reaction_subset_file
)


class TestCoreAnalysis(unittest.TestCase):
    """Test core analysis functions."""

    def setUp(self):
        """Create test data."""
        np.random.seed(42)
        self.n_cells = 50
        self.n_genes = 100

        self.adata = AnnData(
            X=np.random.lognormal(3, 1, (self.n_cells, self.n_genes)),
            obs=pd.DataFrame({
                'condition': ['control'] * 25 + ['treatment'] * 25,
                'cell_type': ['A'] * 15 + ['B'] * 20 + ['C'] * 15
            }, index=[f"cell_{i}" for i in range(self.n_cells)]),
            var=pd.DataFrame(index=[f"GENE_{i}" for i in range(self.n_genes)])
        )

        # Create mock COMPASS results
        self.mock_results = {
            'reaction_scores': pd.DataFrame(
                np.random.gamma(2, 0.5, (20, self.n_cells)),
                index=[f"R{i}" for i in range(20)],
                columns=self.adata.obs_names
            ),
            'uptake_scores': pd.DataFrame(
                np.random.gamma(2, 0.5, (10, self.n_cells)),
                index=[f"M{i}" for i in range(10)],
                columns=self.adata.obs_names
            ),
            'secretion_scores': pd.DataFrame(
                np.random.gamma(2, 0.5, (10, self.n_cells)),
                index=[f"M{i}" for i in range(10)],
                columns=self.adata.obs_names
            )
        }

    def test_check_compass_dependencies(self):
        """Test dependency checking."""
        result = check_compass_dependencies()
        self.assertIsInstance(result, bool)

    def test_validate_compass_input(self):
        """Test input validation."""
        validation = validate_compass_input(self.adata)

        self.assertTrue(validation['valid'])
        self.assertIn('n_cells', validation)
        self.assertIn('n_genes', validation)
        self.assertEqual(validation['n_cells'], self.n_cells)
        self.assertEqual(validation['n_genes'], self.n_genes)

    def test_validate_compass_input_empty(self):
        """Test validation with empty data."""
        empty_adata = AnnData(X=np.zeros((0, 10)))
        validation = validate_compass_input(empty_adata)

        self.assertFalse(validation['valid'])
        self.assertIn('errors', validation)

    def test_validate_compass_input_ensembl(self):
        """Test validation with ENSEMBL IDs."""
        ensembl_adata = AnnData(
            X=np.random.lognormal(3, 1, (10, 10)),
            var=pd.DataFrame(index=[f"ENSG{i:011d}" for i in range(10)])
        )
        validation = validate_compass_input(ensembl_adata)

        self.assertTrue(validation['valid'])
        self.assertTrue(any('ENSEMBL' in w for w in validation['warnings']))

    def test_prepare_compass_input(self):
        """Test input preparation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = prepare_compass_input(self.adata, tmpdir)

            self.assertTrue(os.path.exists(output_file))

            # Check file contents
            loaded = pd.read_csv(output_file, sep='\t', index_col=0)
            self.assertEqual(loaded.shape[1], self.n_cells)

    def test_load_compass_results(self):
        """Test loading COMPASS results."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Save mock results
            self.mock_results['reaction_scores'].to_csv(
                os.path.join(tmpdir, 'reactions.tsv'), sep='\t'
            )

            # Load results
            loaded = load_compass_results(tmpdir)

            self.assertIn('reaction_scores', loaded)
            self.assertEqual(loaded['reaction_scores'].shape[0], 20)

    def test_add_compass_results_to_adata(self):
        """Test adding results to AnnData."""
        adata_modified = add_compass_results_to_adata(
            self.adata.copy(),
            self.mock_results
        )

        # Check that obsm key was added
        self.assertIn('compass_reaction_scores', adata_modified.obsm)

        # Check that metabolite scores were added to obs
        self.assertTrue(any('compass_uptake' in c for c in adata_modified.obs.columns))

    def test_get_available_models(self):
        """Test getting available models."""
        models = get_available_models()

        self.assertIsInstance(models, pd.DataFrame)
        self.assertIn('model', models.columns)
        self.assertIn('RECON2_mat', models['model'].values)

    def test_analyze_differential_flux(self):
        """Test differential flux analysis."""
        groups = self.adata.obs['condition']

        diff_results = analyze_differential_flux(
            self.mock_results['reaction_scores'],
            groups,
            method='wilcoxon'
        )

        self.assertIsInstance(diff_results, pd.DataFrame)
        if len(diff_results) > 0:
            self.assertIn('reaction', diff_results.columns)
            self.assertIn('pvalue', diff_results.columns)
            self.assertIn('padj', diff_results.columns)
            self.assertIn('log2FC', diff_results.columns)

    def test_analyze_differential_flux_invalid_groups(self):
        """Test differential flux with wrong number of groups."""
        groups = self.adata.obs['cell_type']  # 3 groups

        with self.assertRaises(ValueError):
            analyze_differential_flux(
                self.mock_results['reaction_scores'],
                groups
            )

    def test_summarize_metabolic_activity(self):
        """Test subsystem activity summarization."""
        subsystems = infer_subsystems(self.mock_results['reaction_scores'].index)

        summary = summarize_metabolic_activity(
            self.mock_results['reaction_scores'],
            subsystems
        )

        self.assertIsInstance(summary, pd.DataFrame)

    def test_infer_subsystems(self):
        """Test subsystem inference."""
        reaction_ids = pd.Index([
            'GAPDH_pos', 'LDHA_pos', 'ATP5F1A_pos',
            'CS_pos', 'RANDOM_pos'
        ])

        subsystems = infer_subsystems(reaction_ids)

        self.assertIsInstance(subsystems, dict)
        self.assertEqual(len(subsystems), len(reaction_ids))
        # GAPDH should be in Glycolysis
        self.assertIn('Glycolysis', subsystems['GAPDH_pos'])


class TestUtils(unittest.TestCase):
    """Test utility functions."""

    def setUp(self):
        """Create test data."""
        np.random.seed(42)
        self.adata = AnnData(
            X=np.random.lognormal(3, 1, (50, 100)),
            obs=pd.DataFrame({'group': ['A'] * 25 + ['B'] * 25}),
            var=pd.DataFrame(index=[f"GENE_{i}" for i in range(100)])
        )

    def test_check_gene_overlap(self):
        """Test gene overlap checking."""
        model_genes = [f"GENE_{i}" for i in range(50)]  # 50% overlap

        overlap = check_gene_overlap(self.adata, model_genes)

        self.assertEqual(overlap['n_overlap'], 50)
        self.assertEqual(overlap['n_data_genes'], 100)
        self.assertEqual(overlap['overlap_fraction'], 1.0)

    def test_recommend_model(self):
        """Test model recommendation."""
        human_model = recommend_model(species='human')
        self.assertEqual(human_model, 'RECON2_mat')

        mouse_model = recommend_model(species='mouse')
        self.assertEqual(mouse_model, 'Mouse-GEM')

    def test_get_model_catalog(self):
        """Test model catalog."""
        catalog = get_model_catalog()

        self.assertIsInstance(catalog, pd.DataFrame)
        self.assertIn('model', catalog.columns)
        self.assertIn('species', catalog.columns)

    def test_summarize_compass_results(self):
        """Test results summarization."""
        results = {
            'reaction_scores': pd.DataFrame(
                np.random.gamma(2, 0.5, (20, 50))
            ),
            'uptake_scores': pd.DataFrame(
                np.random.gamma(2, 0.5, (10, 50))
            )
        }

        summary = summarize_compass_results(results)

        self.assertIn('reactions', summary)
        self.assertIn('uptake', summary)
        self.assertEqual(summary['reactions']['n_reactions'], 20)

    def test_filter_reactions_by_activity(self):
        """Test reaction filtering."""
        reaction_scores = pd.DataFrame(
            np.random.gamma(2, 0.5, (50, 100))
        )
        # Make some reactions inactive
        reaction_scores.iloc[:10, :] = 0.01

        filtered = filter_reactions_by_activity(
            reaction_scores,
            min_activity=0.1,
            min_cells=5
        )

        self.assertLess(filtered.shape[0], reaction_scores.shape[0])

    def test_get_top_reactions(self):
        """Test getting top reactions."""
        reaction_scores = pd.DataFrame(
            np.random.gamma(2, 0.5, (50, 100))
        )

        top = get_top_reactions(reaction_scores, n=10, by='mean')

        self.assertEqual(top.shape[0], 10)

    def test_get_top_metabolites(self):
        """Test getting top metabolites."""
        uptake = pd.DataFrame(np.random.gamma(2, 0.5, (20, 50)))
        secretion = pd.DataFrame(np.random.gamma(2, 0.5, (20, 50)))

        top = get_top_metabolites(uptake, secretion, n=5)

        self.assertIn('uptake', top)
        self.assertIn('secretion', top)
        self.assertEqual(top['uptake'].shape[0], 5)

    def test_estimate_compass_runtime(self):
        """Test runtime estimation."""
        estimate = estimate_compass_runtime(
            n_cells=1000,
            n_processes=4,
            model='RECON2_mat'
        )

        self.assertIn('estimated_total', estimate)
        self.assertIn('per_cell', estimate)

    def test_create_test_data(self):
        """Test test data creation."""
        adata = create_test_data(
            n_cells=100,
            n_genes=500,
            n_cell_types=3
        )

        self.assertEqual(adata.n_obs, 100)
        self.assertEqual(adata.n_vars, 500)
        self.assertIn('cell_type', adata.obs.columns)

    def test_validate_compass_installation(self):
        """Test installation validation."""
        validation = validate_compass_installation()

        self.assertIn('compass_installed', validation)
        self.assertIn('cplex_installed', validation)
        self.assertIsInstance(validation['compass_installed'], bool)

    def test_create_reaction_subset_file(self):
        """Test creating reaction subset file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            reactions = ['R1', 'R2', 'R3']
            output_file = os.path.join(tmpdir, 'selected_reactions.txt')

            result = create_reaction_subset_file(reactions, output_file)

            self.assertTrue(os.path.exists(result))
            with open(result, 'r') as f:
                lines = [l.strip() for l in f.readlines()]
            self.assertEqual(lines, reactions)


class TestVisualization(unittest.TestCase):
    """Test visualization functions."""

    def setUp(self):
        """Create test data."""
        np.random.seed(42)
        self.reaction_scores = pd.DataFrame(
            np.random.gamma(2, 0.5, (30, 50)),
            index=[f"R{i}" for i in range(30)],
            columns=[f"cell_{i}" for i in range(50)]
        )
        self.uptake_scores = pd.DataFrame(
            np.random.gamma(2, 0.5, (15, 50)),
            index=[f"M{i}" for i in range(15)],
            columns=[f"cell_{i}" for i in range(50)]
        )

    @patch('matplotlib.pyplot.savefig')
    def test_plot_reaction_heatmap(self, mock_savefig):
        """Test reaction heatmap plotting."""
        from visualization import plot_reaction_heatmap

        fig = plot_reaction_heatmap(
            self.reaction_scores,
            n_top=20,
            save_path='test.png'
        )

        self.assertIsNotNone(fig)
        mock_savefig.assert_called_once()

    @patch('matplotlib.pyplot.savefig')
    def test_plot_metabolite_scores(self, mock_savefig):
        """Test metabolite score plotting."""
        from visualization import plot_metabolite_scores

        fig = plot_metabolite_scores(
            self.uptake_scores,
            n_top=10,
            save_path='test.png'
        )

        self.assertIsNotNone(fig)
        mock_savefig.assert_called_once()

    @patch('matplotlib.pyplot.savefig')
    def test_plot_differential_flux(self, mock_savefig):
        """Test differential flux plotting."""
        from visualization import plot_differential_flux

        diff_results = pd.DataFrame({
            'reaction': [f'R{i}' for i in range(20)],
            'log2FC': np.random.randn(20),
            'pvalue': np.random.uniform(0, 0.1, 20),
            'padj': np.random.uniform(0, 0.1, 20)
        })

        fig = plot_differential_flux(
            diff_results,
            save_path='test.png'
        )

        self.assertIsNotNone(fig)
        mock_savefig.assert_called_once()


class TestIntegration(unittest.TestCase):
    """Integration tests for the full workflow."""

    def test_full_workflow_mock(self):
        """Test full workflow with mocked COMPASS."""
        # Create test data
        adata = create_test_data(n_cells=30, n_genes=200)

        # Validate input
        validation = validate_compass_input(adata)
        self.assertTrue(validation['valid'])

        # Create mock results
        results = {
            'reaction_scores': pd.DataFrame(
                np.random.gamma(2, 0.5, (20, adata.n_obs)),
                columns=adata.obs_names
            ),
            'uptake_scores': pd.DataFrame(
                np.random.gamma(2, 0.5, (10, adata.n_obs)),
                columns=adata.obs_names
            )
        }

        # Add to AnnData
        adata_modified = add_compass_results_to_adata(adata, results)
        self.assertIn('compass_reaction_scores', adata_modified.obsm)

        # Summarize
        summary = summarize_compass_results(results)
        self.assertIn('reactions', summary)


if __name__ == '__main__':
    # Run tests
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestCoreAnalysis))
    suite.addTests(loader.loadTestsFromTestCase(TestUtils))
    suite.addTests(loader.loadTestsFromTestCase(TestVisualization))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Exit with error code if tests failed
    exit(0 if result.wasSuccessful() else 1)
