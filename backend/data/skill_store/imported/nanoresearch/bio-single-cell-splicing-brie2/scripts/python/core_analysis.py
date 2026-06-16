"""
Core BRIE2 analysis functions for single-cell splicing analysis.
"""

import os
import sys
import warnings
from pathlib import Path
from typing import List, Optional, Tuple, Union, Dict, Any
import logging

import numpy as np
import pandas as pd
import scanpy as sc
from anndata import AnnData

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_brie_count(
    gff_file: str,
    sam_list_file: Optional[str] = None,
    sam_file: Optional[str] = None,
    barcode_file: Optional[str] = None,
    out_dir: str = "brie_count_output",
    nproc: int = 1,
    event_type: str = "SE",
    mode: str = "smartseq2",
    CB_tag: str = "CB",
    UMI_tag: str = "UR",
    edge_hang: int = 10,
    junc_hang: int = 2,
    verbose: bool = True,
) -> str:
    """
    Run BRIE2 counting to generate cell-by-event count matrices.

    Parameters
    ----------
    gff_file : str
        Path to GFF3 annotation file with splicing events
    sam_list_file : str, optional
        Path to SAM/BAM list file (for Smart-seq2)
        Format: two columns [bam_path, cell_id]
    sam_file : str, optional
        Path to single SAM/BAM file (for droplet data)
    barcode_file : str, optional
        Path to barcode file (for droplet data)
    out_dir : str, default='brie_count_output'
        Output directory
    nproc : int, default=1
        Number of parallel processes
    event_type : str, default='SE'
        Splicing event type ('SE' for skipping exon)
    mode : str, default='smartseq2'
        'smartseq2' or 'droplet'
    CB_tag : str, default='CB'
        Cell barcode tag in BAM (droplet mode)
    UMI_tag : str, default='UR'
        UMI tag in BAM (droplet mode)
    edge_hang : int, default=10
        Bases hanging over exon edge
    junc_hang : int, default=2
        Bases hanging over junction
    verbose : bool, default=True
        Print progress messages

    Returns
    -------
    str : Path to output h5ad file

    Examples
    --------
    >>> # Smart-seq2 mode
    >>> out_file = run_brie_count(
    ...     gff_file='events.gff3',
    ...     sam_list_file='sam_list.tsv',
    ...     out_dir='counts',
    ...     mode='smartseq2',
    ...     nproc=4
    ... )

    >>> # Droplet mode (10x Genomics)
    >>> out_file = run_brie_count(
    ...     gff_file='events.gff3',
    ...     sam_file='aligned.bam',
    ...     barcode_file='barcodes.tsv',
    ...     out_dir='counts',
    ...     mode='droplet',
    ...     nproc=4
    ... )
    """
    try:
        import brie
        from brie.bin.count import smartseq_count, droplet_count
    except ImportError:
        raise ImportError(
            "brie is not installed. Please install with: pip install brie"
        )

    # Validate inputs
    if mode == "smartseq2":
        if sam_list_file is None:
            raise ValueError("sam_list_file is required for smartseq2 mode")
        if not os.path.exists(sam_list_file):
            raise FileNotFoundError(f"SAM list file not found: {sam_list_file}")
    elif mode == "droplet":
        if sam_file is None or barcode_file is None:
            raise ValueError(
                "sam_file and barcode_file are required for droplet mode"
            )
        if not os.path.exists(sam_file):
            raise FileNotFoundError(f"SAM file not found: {sam_file}")
        if not os.path.exists(barcode_file):
            raise FileNotFoundError(f"Barcode file not found: {barcode_file}")
    else:
        raise ValueError(f"Invalid mode: {mode}. Use 'smartseq2' or 'droplet'")

    if not os.path.exists(gff_file):
        raise FileNotFoundError(f"GFF file not found: {gff_file}")

    # Create output directory
    os.makedirs(out_dir, exist_ok=True)

    # Run counting
    if verbose:
        logger.info(f"Running BRIE2 count in {mode} mode...")
        logger.info(f"Output directory: {out_dir}")

    if mode == "smartseq2":
        smartseq_count(
            gff_file=gff_file,
            samList_file=sam_list_file,
            out_dir=out_dir,
            nproc=nproc,
            event_type=event_type,
            verbose=verbose,
            edge_hang=edge_hang,
            junc_hang=junc_hang,
        )
    else:  # droplet
        droplet_count(
            gff_file=gff_file,
            sam_file=sam_file,
            barcode_file=barcode_file,
            out_dir=out_dir,
            nproc=nproc,
            event_type=event_type,
            CB_tag=CB_tag,
            UMI_tag=UMI_tag,
            verbose=verbose,
            edge_hang=edge_hang,
            junc_hang=junc_hang,
        )

    output_file = os.path.join(out_dir, "brie_count.h5ad")

    if not os.path.exists(output_file):
        raise RuntimeError(f"Counting failed. Output file not found: {output_file}")

    if verbose:
        logger.info(f"Counting complete. Output: {output_file}")

    return output_file


