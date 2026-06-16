"""Core analysis functions for COMPASS metabolic flux analysis.

This module provides wrapper functions for the COMPASS package, which performs
metabolic flux inference using flux balance analysis (FBA) for single-cell data.

Reference: Wagner et al., Cell 2021
"""

import os
import re
import numpy as np
import pandas as pd
import scanpy as sc
from anndata import AnnData
from typing import Optional, Union, List, Dict, Any, Tuple
from pathlib import Path
import subprocess
import warnings


def check_compass_dependencies() -> bool:
    """Check if required dependencies are installed.

    Returns:
        True if all dependencies are available
    """
    try:
        import compass
        import scanpy
        import pandas
        import numpy
        return True
    except ImportError as e:
        print(f"Missing dependency: {e}")
        return False


def validate_compass_input(
    adata: AnnData,
    check_raw_counts: bool = True
) -> Dict[str, Any]:
    """Validate input AnnData for COMPASS analysis.

    Args:
        adata: Input AnnData object
        check_raw_counts: Whether to check for raw counts (COMPASS prefers raw counts)

    Returns:
        Dictionary with validation results
    """
    results = {'valid': True, 'warnings': [], 'errors': []}

    # Check dimensions
    if adata.n_obs == 0 or adata.n_vars == 0:
        results['errors'].append("Empty AnnData object")
        results['valid'] = False
        return results

    # Check for gene symbols (not ENSEMBL)
    var_names = adata.var_names[:10]
    ensembl_count = sum(1 for name in var_names if str(name).startswith('ENSG') or str(name).startswith('ENSMUSG'))
    if ensembl_count >= 5:
        results['warnings'].append(
            "Data appears to use ENSEMBL IDs. COMPASS metabolic models expect gene symbols (e.g., 'GAPDH')."
        )

    # Check if data appears to be normalized (COMPASS prefers raw counts)
    if check_raw_counts:
        sample = adata.X[:100, :100] if hasattr(adata.X, 'shape') else adata.X
        if hasattr(sample, 'toarray'):
            sample = sample.toarray()
        if not np.all(sample >= 0):
            results['warnings'].append("Data contains negative values. COMPASS expects non-negative expression values.")

    results['n_cells'] = adata.n_obs
    results['n_genes'] = adata.n_vars

    return results


def prepare_compass_input(
    adata: AnnData,
    output_dir: str,
    layer: Optional[str] = None,
    use_raw: bool = False
) -> str:
    """Prepare input data for COMPASS in TSV format.

    Args:
        adata: AnnData object
        output_dir: Directory to save prepared data
        layer: Which layer to use (default: .X)
        use_raw: Whether to use adata.raw.X

    Returns:
        Path to prepared TSV file
    """
    os.makedirs(output_dir, exist_ok=True)

    # Get expression matrix
    if use_raw and adata.raw is not None:
        expr = pd.DataFrame(
            adata.raw.X.T.toarray() if hasattr(adata.raw.X, 'toarray') else adata.raw.X.T,
            index=adata.raw.var_names,
            columns=adata.obs_names
        )
    elif layer is not None:
        expr = pd.DataFrame(
            adata.layers[layer].T.toarray() if hasattr(adata.layers[layer], 'toarray') else adata.layers[layer].T,
            index=adata.var_names,
            columns=adata.obs_names
        )
    else:
        expr = pd.DataFrame(
            adata.X.T.toarray() if hasattr(adata.X, 'toarray') else adata.X.T,
            index=adata.var_names,
            columns=adata.obs_names
        )

    # Convert gene names to uppercase (COMPASS requirement)
    expr.index = expr.index.str.upper()

    # Handle duplicate gene symbols by summing
    if not expr.index.is_unique:
        expr = expr.groupby(expr.index).sum()

    output_file = os.path.join(output_dir, "compass_input.tsv")
    expr.to_csv(output_file, sep='\t')

    return output_file


