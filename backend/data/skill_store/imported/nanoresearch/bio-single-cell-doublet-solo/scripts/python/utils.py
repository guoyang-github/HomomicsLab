"""
Utility Functions for SOLO Doublet Detection

Helper functions for data validation, processing, and analysis.

Author: Yang Guo
Date: 2026-04-03
"""

import numpy as np
import pandas as pd
import scanpy as sc
from typing import Optional, List, Dict, Tuple, Union
from scipy.sparse import issparse

#==============================================================================
# Data Validation
#==============================================================================

def validate_adata_for_solo(
    adata: sc.AnnData,
    require_raw: bool = True,
    min_cells: int = 100,
    min_genes: int = 100
) -> bool:
    """
    Validate AnnData object for SOLO analysis.

    Parameters
    ----------
    adata : sc.AnnData
        Input data
    require_raw : bool, default=True
        Require raw count data
    min_cells : int, default=100
        Minimum number of cells
    min_genes : int, default=100
        Minimum number of genes

    Returns
    -------
    bool
        True if valid
    """
    if not isinstance(adata, sc.AnnData):
        raise TypeError("Input must be an AnnData object")

    if adata.n_obs < min_cells:
        raise ValueError(f"Too few cells: {adata.n_obs} (minimum {min_cells})")

    if adata.n_vars < min_genes:
        raise ValueError(f"Too few genes: {adata.n_vars} (minimum {min_genes})")

    # Check for raw counts
    if require_raw:
        # Check if data looks like raw counts (integers, small values)
        if issparse(adata.X):
            max_val = adata.X.max()
            # Sample check for integer-like values to avoid memory issues on large matrices
            data = adata.X.data
            if len(data) > 1_000_000:
                sample_idx = np.random.choice(len(data), 1_000_000, replace=False)
                is_integer = np.all(data[sample_idx] == data[sample_idx].astype(int))
            else:
                is_integer = np.all(data == data.astype(int))
        else:
            max_val = adata.X.max()
            is_integer = np.all(adata.X == adata.X.astype(int))

        if max_val < 20 or not is_integer:
            import warnings
            warnings.warn(
                "Data may not be raw counts. SOLO works best with raw UMI counts. "
                "If data is log-normalized, consider using raw counts instead.",
                UserWarning
            )

    return True


#==============================================================================
# Data Preprocessing
#==============================================================================

def preprocess_for_solo(
    adata: sc.AnnData,
    min_genes: int = 200,
    min_cells: int = 3,
    max_genes: Optional[int] = None,
    max_counts: Optional[int] = None,
    mt_threshold: Optional[float] = None,
    inplace: bool = False
) -> sc.AnnData:
    """
    Preprocess data for SOLO analysis.

    Parameters
    ----------
    adata : sc.AnnData
        Raw data
    min_genes : int, default=200
        Minimum genes per cell
    min_cells : int, default=3
        Minimum cells per gene
    max_genes : Optional[int], default=None
        Maximum genes per cell (QC filter)
    max_counts : Optional[int], default=None
        Maximum counts per cell (QC filter)
    mt_threshold : Optional[float], default=None
        Maximum mitochondrial percentage
    inplace : bool, default=False
        Process in place

    Returns
    -------
    sc.AnnData
        Preprocessed data
    """
    if not inplace:
        adata = adata.copy()

    # Basic filtering
    sc.pp.filter_cells(adata, min_genes=min_genes)
    sc.pp.filter_genes(adata, min_cells=min_cells)

    # Calculate QC metrics
    # Support both human (MT-) and mouse (mt-) mitochondrial gene naming
    adata.var['mt'] = (
        adata.var_names.str.startswith('MT-') |
        adata.var_names.str.startswith('mt-')
    )
    sc.pp.calculate_qc_metrics(adata, qc_vars=['mt'], percent_top=None, log1p=False, inplace=True)

    # Additional QC filters
    if max_genes is not None:
        adata = adata[adata.obs['n_genes_by_counts'] < max_genes]

    if max_counts is not None:
        adata = adata[adata.obs['total_counts'] < max_counts]

    if mt_threshold is not None:
        adata = adata[adata.obs['pct_counts_mt'] < mt_threshold]

    print(f"Preprocessed data: {adata.n_obs} cells, {adata.n_vars} genes")

    return adata