def run_brie_quant(
    adata: AnnData,
    cell_features: Optional[np.ndarray] = None,
    gene_features: Optional[np.ndarray] = None,
    cell_feature_names: Optional[List[str]] = None,
    gene_feature_names: Optional[List[str]] = None,
    layer_keys: List[str] = ["isoform1", "isoform2", "ambiguous"],
    LRT_index: Optional[List[int]] = None,
    intercept_mode: str = "gene",
    min_counts: int = 50,
    min_counts_uniq: int = 10,
    min_cells_uniq: int = 30,
    min_MIF_uniq: float = 0.001,
    min_iter: int = 5000,
    max_iter: int = 20000,
    MC_size: int = 1,
    batch_size: int = 500000,
    pseudo_count: float = 0.01,
    base_mode: str = "full",
    verbose: bool = True,
) -> AnnData:
    """
    Run BRIE2 quantification to estimate PSI values and detect differential splicing.

    Parameters
    ----------
    adata : AnnData
        AnnData with count matrices (from brie-count)
    cell_features : np.ndarray, optional
        Cell feature matrix (n_cells × n_features)
    gene_features : np.ndarray, optional
        Gene feature matrix (n_genes × n_features)
    cell_feature_names : list, optional
        Names for cell features
    gene_feature_names : list, optional
        Names for gene features
    layer_keys : list, default=['isoform1', 'isoform2', 'ambiguous']
        Layer names for count matrices
    LRT_index : list, optional
        Feature indices to test with LRT (None=all, []=none)
    intercept_mode : str, default='gene'
        Intercept mode: 'gene', 'cell', or 'None'
    min_counts : int, default=50
        Minimum total counts for gene filtering
    min_counts_uniq : int, default=10
        Minimum unique counts per gene
    min_cells_uniq : int, default=30
        Minimum cells with unique counts
    min_MIF_uniq : float, default=0.001
        Minimum minor isoform frequency
    min_iter : int, default=5000
        Minimum VI iterations
    max_iter : int, default=20000
        Maximum VI iterations
    MC_size : int, default=1
        Monte Carlo sample size
    batch_size : int, default=500000
        Batch size for processing
    pseudo_count : float, default=0.01
        Pseudo count for stability
    base_mode : str, default='full'
        Base model: 'full' or 'null'
    verbose : bool, default=True
        Print progress

    Returns
    -------
    AnnData with PSI values and quantification results

    Examples
    --------
    >>> # Basic quantification
    >>> adata = brie.read_h5ad('counts.h5ad')
    >>> adata_quant = run_brie_quant(adata)

    >>> # With cell features for differential analysis
    >>> cell_features = pd.get_dummies(adata.obs['cell_type']).values
    >>> adata_quant = run_brie_quant(
    ...     adata,
    ...     cell_features=cell_features,
    ...     LRT_index=[0, 1]
    ... )
    """
    try:
        import brie
        from brie.models import fitBRIE
    except ImportError:
        raise ImportError(
            "brie is not installed. Please install with: pip install brie"
        )

    # Validate input
    validate_adata_for_brie(adata, layer_keys=layer_keys)

    # Filter genes
    if verbose:
        logger.info(f"Filtering genes: {adata.n_vars} genes before filtering")

    adata = filter_splicing_data(
        adata,
        min_counts=min_counts,
        min_counts_uniq=min_counts_uniq,
        min_cells_uniq=min_cells_uniq,
        min_MIF_uniq=min_MIF_uniq,
        layer_keys=layer_keys,
        copy=True,
    )

    if verbose:
        logger.info(f"After filtering: {adata.n_vars} genes")

    # Prepare intercept
    intercept = None if intercept_mode.upper() in ["GENE", "CELL"] else 0

    # Determine tau_prior based on data type
    if "unspliced" in layer_keys:
        tau_prior = [1, 1]  # For RNA velocity analysis
    else:
        tau_prior = [3, 27]  # For splicing analysis

    # Run BRIE
    if verbose:
        logger.info("Running BRIE2 quantification...")
        logger.info(f"Parameters: min_iter={min_iter}, max_iter={max_iter}")

    model = fitBRIE(
        adata,
        Xc=cell_features,
        Xg=gene_features,
        LRT_index=LRT_index if LRT_index is not None else [],
        layer_keys=layer_keys,
        intercept=intercept,
        intercept_mode=intercept_mode,
        min_iter=min_iter,
        max_iter=max_iter,
        MC_size=MC_size,
        batch_size=batch_size,
        pseudo_count=pseudo_count,
        base_mode=base_mode,
        tau_prior=tau_prior,
    )

    # Store metadata
    adata.uns["brie_version"] = brie.__version__
    if cell_feature_names is not None:
        adata.uns["Xc_ids"] = cell_feature_names
    if gene_feature_names is not None:
        adata.uns["Xg_ids"] = gene_feature_names

    if verbose:
        logger.info("Quantification complete")

    return adata