def run_compass(
    adata: AnnData,
    output_dir: str,
    model: str = 'RECON2_mat',
    species: str = 'homo_sapiens',
    media: str = 'default-media',
    num_processes: Optional[int] = None,
    lambda_param: float = 0.0,
    num_neighbors: int = 30,
    penalty_diffusion: str = 'knn',
    and_function: str = 'mean',
    select_reactions: Optional[str] = None,
    select_subsystems: Optional[str] = None,
    microcluster_size: Optional[int] = None,
    calc_metabolites: bool = True,
    layer: Optional[str] = None,
    use_raw: bool = False,
    temp_dir: Optional[str] = None,
    verbose: bool = True
) -> Dict[str, pd.DataFrame]:
    """Run COMPASS metabolic flux analysis.

    This is the main function to run COMPASS analysis on single-cell data.

    Args:
        adata: AnnData object with expression data
        output_dir: Directory to save COMPASS outputs
        model: Metabolic model ('RECON2_mat', 'RECON1_mat', 'RECON2.2')
        species: Species ('homo_sapiens' or 'mus_musculus')
        media: Media condition for simulation
        num_processes: Number of parallel processes (default: CPU count)
        lambda_param: Smoothing factor (0-1) for penalty diffusion between cells
        num_neighbors: Number of neighbors for penalty diffusion
        penalty_diffusion: Mode for penalty diffusion ('knn' or 'gaussian')
        and_function: Function for aggregating gene rules ('min', 'median', 'mean')
        select_reactions: File with reactions to analyze (optional)
        select_subsystems: File with subsystems to analyze (optional)
        microcluster_size: Target cells per microcluster for large datasets
        calc_metabolites: Whether to calculate metabolite uptake/secretion scores
        layer: Which adata layer to use (default: .X)
        use_raw: Whether to use adata.raw.X
        temp_dir: Temporary directory for intermediate files
        verbose: Whether to print progress

    Returns:
        Dictionary with reaction_scores, uptake_scores, and secretion_scores DataFrames
    """
    # Validate input
    validation = validate_compass_input(adata)
    if not validation['valid']:
        raise ValueError(f"Invalid input: {validation['errors']}")
    if validation['warnings'] and verbose:
        for warning in validation['warnings']:
            print(f"Warning: {warning}")

    # Create output directories
    os.makedirs(output_dir, exist_ok=True)
    if temp_dir is None:
        temp_dir = os.path.join(output_dir, '_tmp')
    os.makedirs(temp_dir, exist_ok=True)

    # Prepare input data
    if verbose:
        print("Preparing input data...")
    input_file = prepare_compass_input(adata, temp_dir, layer=layer, use_raw=use_raw)

    # Build COMPASS command
    if num_processes is None:
        import multiprocessing
        num_processes = multiprocessing.cpu_count()

    cmd = [
        'compass',
        '--data-mtx', input_file,
        '--model', model,
        '--species', species,
        '--media', media,
        '--output-dir', output_dir,
        '--temp-dir', temp_dir,
        '--num-processes', str(num_processes),
        '--lambda', str(lambda_param),
        '--num-neighbors', str(num_neighbors),
        '--penalty-diffusion', penalty_diffusion,
        '--and-function', and_function,
        '--num-threads', '1'
    ]

    if calc_metabolites:
        cmd.append('--calc-metabolites')

    if microcluster_size is not None:
        cmd.extend(['--microcluster-size', str(microcluster_size)])

    if select_reactions is not None:
        cmd.extend(['--select-reactions', select_reactions])

    if select_subsystems is not None:
        cmd.extend(['--select-subsystems', select_subsystems])

    # Run COMPASS
    if verbose:
        print(f"Running COMPASS with model: {model}")
        print(f"  Species: {species}")
        print(f"  Cells: {adata.n_obs}")
        print(f"  Processes: {num_processes}")
        print(f"  Lambda: {lambda_param}")

    try:
        result = subprocess.run(cmd, capture_output=not verbose, text=True, check=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"COMPASS execution failed: {e.stderr}")
    except FileNotFoundError:
        raise RuntimeError("COMPASS not found. Install with: pip install compass-sc")

    # Load results
    if verbose:
        print("Loading results...")

    results = {}

    reaction_file = os.path.join(output_dir, 'reactions.tsv')
    if os.path.exists(reaction_file):
        results['reaction_scores'] = pd.read_csv(reaction_file, sep='\t', index_col=0)
    else:
        # Try .txt extension
        reaction_file = os.path.join(output_dir, 'reactions.txt')
        if os.path.exists(reaction_file):
            results['reaction_scores'] = pd.read_csv(reaction_file, sep='\t', index_col=0)

    if calc_metabolites:
        uptake_file = os.path.join(output_dir, 'uptake.tsv')
        secretion_file = os.path.join(output_dir, 'secretions.tsv')

        if os.path.exists(uptake_file):
            results['uptake_scores'] = pd.read_csv(uptake_file, sep='\t', index_col=0)

        if os.path.exists(secretion_file):
            results['secretion_scores'] = pd.read_csv(secretion_file, sep='\t', index_col=0)

    if verbose:
        print("COMPASS analysis complete!")
        if 'reaction_scores' in results:
            print(f"  Reactions: {results['reaction_scores'].shape[0]}")
        if 'uptake_scores' in results:
            print(f"  Metabolites (uptake): {results['uptake_scores'].shape[0]}")

    return results


