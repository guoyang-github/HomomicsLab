"""
infercnvpy Analysis Module

A comprehensive wrapper for infercnvpy with utilities for CNV inference
from single-cell transcriptomics data.

Author: Yang Guo
Date: 2026-04-03
Version: 1.0.0
"""

import logging
from pathlib import Path
from typing import List, Optional, Union, Dict, Tuple

import numpy as np
import pandas as pd
import scanpy as sc
import scipy.sparse as sp
from anndata import AnnData

# Optional import for infercnvpy
try:
    import infercnvpy as cnv
    INFERCNVPY_AVAILABLE = True
except ImportError:
    INFERCNVPY_AVAILABLE = False


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def read_gtf_positions(
    gtf_file: Union[str, Path],
    gene_id_attribute: str = "gene_name",
    feature_type: str = "gene"
) -> pd.DataFrame:
    """
    Read gene positions from GTF/GFF file.

    Parameters
    ----------
    gtf_file : Path
        Path to GTF/GFF annotation file
    gene_id_attribute : str
        Attribute to use as gene identifier (default: "gene_name")
    feature_type : str
        Feature type to extract (default: "gene")

    Returns
    -------
    pd.DataFrame
        DataFrame with columns: gene_name, chromosome, start, end

    Examples
    --------
    >>> gene_pos = read_gtf_positions("gencode.v38.annotation.gtf")
    >>> print(gene_pos.head())
          gene_name chromosome    start      end
    0       TP53       chr17  7661779  7687538
    1       MYC        chr8   1277356  1280304
    """
    if not INFERCNVPY_AVAILABLE:
        raise ImportError("infercnvpy not installed. Install with: pip install infercnvpy")

    logger.info(f"Reading gene positions from {gtf_file}")

    try:
        gene_positions = cnv.io.genomic_position_from_gtf(
            gtf_file,
            gene_id_attribute=gene_id_attribute,
            feature_type=feature_type
        )
        logger.info(f"Loaded {len(gene_positions)} gene positions")
        return gene_positions
    except Exception as e:
        logger.error(f"Failed to read GTF file: {e}")
        raise


def add_gene_positions(
    adata: AnnData,
    gene_positions: Optional[pd.DataFrame] = None,
    gtf_file: Optional[Path] = None,
    inplace: bool = True
) -> Optional[AnnData]:
    """
    Add genomic position annotations to AnnData.var.

    Parameters
    ----------
    adata : AnnData
        AnnData object with gene expression
    gene_positions : pd.DataFrame, optional
        DataFrame with gene positions (from read_gtf_positions)
    gtf_file : Path, optional
        Path to GTF file (alternative to gene_positions)
    inplace : bool
        If True, modify adata in place; otherwise return modified copy

    Returns
    -------
    AnnData
        Modified AnnData with chromosome, start, end columns in .var.
        Always returns adata regardless of inplace (deviates from scanpy
        convention to prevent accidental None assignments).

    Raises
    ------
    ValueError
        If neither gene_positions nor gtf_file is provided, or if
        gene_positions is missing required columns

    Examples
    --------
    >>> # From pre-loaded positions
    >>> gene_pos = read_gtf_positions("gencode.v38.annotation.gtf")
    >>> adata = add_gene_positions(adata, gene_positions=gene_pos)

    >>> # Directly from GTF file
    >>> adata = add_gene_positions(adata, gtf_file="gencode.v38.annotation.gtf")
    """
    if not INFERCNVPY_AVAILABLE:
        raise ImportError("infercnvpy not installed")

    if gene_positions is None and gtf_file is None:
        raise ValueError("Either gene_positions or gtf_file must be provided")

    if gene_positions is None:
        gene_positions = read_gtf_positions(gtf_file)

    # Validate gene_positions DataFrame has required columns
    required_cols = {"chromosome", "start", "end"}
    missing_cols = required_cols - set(gene_positions.columns)
    if missing_cols:
        raise ValueError(
            f"gene_positions is missing required columns: {sorted(missing_cols)}. "
            f"Expected columns: {sorted(required_cols)}. "
            f"Actual columns: {list(gene_positions.columns)}"
        )

    if not inplace:
        adata = adata.copy()

    logger.info("Adding gene positions to AnnData.var")

    # Ensure gene names match
    common_genes = adata.var_names.intersection(gene_positions.index)
    logger.info(f"Matched {len(common_genes)} / {len(adata.var_names)} genes")

    if len(common_genes) < len(adata.var_names) * 0.5:
        logger.warning(
            f"Low gene overlap ({len(common_genes)}/{len(adata.var_names)}). "
            "Check if gene names match between AnnData and GTF."
        )

    # Add position columns (safe reindex to handle missing genes)
    pos_reindexed = gene_positions.reindex(adata.var_names)
    adata.var["chromosome"] = pos_reindexed["chromosome"].values
    adata.var["start"] = pos_reindexed["start"].values
    adata.var["end"] = pos_reindexed["end"].values

    # Validate
    missing_pos = adata.var["chromosome"].isna().sum()
    if missing_pos > 0:
        logger.warning(f"{missing_pos} genes do not have position information")

    logger.info("Gene positions added successfully")

    return adata