def filter_splicing_data(
    adata: AnnData,
    min_counts: int = 50,
    min_counts_uniq: int = 10,
    min_cells_uniq: int = 30,
    min_MIF_uniq: float = 0.001,
    layer_keys: List[str] = ["isoform1", "isoform2"],
    copy: bool = False,
) -> AnnData:
    """
    Filter splicing data based on count thresholds.

    Parameters
    ----------
    adata : AnnData
        Input AnnData
    min_counts : int, default=50
        Minimum total counts
    min_counts_uniq : int, default=10
        Minimum unique counts
    min_cells_uniq : int, default=30
        Minimum cells with unique counts
    min_MIF_uniq : float, default=0.001
        Minimum minor isoform frequency
    layer_keys : list, default=['isoform1', 'isoform2']
        Layer names for filtering
    copy : bool, default=False
        Return a copy

    Returns
    -------
    Filtered AnnData
    """
    try:
        import brie
    except ImportError:
        raise ImportError("brie is not installed")

    if copy:
        adata = adata.copy()

    # Apply BRIE's filtering
    adata = brie.pp.filter_genes(
        adata,
        min_counts=min_counts,
        min_counts_uniq=min_counts_uniq,
        min_cells_uniq=min_cells_uniq,
        min_MIF_uniq=min_MIF_uniq,
        uniq_layers=layer_keys[:2],
        ambg_layers=layer_keys[2:] if len(layer_keys) > 2 else [],
        copy=False,
    )

    return adata


def get_psi_values(
    adata: AnnData,
    events: Optional[List[str]] = None,
    with_confidence: bool = True,
) -> pd.DataFrame:
    """
    Extract PSI values from BRIE results.

    Parameters
    ----------
    adata : AnnData
        BRIE quantified AnnData
    events : list, optional
        Specific events to extract (default: all)
    with_confidence : bool, default=True
        Include confidence intervals

    Returns
    -------
    DataFrame with PSI values
    """
    if events is not None:
        adata = adata[:, events]

    # Get PSI matrix
    psi = adata.X if hasattr(adata.X, "shape") else adata.layers.get("psi", adata.X)

    # Create DataFrame
    df = pd.DataFrame(
        psi,
        index=adata.obs_names,
        columns=adata.var_names,
    )

    if with_confidence and "psi_mean" in adata.varm:
        # Add summary statistics
        stats = pd.DataFrame(
            {
                "mean": adata.varm["psi_mean"].flatten()
                if hasattr(adata.varm["psi_mean"], "flatten")
                else adata.varm["psi_mean"],
                "std": adata.varm["psi_std"].flatten()
                if hasattr(adata.varm["psi_std"], "flatten")
                else adata.varm["psi_std"],
            },
            index=adata.var_names,
        )
        df = df.T.join(stats).T

    return df