def load_compass_results(
    output_dir: str,
    prefix: str = ''
) -> Dict[str, pd.DataFrame]:
    """Load COMPASS results from output directory.

    Args:
        output_dir: Directory containing COMPASS outputs
        prefix: Prefix for column names in output

    Returns:
        Dictionary with reaction_scores, uptake_scores, secretion_scores
    """
    results = {}

    # Try both .tsv and .txt extensions
    for ext in ['.tsv', '.txt']:
        reaction_file = os.path.join(output_dir, f'reactions{ext}')
        if os.path.exists(reaction_file):
            results['reaction_scores'] = pd.read_csv(reaction_file, sep='\t', index_col=0)
            break

    for ext in ['.tsv', '.txt']:
        uptake_file = os.path.join(output_dir, f'uptake{ext}')
        if os.path.exists(uptake_file):
            results['uptake_scores'] = pd.read_csv(uptake_file, sep='\t', index_col=0)
            break

    for ext in ['.tsv', '.txt']:
        secretion_file = os.path.join(output_dir, f'secretions{ext}')
        if os.path.exists(secretion_file):
            results['secretion_scores'] = pd.read_csv(secretion_file, sep='\t', index_col=0)
            break

    # Apply prefix to column names if specified
    if prefix:
        for key in results:
            results[key].columns = [f"{prefix}{col}" for col in results[key].columns]

    return results


def add_compass_results_to_adata(
    adata: AnnData,
    compass_results: Dict[str, pd.DataFrame],
    reaction_scores_obs: bool = False,
    prefix: str = 'compass_'
) -> AnnData:
    """Add COMPASS results to AnnData object.

    Args:
        adata: AnnData object
        compass_results: Results dictionary from run_compass or load_compass_results
        reaction_scores_obs: If True, add reaction scores to obs (wide format).
                            If False, store as obsp/obsm (cell x reaction matrix).
        prefix: Prefix for stored data

    Returns:
        AnnData with COMPASS results added
    """
    adata = adata.copy()

    # Add reaction scores
    if 'reaction_scores' in compass_results:
        reaction_df = compass_results['reaction_scores']

        # Ensure columns match adata.obs_names
        reaction_df = reaction_df.loc[:, reaction_df.columns.isin(adata.obs_names)]
        reaction_df = reaction_df.reindex(columns=adata.obs_names)

        if reaction_scores_obs:
            # Add to obs (may create many columns)
            warnings.warn("Adding reaction scores to obs may create thousands of columns")
            for reaction in reaction_df.index:
                adata.obs[f"{prefix}reaction_{reaction}"] = reaction_df.loc[reaction].values
        else:
            # Store as obsm (cells x reactions)
            adata.obsm[f"{prefix}reaction_scores"] = reaction_df.T.values
            adata.uns[f"{prefix}reaction_names"] = list(reaction_df.index)

    # Add metabolite scores to obs
    if 'uptake_scores' in compass_results:
        uptake_df = compass_results['uptake_scores']
        uptake_df = uptake_df.loc[:, uptake_df.columns.isin(adata.obs_names)]
        uptake_df = uptake_df.reindex(columns=adata.obs_names)

        for metab in uptake_df.index:
            adata.obs[f"{prefix}uptake_{metab}"] = uptake_df.loc[metab].values

    if 'secretion_scores' in compass_results:
        secretion_df = compass_results['secretion_scores']
        secretion_df = secretion_df.loc[:, secretion_df.columns.isin(adata.obs_names)]
        secretion_df = secretion_df.reindex(columns=adata.obs_names)

        for metab in secretion_df.index:
            adata.obs[f"{prefix}secretion_{metab}"] = secretion_df.loc[metab].values

    return adata


