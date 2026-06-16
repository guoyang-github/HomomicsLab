"""Core analysis functions for FastCCC cell-cell communication analysis.

This module provides wrapper functions for the FastCCC package, which performs
permutation-free cell-cell communication analysis using FFT-based convolution.

Reference: Hou et al., Nature Communications 2025
"""

import os
import re
import numpy as np
import pandas as pd
import scanpy as sc
from anndata import AnnData
from typing import Optional, Union, List, Dict, Any, Tuple
from pathlib import Path
import warnings


def check_fastccc_dependencies() -> bool:
    """Check if required dependencies are installed.

    Returns:
        True if all dependencies are available
    """
    try:
        import fastccc
        import scanpy
        import pandas
        import numpy
        return True
    except ImportError as e:
        print(f"Missing dependency: {e}")
        return False


def validate_fastccc_input(
    adata: AnnData,
    groupby: str,
    check_normalized: bool = True
) -> Dict[str, Any]:
    """Validate input AnnData for FastCCC analysis.

    Args:
        adata: Input AnnData object
        groupby: Column name for cell type annotations
        check_normalized: Whether to check for normalized data

    Returns:
        Dictionary with validation results
    """
    results = {'valid': True, 'warnings': [], 'errors': []}

    # Check dimensions
    if adata.n_obs == 0 or adata.n_vars == 0:
        results['errors'].append("Empty AnnData object")
        results['valid'] = False
        return results

    # Check for cell type annotations
    if groupby not in adata.obs.columns:
        results['errors'].append(f"Column '{groupby}' not found in adata.obs")
        results['valid'] = False
    else:
        n_celltypes = adata.obs[groupby].nunique()
        if n_celltypes < 2:
            results['errors'].append(f"Need at least 2 cell types, found {n_celltypes}")
            results['valid'] = False
        results['n_celltypes'] = n_celltypes

    # Check for gene symbols (not ENSEMBL)
    var_names = adata.var_names[:10]
    ensembl_count = sum(1 for name in var_names if str(name).startswith('ENSG') or str(name).startswith('ENSMUSG'))
    if ensembl_count >= 5:
        results['warnings'].append(
            "Data appears to use ENSEMBL IDs. FastCCC expects gene symbols."
        )

    # Check if data is sparse (FastCCC requirement)
    if not hasattr(adata.X, 'toarray') and not hasattr(adata.X, 'todense'):
        results['warnings'].append(
            "Data is not in sparse format. FastCCC works best with sparse matrices."
        )

    results['n_cells'] = adata.n_obs
    results['n_genes'] = adata.n_vars

    return results