def run_infercnv_pipeline(
    adata: AnnData,
    reference_key: str,
    reference_cat: Union[str, List[str]],
    window_size: int = 100,
    step: int = 10,
    lfc_clip: float = 3.0,
    dynamic_threshold: float = 1.5,
    exclude_chromosomes: Tuple[str, ...] = ("chrX", "chrY"),
    chunksize: int = 5000,
    n_jobs: int = -1,
    key_added: str = "cnv",
    calculate_gene_values: bool = False,
    layer: Optional[str] = None,
    verbose: bool = True
) -> None:
    """
    Run complete CNV inference pipeline.

    This is the main entry point for CNV analysis, wrapping infercnvpy's
    infercnv function with sensible defaults and progress logging.

    Parameters
    ----------
    adata : AnnData
        AnnData object with gene expression and position annotations
    reference_key : str
        Column name in adata.obs with cell type annotations
    reference_cat : str or List[str]
        Value(s) in reference_key indicating normal/reference cells
    window_size : int
        Number of genes in running window (default: 100)
    step : int
        Step size for sliding window (default: 10)
    lfc_clip : float
        Clip log fold changes at this value (default: 3.0)
    dynamic_threshold : float
        Multiplier for stddev-based noise filtering (default: 1.5)
    exclude_chromosomes : Tuple[str, ...]
        Chromosomes to exclude (default: ("chrX", "chrY"))
    chunksize : int
        Process cells in chunks for memory efficiency (default: 5000)
    n_jobs : int
        Number of parallel jobs (-1 = all cores, default: -1)
    key_added : str
        Key for storing results in adata (default: "cnv")
    calculate_gene_values : bool
        Calculate per-gene CNV values (memory intensive, default: False)
    layer : str, optional
        Layer to use instead of adata.X
    verbose : bool
        Print progress messages

    Returns
    -------
    None
        Results stored in adata.obsm[f"X_{key_added}"] and adata.uns[key_added]

    Notes
    -----
    - Requires chromosome, start, end columns in adata.var
    - Reference cells are used for baseline expression correction
    - Results are log-fold changes relative to reference

    Examples
    --------
    >>> # Basic usage with normal immune cells as reference
    >>> run_infercnv_pipeline(
    ...     adata,
    ...     reference_key="cell_type",
    ...     reference_cat=["T_cell", "B_cell", "Macrophage"]
    ... )

    >>> # With custom parameters
    >>> run_infercnv_pipeline(
    ...     adata,
    ...     reference_key="sample",
    ...     reference_cat="normal_tissue",
    ...     window_size=50,
    ...     step=5,
    ...     key_added="cnv_high_res"
    ... )
    """
    if not INFERCNVPY_AVAILABLE:
        raise ImportError("infercnvpy not installed. Install with: pip install infercnvpy")

    if verbose:
        logger.info("=" * 60)
        logger.info("Starting CNV Inference Pipeline")
        logger.info("=" * 60)
        logger.info(f"AnnData shape: {adata.shape}")
        logger.info(f"Reference: {reference_key} = {reference_cat}")
        logger.info(f"Window size: {window_size}, Step: {step}")

    # Validate input
    if not all(col in adata.var.columns for col in ["chromosome", "start", "end"]):
        raise ValueError(
            "Gene positions not found in adata.var. "
            "Run add_gene_positions() first."
        )

    # Validate reference categories exist in data
    ref_cats = [reference_cat] if isinstance(reference_cat, str) else reference_cat
    available_cats = set(adata.obs[reference_key].unique())
    missing_cats = set(ref_cats) - available_cats
    if missing_cats:
        raise ValueError(
            f"Reference categories not found in adata.obs['{reference_key}']: "
            f"{sorted(missing_cats)}. Available: {sorted(available_cats)}"
        )

    # Run infercnv
    if verbose:
        logger.info("Running CNV inference...")

    # infercnvpy >= 0.6 uses None (not -1) for "all cores"
    effective_n_jobs = None if n_jobs == -1 else n_jobs

    try:
        cnv.tl.infercnv(
            adata,
            reference_key=reference_key,
            reference_cat=reference_cat,
            window_size=window_size,
            step=step,
            lfc_clip=lfc_clip,
            dynamic_threshold=dynamic_threshold,
            exclude_chromosomes=exclude_chromosomes,
            chunksize=chunksize,
            n_jobs=effective_n_jobs,
            inplace=True,
            layer=layer,
            key_added=key_added,
            calculate_gene_values=calculate_gene_values
        )
    except Exception as e:
        logger.error(f"CNV inference failed: {e}")
        raise

    if verbose:
        logger.info("CNV inference complete!")
        logger.info(f"Results stored in adata.obsm['X_{key_added}']")
        logger.info(f"Chromosome positions in adata.uns['{key_added}']")
        if calculate_gene_values:
            logger.info(f"Per-gene CNV in adata.layers['gene_values_{key_added}']")
        logger.info("=" * 60)