def subsample_data(
    adata: sc.AnnData,
    n_obs: Optional[int] = None,
    fraction: Optional[float] = None,
    random_seed: int = 42
) -> sc.AnnData:
    """
    Subsample data for faster testing.

    Parameters
    ----------
    adata : sc.AnnData
        Input data
    n_obs : Optional[int], default=None
        Number of cells to keep
    fraction : Optional[float], default=None
        Fraction of cells to keep
    random_seed : int, default=42
        Random seed

    Returns
    -------
    sc.AnnData
        Subsampled data
    """
    np.random.seed(random_seed)

    if n_obs is not None:
        n_obs = min(n_obs, adata.n_obs)
        indices = np.random.choice(adata.n_obs, n_obs, replace=False)
    elif fraction is not None:
        n_obs = int(adata.n_obs * fraction)
        indices = np.random.choice(adata.n_obs, n_obs, replace=False)
    else:
        return adata

    return adata[indices].copy()


#==============================================================================
# Threshold Optimization
#==============================================================================

def estimate_optimal_threshold(
    predictions: pd.DataFrame,
    expected_doublet_rate: Optional[float] = None,
    method: str = 'otsu'
) -> float:
    """
    Estimate optimal doublet threshold.

    Parameters
    ----------
    predictions : pd.DataFrame
        SOLO predictions
    expected_doublet_rate : Optional[float], default=None
        Expected doublet rate (if known from 10x/technical specs)
    method : str, default='otsu'
        Method for threshold estimation ('otsu', 'knee', 'quantile')

    Returns
    -------
    float
        Estimated threshold
    """
    scores = predictions['doublet'].values

    if method == 'otsu':
        try:
            from skimage.filters import threshold_otsu
            threshold = threshold_otsu(scores)
        except ImportError:
            # Fallback to simple quantile-based method
            threshold = np.percentile(scores, 90)

    elif method == 'knee':
        try:
            from kneed import KneeLocator
            sorted_scores = np.sort(scores)
            x = np.arange(len(sorted_scores))
            knee = KneeLocator(x, sorted_scores, curve='convex', direction='increasing')
            threshold = sorted_scores[knee.knee] if knee.knee else 0.5
        except ImportError:
            threshold = 0.5

    elif method == 'quantile':
        if expected_doublet_rate:
            threshold = np.percentile(scores, (1 - expected_doublet_rate) * 100)
        else:
            threshold = np.percentile(scores, 90)

    else:
        threshold = 0.5

    print(f"Estimated threshold: {threshold:.3f}")
    return threshold


def optimize_threshold_range(
    predictions: pd.DataFrame,
    thresholds: List[float] = None
) -> pd.DataFrame:
    """
    Evaluate multiple thresholds and return summary statistics.

    Parameters
    ----------
    predictions : pd.DataFrame
        SOLO predictions
    thresholds : List[float], default=None
        Thresholds to evaluate (default: [0.3, 0.4, 0.5, 0.6, 0.7])

    Returns
    -------
    pd.DataFrame
        Summary statistics for each threshold
    """
    if thresholds is None:
        thresholds = [0.3, 0.4, 0.5, 0.6, 0.7]

    results = []
    for thresh in thresholds:
        n_doublets = (predictions['doublet'] > thresh).sum()
        doublet_rate = n_doublets / len(predictions) * 100

        results.append({
            'threshold': thresh,
            'n_doublets': n_doublets,
            'doublet_rate_%': doublet_rate
        })

    return pd.DataFrame(results)


#==============================================================================
# Doublet Rate Estimation
#==============================================================================