def get_available_models() -> pd.DataFrame:
    """Get list of available metabolic models in COMPASS.

    Returns:
        DataFrame with model information
    """
    models = [
        {
            'model': 'RECON2_mat',
            'name': 'RECON2',
            'species': 'Homo sapiens',
            'description': 'Human metabolic network reconstruction (recommended)',
            'reactions': ~7440,
            'metabolites': ~5060
        },
        {
            'model': 'RECON1_mat',
            'name': 'RECON1',
            'species': 'Homo sapiens',
            'description': 'Original human metabolic reconstruction',
            'reactions': ~3740,
            'metabolites': ~2760
        },
        {
            'model': 'RECON2.2',
            'name': 'RECON2.2',
            'species': 'Homo sapiens',
            'description': 'Updated RECON2 with improved annotations',
            'reactions': ~7780,
            'metabolites': ~5320
        },
        {
            'model': 'Mouse-GEM',
            'name': 'Mouse-GEM',
            'species': 'Mus musculus',
            'description': 'Mouse genome-scale metabolic model',
            'reactions': ~7600,
            'metabolites': ~4900
        }
    ]

    return pd.DataFrame(models)


def list_model_genes(
    model: str = 'RECON2_mat',
    species: str = 'homo_sapiens'
) -> List[str]:
    """List genes included in a metabolic model.

    Args:
        model: Metabolic model name
        species: Species name

    Returns:
        List of gene symbols in the model
    """
    try:
        cmd = ['compass', '--list-genes', '/dev/stdout', '--model', model, '--species', species]
        result = subprocess.run(cmd, capture_output=True, text=True)
        genes = result.stdout.strip().split('\n')
        return [g for g in genes if g]
    except Exception as e:
        print(f"Error listing genes: {e}")
        return []


def list_model_reactions(
    model: str = 'RECON2_mat',
    species: str = 'homo_sapiens'
) -> Dict[str, str]:
    """List reactions and their subsystems in a metabolic model.

    Args:
        model: Metabolic model name
        species: Species name

    Returns:
        Dictionary mapping reaction IDs to subsystems
    """
    try:
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_file = f.name

        cmd = ['compass', '--list-reactions', temp_file, '--model', model, '--species', species]
        subprocess.run(cmd, capture_output=True)

        import json
        with open(temp_file, 'r') as f:
            reactions = json.load(f)

        os.remove(temp_file)
        return reactions
    except Exception as e:
        print(f"Error listing reactions: {e}")
        return {}


def analyze_differential_flux(
    reaction_scores: pd.DataFrame,
    group_labels: Union[pd.Series, np.ndarray, List],
    method: str = 'wilcoxon'
) -> pd.DataFrame:
    """Perform differential flux analysis between groups.

    Args:
        reaction_scores: DataFrame with reaction scores (reactions x cells)
        group_labels: Group labels for each cell
        method: Statistical test ('wilcoxon', 't-test')

    Returns:
        DataFrame with differential flux statistics
    """
    from scipy import stats

    results = []
    groups = pd.Series(group_labels).unique()

    if len(groups) != 2:
        raise ValueError(f"Expected 2 groups, found {len(groups)}: {groups}")

    group_a, group_b = groups

    for reaction in reaction_scores.index:
        scores_a = reaction_scores.loc[reaction, group_labels == group_a].dropna()
        scores_b = reaction_scores.loc[reaction, group_labels == group_b].dropna()

        if len(scores_a) < 3 or len(scores_b) < 3:
            continue

        if method == 'wilcoxon':
            statistic, pvalue = stats.ranksums(scores_a, scores_b)
        elif method == 't-test':
            statistic, pvalue = stats.ttest_ind(scores_a, scores_b)
        else:
            raise ValueError(f"Unknown method: {method}")

        log2fc = np.log2((np.mean(scores_b) + 1e-10) / (np.mean(scores_a) + 1e-10))

        results.append({
            'reaction': reaction,
            'mean_A': np.mean(scores_a),
            'mean_B': np.mean(scores_b),
            'log2FC': log2fc,
            'statistic': statistic,
            'pvalue': pvalue
        })

    results_df = pd.DataFrame(results)

    if len(results_df) > 0:
        from statsmodels.stats.multitest import multipletests
        results_df['padj'] = multipletests(results_df['pvalue'], method='fdr_bh')[1]
        results_df = results_df.sort_values('padj')

    return results_df