def cluster_by_cnv(
    adata: AnnData,
    key: str = "cnv",
    n_neighbors: int = 15,
    n_pcs: int = 50,
    resolution: float = 0.5,
    inplace: bool = True
) -> Optional[AnnData]:
    """
    Cluster cells by CNV profile.

    Parameters
    ----------
    adata : AnnData
        AnnData with CNV matrix in adata.obsm[f"X_{key}"]
    key : str
        Key used for CNV inference (default: "cnv")
    n_neighbors : int
        Number of neighbors for graph construction (default: 15)
    n_pcs : int
        Number of principal components to use (default: 50)
    resolution : float
        Leiden clustering resolution (default: 0.5)
    inplace : bool
        Modify adata in place

    Returns
    -------
    AnnData or None
        Modified AnnData with CNV-based clustering in adata.obs[f"{key}_leiden"]

    Examples
    --------
    >>> cluster_by_cnv(adata, key="cnv", resolution=0.5)
    >>> sc.pl.umap(adata, color="cnv_leiden")
    """
    if not inplace:
        adata = adata.copy()

    cnv_key = f"X_{key}"
    if cnv_key not in adata.obsm:
        raise ValueError(f"CNV matrix not found in adata.obsm['{cnv_key}']. Run infercnv first.")

    logger.info("Clustering cells by CNV profile...")

    # Cap n_pcs to available dimensions (windows - 1)
    max_pcs = adata.obsm[cnv_key].shape[1] - 1
    effective_pcs = min(n_pcs, max_pcs) if max_pcs > 0 else 1
    if effective_pcs < n_pcs:
        logger.warning(f"n_pcs reduced from {n_pcs} to {effective_pcs} (CNV matrix has {max_pcs + 1} windows)")

    # Use CNV matrix for dimensionality reduction
    sc.pp.neighbors(
        adata,
        use_rep=cnv_key,
        n_neighbors=n_neighbors,
        n_pcs=effective_pcs
    )

    sc.tl.umap(adata)
    sc.tl.leiden(adata, key_added=f"{key}_leiden", resolution=resolution)

    logger.info(f"Clustering complete. Found {adata.obs[f'{key}_leiden'].nunique()} clusters")

    if not inplace:
        return adata