def run_fastccc(
    adata: AnnData,
    database_file_path: str,
    groupby: str,
    save_path: Optional[str] = None,
    single_unit_summary: str = 'Mean',
    complex_aggregation: str = 'Minimum',
    lr_combination: str = 'Arithmetic',
    min_percentile: float = 0.1,
    use_deg: bool = False,
    style: Optional[str] = None,
    verbose: bool = True
) -> Dict[str, pd.DataFrame]:
    """Run FastCCC cell-cell communication analysis.

    This is the main function to run FastCCC analysis on single-cell data.

    Args:
        adata: AnnData object with expression data
        database_file_path: Path to LR interaction database
        groupby: Column name for cell type annotations
        save_path: Directory to save results (default: './results/')
        single_unit_summary: Method for single-unit summary ('Mean', 'Median', 'Q3', 'Quantile_0.9')
        complex_aggregation: Method for complex aggregation ('Minimum', 'Average')
        lr_combination: Method for L-R combination ('Arithmetic', 'Geometric')
        min_percentile: Minimum percentile threshold for expression
        use_deg: Whether to filter by differentially expressed genes
        style: Style for analysis (None or 'cpdb' for CellPhoneDB-style)
        verbose: Whether to print progress

    Returns:
        Dictionary with interactions_strength, pvals, and percents_analysis DataFrames
    """
    try:
        from fastccc import core as fastccc_core
    except ImportError:
        raise ImportError("FastCCC not installed. Install with: pip install fastccc")

    # Validate input
    validation = validate_fastccc_input(adata, groupby)
    if not validation['valid']:
        raise ValueError(f"Invalid input: {validation['errors']}")
    if validation['warnings'] and verbose:
        for warning in validation['warnings']:
            print(f"Warning: {warning}")

    # Create cell type file
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        celltype_file = f.name
        adata.obs[[groupby]].to_csv(f, sep='\t', index=True)

    try:
        # Create temporary counts file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            counts_file = f.name
            # Save as TSV format
            pd.DataFrame(
                adata.X.T.toarray() if hasattr(adata.X, 'toarray') else adata.X.T,
                index=adata.var_names,
                columns=adata.obs_names
            ).to_csv(f, sep='\t')

        # Run FastCCC
        if verbose:
            print(f"Running FastCCC with {validation['n_celltypes']} cell types...")
            print(f"  Single unit summary: {single_unit_summary}")
            print(f"  Complex aggregation: {complex_aggregation}")
            print(f"  L-R combination: {lr_combination}")

        interactions_strength, pvals, percents_analysis = fastccc_core.statistical_analysis_method(
            database_file_path=database_file_path,
            celltype_file_path=celltype_file,
            counts_file_path=counts_file,
            convert_type='hgnc_symbol',
            single_unit_summary=single_unit_summary,
            complex_aggregation=complex_aggregation,
            lr_combination=lr_combination,
            min_percentile=min_percentile,
            style=style,
            use_DEG=use_deg,
            save_path=save_path
        )

        if verbose:
            print("FastCCC analysis complete!")
            print(f"  Interactions tested: {interactions_strength.shape[1]}")
            print(f"  Cell type pairs: {interactions_strength.shape[0]}")

        return {
            'interactions_strength': interactions_strength,
            'pvals': pvals,
            'percents_analysis': percents_analysis
        }

    finally:
        # Cleanup temp files
        if os.path.exists(celltype_file):
            os.remove(celltype_file)
        if os.path.exists(counts_file):
            os.remove(counts_file)


def run_fastccc_cauchy_combined(
    adata: AnnData,
    database_file_path: str,
    groupby: str,
    save_path: Optional[str] = None,
    single_unit_summary_list: List[str] = ['Mean', 'Median', 'Q3', 'Quantile_0.9'],
    complex_aggregation_list: List[str] = ['Minimum', 'Average'],
    lr_combination_list: List[str] = ['Arithmetic', 'Geometric'],
    min_percentile: float = 0.1,
    use_deg: bool = False,
    verbose: bool = True
) -> Dict[str, Any]:
    """Run FastCCC with Cauchy combination of multiple scoring methods.

    This function runs multiple scoring methods and combines them using
    Cauchy combination for more robust results.

    Args:
        adata: AnnData object
        database_file_path: Path to LR interaction database
        groupby: Column name for cell type annotations
        save_path: Directory to save results
        single_unit_summary_list: List of single-unit summary methods
        complex_aggregation_list: List of complex aggregation methods
        lr_combination_list: List of L-R combination methods
        min_percentile: Minimum percentile threshold
        use_deg: Whether to filter by DEGs
        verbose: Whether to print progress

    Returns:
        Dictionary with results and significant interactions
    """
    try:
        from fastccc import core as fastccc_core
    except ImportError:
        raise ImportError("FastCCC not installed.")

    # Validate input
    validation = validate_fastccc_input(adata, groupby)
    if not validation['valid']:
        raise ValueError(f"Invalid input: {validation['errors']}")

    # Create temporary files
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        celltype_file = f.name
        adata.obs[[groupby]].to_csv(f, sep='\t', index=True)

    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            counts_file = f.name
            pd.DataFrame(
                adata.X.T.toarray() if hasattr(adata.X, 'toarray') else adata.X.T,
                index=adata.var_names,
                columns=adata.obs_names
            ).to_csv(f, sep='\t')

        if verbose:
            print(f"Running FastCCC with Cauchy combination...")
            print(f"  Methods to combine: {len(single_unit_summary_list) * len(complex_aggregation_list) * len(lr_combination_list)}")

        fastccc_core.Cauchy_combination_of_statistical_analysis_methods(
            database_file_path=database_file_path,
            celltype_file_path=celltype_file,
            counts_file_path=counts_file,
            convert_type='hgnc_symbol',
            single_unit_summary_list=single_unit_summary_list,
            complex_aggregation_list=complex_aggregation_list,
            lr_combination_list=lr_combination_list,
            min_percentile=min_percentile,
            save_path=save_path,
            use_DEG=use_deg
        )

        if verbose:
            print("FastCCC Cauchy combination complete!")

        # Load results
        if save_path:
            import glob
            result_files = glob.glob(f'{save_path}/*significant_results.tsv')
            if result_files:
                significant_results = pd.read_csv(result_files[0], sep='\t')
                return {'significant_results': significant_results}

        return {}

    finally:
        if os.path.exists(celltype_file):
            os.remove(celltype_file)
        if os.path.exists(counts_file):
            os.remove(counts_file)