def summarize_metabolic_activity(
    reaction_scores: pd.DataFrame,
    subsystems: Optional[Dict[str, str]] = None
) -> pd.DataFrame:
    """Summarize metabolic activity by subsystem.

    Args:
        reaction_scores: DataFrame with reaction scores
        subsystems: Dictionary mapping reaction IDs to subsystems

    Returns:
        DataFrame with subsystem-level summary statistics
    """
    if subsystems is None:
        # Default subsystems for RECON2
        subsystems = infer_subsystems(reaction_scores.index)

    # Add subsystem column
    reaction_scores_copy = reaction_scores.copy()
    reaction_scores_copy['subsystem'] = reaction_scores_copy.index.map(subsystems)
    reaction_scores_copy = reaction_scores_copy.dropna(subset=['subsystem'])

    # Summarize by subsystem
    summary = reaction_scores_copy.groupby('subsystem').agg({
        col: ['mean', 'std', 'max'] for col in reaction_scores.columns
    })

    return summary


def infer_subsystems(reaction_ids: pd.Index) -> Dict[str, str]:
    """Infer subsystems from reaction IDs using common naming patterns.

    Args:
        reaction_ids: Index of reaction IDs

    Returns:
        Dictionary mapping reaction IDs to inferred subsystems
    """
    # Common RECON2 subsystems based on reaction prefixes/patterns
    subsystem_patterns = {
        r'GLC|G6P|F6P|FBA|TPI|GAP|PG[KM]|ENO|PYK|LDH': 'Glycolysis/Gluconeogenesis',
        r'CIT|ACO|IDH|OGDC|SUCL|SDH|FUM|MDH|PC': 'Citric acid cycle',
        r'PDH|ACCOA|CS': 'Pyruvate metabolism',
        r'ETF|NADH|FADH|CYO|ATP synthase': 'Oxidative phosphorylation',
        r'FAO|CPT|ACOX|ECH|HMGCOA|ACACT': 'Fatty acid metabolism',
        r'GLN|GLU|ASP|ALA|SER|CYS|GLY|THR|MET|VAL|LEU|ILE|PHE|TYR|TRP|HIS|LYS|ARG|PRO': 'Amino acid metabolism',
        r'PNT|PPP|G6PDH|TKT|TAL': 'Pentose phosphate pathway',
        r'GLUT|SLC2A|SLC5A': 'Transport',
        r'EX_': 'Exchange',
        r'_pos$|_neg$': 'Reaction (bidirectional)'
    }

    subsystems = {}
    for rxn in reaction_ids:
        rxn_str = str(rxn)
        assigned = False
        for pattern, subsystem in subsystem_patterns.items():
            if re.search(pattern, rxn_str, re.IGNORECASE):
                subsystems[rxn] = subsystem
                assigned = True
                break
        if not assigned:
            subsystems[rxn] = 'Other'

    return subsystems


def run_compass_pipeline(
    adata: AnnData,
    output_dir: str,
    groupby: Optional[str] = None,
    compare_groups: Optional[List[str]] = None,
    **compass_kwargs
) -> Dict[str, Any]:
    """Complete COMPASS pipeline including differential analysis.

    Args:
        adata: AnnData object
        output_dir: Output directory
        groupby: Column in adata.obs for grouping
        compare_groups: Two groups to compare for differential analysis
        **compass_kwargs: Additional arguments for run_compass

    Returns:
        Dictionary with results and analysis outputs
    """
    results = {}

    # Run COMPASS
    compass_results = run_compass(adata, output_dir, **compass_kwargs)
    results['compass_results'] = compass_results

    # Add to AnnData
    adata_with_compass = add_compass_results_to_adata(adata, compass_results)
    results['adata'] = adata_with_compass

    # Differential analysis if groups specified
    if groupby is not None and compare_groups is not None:
        if 'reaction_scores' in compass_results:
            groups = adata.obs[groupby].values
            diff_results = analyze_differential_flux(
                compass_results['reaction_scores'],
                groups
            )
            results['differential_flux'] = diff_results

    return results
