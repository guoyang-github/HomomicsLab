"""
Utility Functions for pertpy
=============================

Helper functions for data validation, result processing, and analysis utilities.
"""

import numpy as np
import pandas as pd
from typing import Optional, Union, List, Dict, Tuple, Any
import warnings


def get_perturbation_summary(
    adata,
    perturbation_col: str = "perturbation"
) -> pd.DataFrame:
    """
    Get summary statistics for each perturbation.

    Parameters
    ----------
    adata : AnnData
        Annotated data matrix
    perturbation_col : str
        Column with perturbation labels

    Returns
    -------
    pd.DataFrame
        Summary statistics per perturbation
    """
    if perturbation_col not in adata.obs.columns:
        raise ValueError(f"Column '{perturbation_col}' not found")

    summary = adata.obs[perturbation_col].value_counts().to_frame(name='cell_count')
    summary['proportion'] = summary['cell_count'] / len(adata)

    # Add mean expression per perturbation (for first 10 genes as example)
    for pert in summary.index[:5]:
        mask = adata.obs[perturbation_col] == pert
        summary.loc[pert, 'mean_total_expression'] = np.mean(adata.X[mask].sum(axis=1))

    return summary


def find_high_confidence_perturbations(
    distance_df: pd.DataFrame,
    control: str,
    threshold_percentile: float = 90
) -> List[str]:
    """
    Identify perturbations with high distance from control.

    Parameters
    ----------
    distance_df : pd.DataFrame
        Distance matrix
    control : str
        Control perturbation name
    threshold_percentile : float
        Percentile threshold for high confidence

    Returns
    -------
    list
        List of high confidence perturbations
    """
    if control not in distance_df.index:
        raise ValueError(f"Control '{control}' not found in distance matrix")

    control_distances = distance_df.loc[control].drop(control)
    threshold = np.percentile(control_distances, threshold_percentile)

    high_conf = control_distances[control_distances >= threshold].index.tolist()

    print(f"High confidence perturbations (distance >= {threshold:.2f}):")
    for pert in high_conf:
        print(f"  {pert}: {control_distances[pert]:.2f}")

    return high_conf


def merge_perturbation_results(
    adata,
    results_dict: Dict[str, pd.DataFrame],
    key_col: str = "perturbation"
) -> pd.DataFrame:
    """
    Merge multiple perturbation results into single DataFrame.

    Parameters
    ----------
    adata : AnnData
        Annotated data matrix
    results_dict : dict
        Dictionary of results DataFrames
    key_col : str
        Key column for merging

    Returns
    -------
    pd.DataFrame
        Merged results
    """
    merged = None

    for name, df in results_dict.items():
        df_copy = df.copy()
        df_copy.columns = [f"{name}_{col}" for col in df_copy.columns]

        if merged is None:
            merged = df_copy
        else:
            merged = merged.join(df_copy, how='outer')

    return merged


def export_de_results(
    de_results: Dict[str, pd.DataFrame],
    output_prefix: str = "de_results",
    significant_only: bool = False,
    pval_threshold: float = 0.05
) -> None:
    """
    Export differential expression results to CSV files.

    Parameters
    ----------
    de_results : dict
        Dictionary of DE results per perturbation
    output_prefix : str
        Prefix for output files
    significant_only : bool
        Whether to export only significant genes
    pval_threshold : float
        P-value threshold for significance
    """
    for perturbation, df in de_results.items():
        if significant_only:
            # Assuming padj column exists
            if 'padj' in df.columns:
                df = df[df['padj'] < pval_threshold]

        safe_name = perturbation.replace('/', '_').replace(' ', '_')
        filename = f"{output_prefix}_{safe_name}.csv"
        df.to_csv(filename)
        print(f"Exported {perturbation}: {len(df)} genes to {filename}")


def get_top_de_genes(
    de_results: pd.DataFrame,
    n_genes: int = 10,
    sort_by: str = "log2FoldChange",
    ascending: bool = False
) -> pd.DataFrame:
    """
    Get top differentially expressed genes.

    Parameters
    ----------
    de_results : pd.DataFrame
        DE results DataFrame
    n_genes : int
        Number of top genes to return
    sort_by : str
        Column to sort by
    ascending : bool
        Whether to sort in ascending order

    Returns
    -------
    pd.DataFrame
        Top DE genes
    """
    return de_results.sort_values(by=sort_by, ascending=ascending).head(n_genes)