def load_fastccc_results(
    result_dir: str,
    task_id: Optional[str] = None
) -> Dict[str, pd.DataFrame]:
    """Load FastCCC results from output directory.

    Args:
        result_dir: Directory containing FastCCC outputs
        task_id: Optional task ID to filter files

    Returns:
        Dictionary with interactions_strength, pvals, percents_analysis
    """
    results = {}
    import glob

    # Find files
    if task_id:
        strength_files = glob.glob(f'{result_dir}/{task_id}*interactions_strength.tsv')
        pval_files = glob.glob(f'{result_dir}/{task_id}*pvals.tsv')
        percent_files = glob.glob(f'{result_dir}/{task_id}*percents_analysis.tsv')
    else:
        strength_files = glob.glob(f'{result_dir}/*interactions_strength.tsv')
        pval_files = glob.glob(f'{result_dir}/*pvals.tsv')
        percent_files = glob.glob(f'{result_dir}/*percents_analysis.tsv')

    # Load files
    if strength_files:
        results['interactions_strength'] = pd.read_csv(strength_files[0], sep='\t', index_col=0)
    if pval_files:
        results['pvals'] = pd.read_csv(pval_files[0], sep='\t', index_col=0)
    if percent_files:
        results['percents_analysis'] = pd.read_csv(percent_files[0], sep='\t', index_col=0)

    # Try to load Cauchy combined results
    cauchy_files = glob.glob(f'{result_dir}/*Cauchy*pvals.tsv')
    if cauchy_files:
        results['cauchy_pvals'] = pd.read_csv(cauchy_files[0], sep='\t', index_col=0)

    significant_files = glob.glob(f'{result_dir}/*significant_results.tsv')
    if significant_files:
        results['significant_results'] = pd.read_csv(significant_files[0], sep='\t')

    return results


def get_significant_interactions(
    pvals: pd.DataFrame,
    interactions_strength: Optional[pd.DataFrame] = None,
    pval_threshold: float = 0.05,
    database_file_path: Optional[str] = None
) -> pd.DataFrame:
    """Extract significant interactions from p-value matrix.

    Args:
        pvals: DataFrame with p-values
        interactions_strength: Optional DataFrame with interaction strengths
        pval_threshold: P-value threshold for significance
        database_file_path: Path to database for annotation

    Returns:
        DataFrame with significant interactions
    """
    try:
        from fastccc import ccc_utils
    except ImportError:
        raise ImportError("FastCCC not installed.")

    # Get interactions from database if provided
    if database_file_path:
        from fastccc import preprocess
        interactions = preprocess.get_interactions(database_file_path)
        significant_df = ccc_utils.create_significant_interactions_df(pvals, interactions)
    else:
        # Manual extraction
        sig_mask = pvals < pval_threshold
        results = []
        for idx in sig_mask.index:
            for col in sig_mask.columns:
                if sig_mask.loc[idx, col]:
                    results.append({
                        'cell_pair': idx,
                        'interaction_id': col,
                        'pvalue': pvals.loc[idx, col]
                    })
        significant_df = pd.DataFrame(results)

    return significant_df