def estimate_expected_doublet_rate(
    n_cells: int,
    method: str = '10x'
) -> float:
    """
    Estimate expected doublet rate based on cell loading.

    Parameters
    ----------
    n_cells : int
        Number of recovered cells
    method : str, default='10x'
        Method/platform ('10x', 'dropseq', 'general')

    Returns
    -------
    float
        Expected doublet rate
    """
    if method == '10x':
        # Based on 10x Genomics documentation
        # Doublet rate ≈ 0.8% per 1,000 cells
        rate = 0.008 * (n_cells / 1000)
    elif method == 'dropseq':
        # Drop-seq typically has lower doublet rates
        rate = 0.005 * (n_cells / 1000)
    else:
        # General estimate
        rate = 0.01 * (n_cells / 1000)

    # Cap at reasonable maximum
    rate = min(rate, 0.5)

    return rate


#==============================================================================
# Comparison with Other Methods
#==============================================================================

def compare_predictions(
    solo_predictions: pd.DataFrame,
    other_predictions: pd.DataFrame,
    other_name: str = 'other',
    solo_threshold: float = 0.5,
    other_threshold: float = 0.5
) -> Dict[str, any]:
    """
    Compare SOLO predictions with another doublet detection method.

    Parameters
    ----------
    solo_predictions : pd.DataFrame
        SOLO predictions
    other_predictions : pd.DataFrame
        Other method's predictions
    other_name : str, default='other'
        Name of other method
    solo_threshold : float, default=0.5
        Threshold for SOLO
    other_threshold : float, default=0.5
        Threshold for other method

    Returns
    -------
    Dict
        Comparison metrics
    """
    # Get binary predictions
    solo_binary = (solo_predictions['doublet'] > solo_threshold).astype(int)

    if 'prediction' in other_predictions.columns:
        other_pred = other_predictions['prediction']
        if other_pred.dtype == bool:
            other_binary = other_pred.astype(int)
        elif other_pred.dtype == object:
            other_binary = (other_pred == 'doublet').astype(int)
        else:
            other_binary = (other_pred > 0).astype(int)
    else:
        other_binary = (other_predictions.iloc[:, 0] > other_threshold).astype(int)

    # Calculate agreement
    agreement = (solo_binary == other_binary).mean()

    # Confusion matrix
    tp = ((solo_binary == 1) & (other_binary == 1)).sum()
    tn = ((solo_binary == 0) & (other_binary == 0)).sum()
    fp = ((solo_binary == 1) & (other_binary == 0)).sum()
    fn = ((solo_binary == 0) & (other_binary == 1)).sum()

    results = {
        'agreement': agreement,
        'confusion_matrix': {
            'true_positives': int(tp),
            'true_negatives': int(tn),
            'false_positives': int(fp),
            'false_negatives': int(fn)
        },
        'solo_only': int(fp),
        f'{other_name}_only': int(fn),
        'both_doublet': int(tp),
        'both_singlet': int(tn)
    }

    return results


def ensemble_doublet_calls(
    predictions_dict: Dict[str, pd.DataFrame],
    weights: Optional[Dict[str, float]] = None,
    threshold: float = 0.5
) -> pd.DataFrame:
    """
    Create ensemble doublet calls from multiple methods.

    Parameters
    ----------
    predictions_dict : Dict[str, pd.DataFrame]
        Dictionary mapping method names to predictions
    weights : Optional[Dict[str, float]], default=None
        Weights for each method
    threshold : float, default=0.5
        Threshold for ensemble call

    Returns
    -------
    pd.DataFrame
        Ensemble predictions
    """
    if weights is None:
        weights = {k: 1.0 for k in predictions_dict.keys()}

    # Normalize weights
    total_weight = sum(weights.values())
    weights = {k: v / total_weight for k, v in weights.items()}

    # Calculate weighted ensemble score
    ensemble_score = np.zeros(len(list(predictions_dict.values())[0]))

    for method, preds in predictions_dict.items():
        if 'doublet' in preds.columns:
            scores = preds['doublet'].values
        else:
            scores = preds.iloc[:, 0].values
        ensemble_score += scores * weights[method]

    # Create ensemble predictions
    is_doublet = ensemble_score > threshold
    ensemble_preds = pd.DataFrame({
        'ensemble_score': ensemble_score,
        'ensemble_prediction': is_doublet.astype(int),
        'ensemble_label': np.where(is_doublet, 'doublet', 'singlet')
    })

    return ensemble_preds