def identify_cnv_regions(
    adata: AnnData,
    key: str = "cnv",
    threshold: float = 0.3,
    min_cells: int = 10
) -> pd.DataFrame:
    """
    Identify significant CNV alterations per chromosome.

    Parameters
    ----------
    adata : AnnData
        AnnData with CNV results
    key : str
        CNV key (default: "cnv")
    threshold : float
        Absolute CNV threshold (default: 0.3)
    min_cells : int
        Minimum cells with alteration (default: 10)

    Returns
    -------
    pd.DataFrame
        DataFrame with CNV alteration summary

    Examples
    --------
    >>> cnv_regions = identify_cnv_regions(adata, threshold=0.3)
    >>> print(cnv_regions)
    """
    cnv_key = f"X_{key}"
    if cnv_key not in adata.obsm:
        raise ValueError(f"CNV matrix not found in adata.obsm['{cnv_key}']")

    cnv_matrix = adata.obsm[cnv_key]
    chr_pos = adata.uns[key]["chr_pos"]

    results = []

    for chrom, start_idx in chr_pos.items():
        # Get end index
        chroms = list(chr_pos.keys())
        chrom_idx = chroms.index(chrom)
        if chrom_idx < len(chroms) - 1:
            end_idx = list(chr_pos.values())[chrom_idx + 1]
        else:
            end_idx = cnv_matrix.shape[1]

        # Get CNV values for this chromosome
        chr_slice = cnv_matrix[:, start_idx:end_idx]
        chr_cnv = chr_slice.toarray() if hasattr(chr_slice, "toarray") else np.array(chr_slice)

        # Calculate metrics
        mean_cnv = chr_cnv.mean()
        abs_mean_cnv = np.abs(chr_cnv).mean()
        std_cnv = chr_cnv.std()

        # Count cells with any alteration on this chromosome
        cells_with_amp = np.any(chr_cnv > threshold, axis=1).sum()
        cells_with_del = np.any(chr_cnv < -threshold, axis=1).sum()
        cells_altered = np.any(np.abs(chr_cnv) > threshold, axis=1).sum()

        # Count total alteration events (cell-window pairs)
        n_amp_events = (chr_cnv > threshold).sum()
        n_del_events = (chr_cnv < -threshold).sum()

        if cells_altered >= min_cells:
            results.append({
                "chromosome": chrom,
                "mean_cnv": mean_cnv,
                "abs_mean_cnv": abs_mean_cnv,
                "std_cnv": std_cnv,
                "n_cells_amp": int(cells_with_amp),
                "n_cells_del": int(cells_with_del),
                "n_cells_altered": int(cells_altered),
                "n_amp_events": int(n_amp_events),
                "n_del_events": int(n_del_events),
            })

    df = pd.DataFrame(results)
    if df.empty:
        return df
    return df.sort_values("n_cells_altered", ascending=False)


def summarize_cnv_by_chromosome(
    adata: AnnData,
    key: str = "cnv",
    groupby: Optional[str] = None
) -> pd.DataFrame:
    """
    Summarize CNV profiles by chromosome.

    Parameters
    ----------
    adata : AnnData
        AnnData with CNV results
    key : str
        CNV key (default: "cnv")
    groupby : str, optional
        Column in adata.obs for grouping (e.g., cell type)

    Returns
    -------
    pd.DataFrame
        Summary statistics per chromosome

    Examples
    --------
    >>> summary = summarize_cnv_by_chromosome(adata, groupby="cell_type")
    >>> print(summary)
    """
    cnv_key = f"X_{key}"
    if cnv_key not in adata.obsm:
        raise ValueError(f"CNV matrix not found in adata.obsm['{cnv_key}']")

    cnv_matrix = adata.obsm[cnv_key]
    chr_pos = adata.uns[key]["chr_pos"]

    results = []

    groups = [None] if groupby is None else adata.obs[groupby].unique()

    for group in groups:
        if group is None:
            mask = np.ones(adata.n_obs, dtype=bool)
            group_name = "all"
        else:
            mask = (adata.obs[groupby] == group).values
            group_name = group

        for chrom, start_idx in chr_pos.items():
            # Get chromosome indices
            chroms = list(chr_pos.keys())
            chrom_idx = chroms.index(chrom)
            if chrom_idx < len(chroms) - 1:
                end_idx = list(chr_pos.values())[chrom_idx + 1]
            else:
                end_idx = cnv_matrix.shape[1]

            # Get CNV for this group and chromosome
            chr_slice = cnv_matrix[mask, start_idx:end_idx]
            chr_cnv = chr_slice.toarray() if hasattr(chr_slice, "toarray") else np.array(chr_slice)

            results.append({
                "group": group_name,
                "chromosome": chrom,
                "mean_cnv": chr_cnv.mean(),
                "std_cnv": chr_cnv.std(),
                "min_cnv": chr_cnv.min(),
                "max_cnv": chr_cnv.max(),
                "n_cells": mask.sum()
            })

    return pd.DataFrame(results)