def analyze_celltype_specific_interactions(
    pvals: pd.DataFrame,
    interactions_strength: pd.DataFrame,
    source_celltype: str,
    target_celltype: str,
    pval_threshold: float = 0.05
) -> pd.DataFrame:
    """Analyze interactions for a specific cell type pair.

    Args:
        pvals: DataFrame with p-values
        interactions_strength: DataFrame with interaction strengths
        source_celltype: Source cell type
        target_celltype: Target cell type
        pval_threshold: P-value threshold

    Returns:
        DataFrame with interactions for the specified cell pair
    """
    cell_pair = f"{source_celltype}|{target_celltype}"

    if cell_pair not in pvals.index:
        raise ValueError(f"Cell pair '{cell_pair}' not found in results")

    # Extract data for this cell pair
    pair_pvals = pvals.loc[cell_pair]
    pair_strength = interactions_strength.loc[cell_pair]

    # Create results DataFrame
    results = pd.DataFrame({
        'interaction_id': pvals.columns,
        'pvalue': pair_pvals.values,
        'strength': pair_strength.values,
        'significant': pair_pvals < pval_threshold
    })

    # Sort by p-value
    results = results.sort_values('pvalue')

    return results


def compare_conditions_fastccc(
    adata_dict: Dict[str, AnnData],
    database_file_path: str,
    groupby: str,
    save_path: str = './fastccc_comparison',
    min_percentile: float = 0.1,
    verbose: bool = True
) -> Dict[str, Any]:
    """Run FastCCC on multiple conditions and compare results.

    Args:
        adata_dict: Dictionary mapping condition names to AnnData objects
        database_file_path: Path to LR interaction database
        groupby: Column name for cell type annotations
        save_path: Directory to save results
        min_percentile: Minimum percentile threshold
        verbose: Whether to print progress

    Returns:
        Dictionary with results for each condition
    """
    os.makedirs(save_path, exist_ok=True)

    all_results = {}

    for condition, adata in adata_dict.items():
        if verbose:
            print(f"\nProcessing condition: {condition}")

        condition_save_path = os.path.join(save_path, condition)

        results = run_fastccc(
            adata,
            database_file_path=database_file_path,
            groupby=groupby,
            save_path=condition_save_path,
            min_percentile=min_percentile,
            verbose=verbose
        )

        all_results[condition] = results

    # Compare significant interactions across conditions
    if verbose:
        print("\nComparing conditions...")

    comparison = compare_interactions_across_conditions(
        all_results,
        pval_threshold=0.05
    )

    all_results['comparison'] = comparison

    return all_results


def compare_interactions_across_conditions(
    results_dict: Dict[str, Dict[str, pd.DataFrame]],
    pval_threshold: float = 0.05
) -> pd.DataFrame:
    """Compare significant interactions across multiple conditions.

    Args:
        results_dict: Dictionary mapping condition names to FastCCC results
        pval_threshold: P-value threshold for significance

    Returns:
        DataFrame with comparison across conditions
    """
    comparison_data = []

    for condition, results in results_dict.items():
        if 'pvals' not in results:
            continue

        pvals = results['pvals']
        sig_mask = pvals < pval_threshold

        # Count significant interactions
        n_sig = sig_mask.sum().sum()
        n_total = pvals.shape[0] * pvals.shape[1]

        comparison_data.append({
            'condition': condition,
            'n_significant': n_sig,
            'n_total': n_total,
            'significance_rate': n_sig / n_total if n_total > 0 else 0
        })

    return pd.DataFrame(comparison_data)