def validate_de_results(
    de_results: pd.DataFrame,
    expected_columns: List[str] = None
) -> bool:
    """
    Validate differential expression results.

    Parameters
    ----------
    de_results : pd.DataFrame
        DE results DataFrame
    expected_columns : list, optional
        Expected columns

    Returns
    -------
    bool
        True if valid
    """
    if expected_columns is None:
        expected_columns = ['log2FoldChange', 'padj']

    missing = set(expected_columns) - set(de_results.columns)
    if missing:
        raise ValueError(f"Missing columns: {missing}")

    # Check for NaN values
    nan_counts = de_results.isna().sum()
    if nan_counts.any():
        warnings.warn(f"NaN values found in columns: {nan_counts[nan_counts > 0].to_dict()}")

    # Check p-value range
    if 'padj' in de_results.columns:
        if not de_results['padj'].between(0, 1).all():
            warnings.warn("Some adjusted p-values are outside [0, 1] range")

    return True


def compare_perturbation_effects(
    de_results1: pd.DataFrame,
    de_results2: pd.DataFrame,
    gene_col: str = "gene",
    lfc_col: str = "log2FoldChange",
    pval_col: str = "padj"
) -> pd.DataFrame:
    """
    Compare effects of two perturbations.

    Parameters
    ----------
    de_results1 : pd.DataFrame
        First perturbation DE results
    de_results2 : pd.DataFrame
        Second perturbation DE results
    gene_col : str
        Gene column name
    lfc_col : str
        Log fold change column name
    pval_col : str
        P-value column name

    Returns
    -------
    pd.DataFrame
        Comparison results
    """
    # Merge on gene
    merged = pd.merge(
        de_results1[[gene_col, lfc_col, pval_col]].rename(columns={lfc_col: 'lfc1', pval_col: 'pval1'}),
        de_results2[[gene_col, lfc_col, pval_col]].rename(columns={lfc_col: 'lfc2', pval_col: 'pval2'}),
        on=gene_col,
        how='outer'
    )

    # Calculate correlation
    valid_genes = merged.dropna()
    correlation = np.corrcoef(valid_genes['lfc1'], valid_genes['lfc2'])[0, 1]

    print(f"LogFC correlation between perturbations: {correlation:.3f}")

    return merged


def summarize_augment_results(
    adata,
    key: str = "augur_results"
) -> Dict[str, Any]:
    """
    Summarize Augur analysis results.

    Parameters
    ----------
    adata : AnnData
        AnnData with Augur results
    key : str
        Key in .uns

    Returns
    -------
    dict
        Summary statistics
    """
    if key not in adata.uns:
        raise ValueError(f"Augur results not found in .uns['{key}']")

    results = adata.uns[key]

    summary = {
        'mean_auc': results['AUC'].mean() if 'AUC' in results else None,
        'median_auc': results['AUC'].median() if 'AUC' in results else None,
        'min_auc': results['AUC'].min() if 'AUC' in results else None,
        'max_auc': results['AUC'].max() if 'AUC' in results else None,
    }

    return summary


def create_perturbation_report(
    adata,
    perturbation_col: str = "perturbation",
    output_file: Optional[str] = None
) -> str:
    """
    Create comprehensive perturbation analysis report.

    Parameters
    ----------
    adata : AnnData
        Annotated data matrix
    perturbation_col : str
        Column with perturbation labels
    output_file : str, optional
        Output file path

    Returns
    -------
    str
        Report text
    """
    lines = [
        "Perturbation Analysis Report",
        "=" * 40,
        "",
        f"Analysis Date: {pd.Timestamp.now()}",
        f"Total Cells: {adata.n_obs}",
        f"Total Genes: {adata.n_vars}",
        "",
        "Perturbation Summary:",
    ]

    summary = get_perturbation_summary(adata, perturbation_col)
    lines.append(summary.to_string())

    # Check for analysis results
    if 'augur_results' in adata.uns:
        lines.extend(["", "Augur Results:", str(adata.uns['augur_results'].head())])

    if 'mixscape_class' in adata.obs:
        lines.extend(["", "Mixscape Classification:", str(adata.obs['mixscape_class'].value_counts())])

    report = "\n".join(lines)

    if output_file:
        with open(output_file, 'w') as f:
            f.write(report)
        print(f"Report saved to {output_file}")

    return report


def check_dependencies() -> bool:
    """
    Check if required dependencies are installed.

    Returns
    -------
    bool
        True if all dependencies are available
    """
    required = ['pertpy', 'scanpy', 'anndata']
    optional = ['seaborn', 'pydeseq2']

    missing = []
    for pkg in required:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)

    if missing:
        raise ImportError(f"Missing required packages: {missing}. Install with: pip install pertpy")

    missing_opt = []
    for pkg in optional:
        try:
            __import__(pkg)
        except ImportError:
            missing_opt.append(pkg)

    if missing_opt:
        warnings.warn(f"Optional packages not installed: {missing_opt}")

    return True