#==============================================================================
# Result Processing
#==============================================================================

def merge_predictions_with_adata(
    adata: sc.AnnData,
    predictions: pd.DataFrame,
    prefix: str = 'solo'
) -> sc.AnnData:
    """
    Merge SOLO predictions with AnnData object.

    Parameters
    ----------
    adata : sc.AnnData
        Data object
    predictions : pd.DataFrame
        SOLO predictions
    prefix : str, default='solo'
        Prefix for column names

    Returns
    -------
    sc.AnnData
        Updated AnnData
    """
    adata = adata.copy()

    # Ensure index alignment
    if not all(predictions.index == adata.obs_names):
        predictions = predictions.reindex(adata.obs_names)

    # Add columns
    if 'doublet' in predictions.columns:
        adata.obs[f'{prefix}_doublet_score'] = predictions['doublet']
    if 'singlet' in predictions.columns:
        adata.obs[f'{prefix}_singlet_score'] = predictions['singlet']
    if 'prediction_label' in predictions.columns:
        adata.obs[f'{prefix}_prediction'] = predictions['prediction_label']
    elif 'prediction' in predictions.columns:
        pred_col = predictions['prediction']
        if pred_col.dtype == object:
            adata.obs[f'{prefix}_prediction'] = pred_col
        elif pred_col.dtype == bool:
            adata.obs[f'{prefix}_prediction'] = pred_col.map({True: 'doublet', False: 'singlet'})
        else:
            adata.obs[f'{prefix}_prediction'] = (pred_col > 0).map({True: 'doublet', False: 'singlet'})

    return adata


#==============================================================================
# Export Helpers
#==============================================================================

def create_summary_report(
    predictions: pd.DataFrame,
    threshold: float = 0.5,
    output_path: Optional[str] = None
) -> str:
    """
    Create a text summary report of doublet detection.

    Parameters
    ----------
    predictions : pd.DataFrame
        SOLO predictions
    threshold : float, default=0.5
        Threshold used
    output_path : Optional[str], default=None
        Path to save report

    Returns
    -------
    str
        Report text
    """
    n_total = len(predictions)
    n_doublets = (predictions['doublet'] > threshold).sum()
    n_singlets = n_total - n_doublets
    doublet_rate = n_doublets / n_total * 100

    report = f"""
SOLO Doublet Detection Report
==============================

Parameters
----------
Threshold: {threshold}

Results
-------
Total cells analyzed: {n_total:,}
Predicted singlets: {n_singlets:,} ({100 - doublet_rate:.2f}%)
Predicted doublets: {n_doublets:,} ({doublet_rate:.2f}%)

Score Statistics
----------------
Mean doublet score: {predictions['doublet'].mean():.4f}
Median doublet score: {predictions['doublet'].median():.4f}
Min doublet score: {predictions['doublet'].min():.4f}
Max doublet score: {predictions['doublet'].max():.4f}
Std doublet score: {predictions['doublet'].std():.4f}

Interpretation
--------------
A doublet rate of {doublet_rate:.1f}% is {'typical' if 0.05 < doublet_rate/100 < 0.3 else 'unusual'} for single-cell RNA-seq data.
Expected doublet rates from 10x Genomics range from ~2-8% depending on cell loading.
"""

    if output_path:
        with open(output_path, 'w') as f:
            f.write(report)
        print(f"Report saved to {output_path}")

    return report