def get_top_interactions(
    interactions_strength: pd.DataFrame,
    pvals: Optional[pd.DataFrame] = None,
    n_top: int = 20,
    by: str = 'strength'
) -> pd.DataFrame:
    """Get top interactions by strength or significance.

    Args:
        interactions_strength: DataFrame with interaction strengths
        pvals: Optional DataFrame with p-values
        n_top: Number of top interactions to return
        by: Metric to use ('strength' or 'significance')

    Returns:
        DataFrame with top interactions
    """
    results = []

    for cell_pair in interactions_strength.index:
        for interaction in interactions_strength.columns:
            result = {
                'cell_pair': cell_pair,
                'interaction': interaction,
                'strength': interactions_strength.loc[cell_pair, interaction]
            }
            if pvals is not None:
                result['pvalue'] = pvals.loc[cell_pair, interaction]
            results.append(result)

    results_df = pd.DataFrame(results)

    if by == 'strength':
        results_df = results_df.nlargest(n_top, 'strength')
    elif by == 'significance' and pvals is not None:
        results_df = results_df.nsmallest(n_top, 'pvalue')

    return results_df


def summarize_interactions_by_cellpair(
    pvals: pd.DataFrame,
    interactions_strength: pd.DataFrame,
    pval_threshold: float = 0.05
) -> pd.DataFrame:
    """Summarize interactions by cell type pair.

    Args:
        pvals: DataFrame with p-values
        interactions_strength: DataFrame with interaction strengths
        pval_threshold: P-value threshold

    Returns:
        DataFrame with summary per cell type pair
    """
    summary = []

    for cell_pair in pvals.index:
        pair_pvals = pvals.loc[cell_pair]
        pair_strength = interactions_strength.loc[cell_pair]

        n_sig = (pair_pvals < pval_threshold).sum()
        n_total = len(pair_pvals)

        summary.append({
            'cell_pair': cell_pair,
            'n_significant': n_sig,
            'n_total': n_total,
            'significance_rate': n_sig / n_total if n_total > 0 else 0,
            'mean_strength': pair_strength.mean(),
            'max_strength': pair_strength.max()
        })

    return pd.DataFrame(summary).sort_values('n_significant', ascending=False)


def run_fastccc_pipeline(
    adata: AnnData,
    database_file_path: str,
    groupby: str,
    output_dir: str = './fastccc_output',
    use_cauchy: bool = True,
    compare_conditions: Optional[Dict[str, AnnData]] = None,
    verbose: bool = True
) -> Dict[str, Any]:
    """Complete FastCCC analysis pipeline.

    Args:
        adata: AnnData object (or main condition if comparing)
        database_file_path: Path to LR interaction database
        groupby: Column name for cell type annotations
        output_dir: Output directory
        use_cauchy: Whether to use Cauchy combination
        compare_conditions: Optional dict of conditions to compare
        verbose: Whether to print progress

    Returns:
        Dictionary with all results
    """
    os.makedirs(output_dir, exist_ok=True)

    results = {}

    # Run main analysis
    if verbose:
        print("Running main FastCCC analysis...")

    if use_cauchy:
        main_results = run_fastccc_cauchy_combined(
            adata,
            database_file_path=database_file_path,
            groupby=groupby,
            save_path=output_dir,
            verbose=verbose
        )
    else:
        main_results = run_fastccc(
            adata,
            database_file_path=database_file_path,
            groupby=groupby,
            save_path=output_dir,
            verbose=verbose
        )

    results['main'] = main_results

    # Compare conditions if provided
    if compare_conditions:
        if verbose:
            print("\nRunning condition comparison...")

        comparison_results = compare_conditions_fastccc(
            compare_conditions,
            database_file_path=database_file_path,
            groupby=groupby,
            save_path=os.path.join(output_dir, 'comparison'),
            verbose=verbose
        )

        results['comparison'] = comparison_results

    if verbose:
        print("\nPipeline complete!")

    return results