def get_significant_events(
    adata: AnnData,
    qval_threshold: float = 0.05,
    sort_by: str = "qval",
) -> pd.DataFrame:
    """
    Get statistically significant differential splicing events.

    Parameters
    ----------
    adata : AnnData
        BRIE quantified AnnData
    qval_threshold : float, default=0.05
        FDR threshold
    sort_by : str, default='qval'
        Column to sort by

    Returns
    -------
    DataFrame of significant events
    """
    try:
        import brie
    except ImportError:
        raise ImportError("brie is not installed")

    # Get results table
    df = brie.io.dump_results(adata)

    # Filter by q-value
    if "qval" in df.columns:
        significant = df[df["qval"] < qval_threshold].copy()
        significant = significant.sort_values(sort_by)
    else:
        warnings.warn("No qval column found. Returning all results.")
        significant = df

    return significant


def compare_cell_groups(
    adata: AnnData,
    group_key: str,
    group1: str,
    group2: str,
    events: Optional[List[str]] = None,
) -> pd.DataFrame:
    """
    Compare PSI values between two cell groups.

    Parameters
    ----------
    adata : AnnData
        BRIE quantified AnnData
    group_key : str
        Column in adata.obs for grouping
    group1 : str
        First group name
    group2 : str
        Second group name
    events : list, optional
        Specific events to compare

    Returns
    -------
    DataFrame with comparison statistics
    """
    from scipy import stats

    if group_key not in adata.obs.columns:
        raise ValueError(f"Group key '{group_key}' not found in adata.obs")

    # Get cells in each group
    mask1 = adata.obs[group_key] == group1
    mask2 = adata.obs[group_key] == group2

    if events is not None:
        adata = adata[:, events]

    # Get PSI values
    psi1 = adata[mask1].X
    psi2 = adata[mask2].X

    # Calculate statistics
    results = []
    for i, event in enumerate(adata.var_names):
        p1 = psi1[:, i] if psi1.ndim > 1 else psi1[i]
        p2 = psi2[:, i] if psi2.ndim > 1 else psi2[i]

        # Remove NaN values
        p1 = p1[~np.isnan(p1)]
        p2 = p2[~np.isnan(p2)]

        if len(p1) > 0 and len(p2) > 0:
            mean1, mean2 = np.mean(p1), np.mean(p2)
            std1, std2 = np.std(p1), np.std(p2)

            # T-test
            if len(p1) > 1 and len(p2) > 1:
                t_stat, pval = stats.ttest_ind(p1, p2)
            else:
                t_stat, pval = np.nan, np.nan

            results.append(
                {
                    "event": event,
                    f"{group1}_mean": mean1,
                    f"{group1}_std": std1,
                    f"{group1}_n": len(p1),
                    f"{group2}_mean": mean2,
                    f"{group2}_std": std2,
                    f"{group2}_n": len(p2),
                    "delta_psi": mean1 - mean2,
                    "t_statistic": t_stat,
                    "pvalue": pval,
                }
            )

    df = pd.DataFrame(results)

    # FDR correction
    if "pvalue" in df.columns and len(df) > 0:
        from statsmodels.stats.multitest import multipletests

        pvals = df["pvalue"].dropna().values
        if len(pvals) > 0:
            _, qvals, _, _ = multipletests(pvals, method="fdr_bh")
            df.loc[df["pvalue"].notna(), "qvalue"] = qvals

    return df


def validate_adata_for_brie(
    adata: AnnData,
    layer_keys: List[str] = ["isoform1", "isoform2", "ambiguous"],
) -> bool:
    """
    Validate AnnData has required structure for BRIE analysis.

    Parameters
    ----------
    adata : AnnData
        Input AnnData
    layer_keys : list
        Required layer names

    Returns
    -------
    bool : True if valid

    Raises
    ------
    ValueError if validation fails
    """
    # Check layers
    for key in layer_keys:
        if key not in adata.layers:
            raise ValueError(f"Required layer '{key}' not found in adata.layers")

    # Check dimensions match
    shape = adata.layers[layer_keys[0]].shape
    for key in layer_keys:
        if adata.layers[key].shape != shape:
            raise ValueError(f"Layer '{key}' has mismatched shape")

    # Check for required var columns (gene info)
    if "GeneID" not in adata.var.columns and adata.var.index.name != "GeneID":
        warnings.warn("GeneID not found in adata.var")

    return True