def export_cnv_results(
    adata: AnnData,
    output_dir: Path,
    key: str = "cnv",
    prefix: str = "infercnv"
) -> None:
    """
    Export CNV results to files.

    Parameters
    ----------
    adata : AnnData
        AnnData with CNV results
    output_dir : Path
        Directory for output files
    key : str
        CNV key (default: "cnv")
    prefix : str
        Prefix for output files (default: "infercnv")

    Examples
    --------
    >>> export_cnv_results(adata, "./cnv_results/", key="cnv")
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cnv_key = f"X_{key}"
    if cnv_key not in adata.obsm:
        raise ValueError(f"CNV matrix not found in adata.obsm['{cnv_key}']")

    logger.info(f"Exporting CNV results to {output_dir}")

    # Export CNV matrix
    cnv_matrix = adata.obsm[cnv_key]
    cnv_df = pd.DataFrame(
        cnv_matrix.toarray() if hasattr(cnv_matrix, "toarray") else cnv_matrix,
        index=adata.obs_names
    )
    cnv_df.to_csv(output_dir / f"{prefix}_infercnv_matrix.csv.gz")

    # Export chromosome positions
    chr_pos = adata.uns[key]["chr_pos"]
    pd.Series(chr_pos).to_csv(output_dir / f"{prefix}_infercnv_chr_pos.csv")

    # Export cell metadata with CNV clusters if available
    obs_cols = [col for col in adata.obs.columns if key in col]
    if obs_cols:
        adata.obs[obs_cols].to_csv(output_dir / f"{prefix}_infercnv_cell_metadata.csv")

    logger.info("Export complete!")


def calculate_cnv_score(
    adata: AnnData,
    method: str = "cell",
    groupby: str = "cnv_leiden",
    key_added: str = "cnv_score",
    use_rep: str = "cnv",
    inplace: bool = True
) -> Optional[np.ndarray]:
    """
    Calculate CNV score for cells.

    Parameters
    ----------
    adata : AnnData
        AnnData with CNV results
    method : str
        "cell" for cell-level score, "cluster" for cluster-level score (default: "cell")
    groupby : str
        Column in adata.obs for grouping when method="cluster" (default: "cnv_leiden")
    key_added : str
        Key for storing results in adata.obs (default: "cnv_score")
    use_rep : str
        Key for CNV matrix in adata.obsm (default: "cnv")
    inplace : bool
        If True, store result in adata.obs; otherwise return array

    Returns
    -------
    np.ndarray or None
        CNV scores if inplace=False

    Examples
    --------
    >>> # Cell-level score
    >>> calculate_cnv_score(adata, method="cell", key_added="cnv_score")
    >>> print(adata.obs["cnv_score"])

    >>> # Cluster-level score (same as cnv.tl.cnv_score)
    >>> calculate_cnv_score(adata, method="cluster", groupby="cnv_leiden")
    """
    cnv_key = f"X_{use_rep}"
    if cnv_key not in adata.obsm:
        raise ValueError(f"CNV matrix not found in adata.obsm['{cnv_key}']. Run infercnv first.")

    cnv_matrix = adata.obsm[cnv_key]
    if sp.issparse(cnv_matrix):
        cnv_matrix = cnv_matrix.toarray()

    if method == "cell":
        # Cell-level: mean of absolute CNV values for each cell
        scores = np.abs(cnv_matrix).mean(axis=1)
        logger.info(f"Calculated cell-level CNV score for {len(scores)} cells")
    elif method == "cluster":
        # Cluster-level: same as infercnvpy's cnv_score
        if groupby not in adata.obs.columns:
            raise ValueError(f"'{groupby}' not found in adata.obs. Run leiden clustering first.")
        cluster_scores = {
            cluster: np.mean(np.abs(cnv_matrix[adata.obs[groupby].values == cluster, :]))
            for cluster in adata.obs[groupby].unique()
        }
        scores = np.array([cluster_scores[c] for c in adata.obs[groupby]])
        logger.info(f"Calculated cluster-level CNV score for {len(cluster_scores)} clusters")
    else:
        raise ValueError("method must be 'cell' or 'cluster'")

    if inplace:
        adata.obs[key_added] = scores
    else:
        return scores


if __name__ == "__main__":
    print("infercnvpy Analysis Module")
    print("\nAvailable functions:")
    print("- read_gtf_positions()")
    print("- add_gene_positions()")
    print("- run_infercnv_pipeline()")

    print("- cluster_by_cnv()")
    print("- calculate_cnv_score()")
    print("- identify_cnv_regions()")
    print("- summarize_cnv_by_chromosome()")
    print("- export_cnv_results()")
    print("\nFor more info, see SKILL.md and usage-guide.md")
