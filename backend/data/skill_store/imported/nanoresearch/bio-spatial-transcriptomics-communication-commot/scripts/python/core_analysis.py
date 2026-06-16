"""
COMMOT core analysis module for spatial cell-cell communication.

Optimal transport-based spatial cell-cell communication analysis
with spatial distance constraints and directionality inference.

All wrappers map to the native COMMOT API (v0.0.3) with these key patterns:
  - Results stored under keys like: 'commot-{database_name}-...'
  - spatial_communication requires database_name (not key_added)
  - cluster_communication uses native param 'clustering' (not 'cluster_key')

Author: Yang Guo
Date: 2026-04-03
Version: 1.2.0
"""

import warnings
from typing import Optional, List, Dict, Tuple, Union
import pandas as pd
import numpy as np
from scipy import sparse
import scanpy as sc
from anndata import AnnData


# ============================================================================
# Data Preparation
# ============================================================================

def prepare_data(
    adata: AnnData,
    spatial_key: str = 'spatial',
    min_counts: int = 100,
    normalize: bool = True,
    log1p: bool = True,
) -> AnnData:
    """
    Prepare spatial data for COMMOT analysis.

    Parameters
    ----------
    adata : AnnData
        Spatial transcriptomics data
    spatial_key : str, default='spatial'
        Key for spatial coordinates in obsm
    min_counts : int, default=100
        Minimum counts per spot/cell
    normalize : bool, default=True
        Whether to normalize total counts
    log1p : bool, default=True
        Whether to apply log1p transformation

    Returns
    -------
    AnnData
        Prepared data with normalized counts and validated spatial coordinates
    """
    try:
        import commot as ct
    except ImportError:
        raise ImportError(
            "commot not installed. Install with: pip install commot"
        )

    adata = adata.copy()

    # Check spatial coordinates
    if spatial_key not in adata.obsm:
        available = list(adata.obsm.keys())
        raise ValueError(
            f"'{spatial_key}' not found in adata.obsm. "
            f"Available: {available}"
        )

    # Check spatial coordinates dimensions
    spatial_coords = adata.obsm[spatial_key]
    if spatial_coords.shape[1] < 2:
        raise ValueError(
            f"Spatial coordinates must have at least 2 dimensions, "
            f"got {spatial_coords.shape[1]}"
        )

    print(f"Spatial coordinates: {spatial_coords.shape}")
    print(f"Coordinate range: X[{spatial_coords[:,0].min():.1f}, {spatial_coords[:,0].max():.1f}], "
          f"Y[{spatial_coords[:,1].min():.1f}, {spatial_coords[:,1].max():.1f}]")

    # Filter low quality spots
    if 'total_counts' not in adata.obs:
        adata.obs['total_counts'] = np.array(adata.X.sum(axis=1)).flatten()

    n_before = adata.n_obs
    adata = adata[adata.obs['total_counts'] >= min_counts].copy()
    n_after = adata.n_obs

    if n_after < n_before:
        print(f"Filtered {n_before - n_after} spots with < {min_counts} counts")

    if n_after == 0:
        raise ValueError("No spots remaining after filtering!")

    # Normalize if requested
    if normalize:
        sc.pp.normalize_total(adata, inplace=True)
        print("Normalized total counts to 10,000")

    if log1p:
        sc.pp.log1p(adata)
        print("Applied log1p transformation")

    print(f"Final data: {adata.n_obs} spots x {adata.n_vars} genes")
    return adata


def check_spatial_units(
    adata: AnnData,
    spatial_key: str = 'spatial',
    expected_scale: str = 'microns'
) -> None:
    """
    Check and report spatial coordinate units.

    Parameters
    ----------
    adata : AnnData
        Spatial data
    spatial_key : str, default='spatial'
        Key for spatial coordinates
    expected_scale : str, default='microns'
        Expected scale for coordinates

    Notes
    -----
    COMMOT expects spatial coordinates in microns. This function helps
    verify the scale of coordinates.
    """
    coords = adata.obsm[spatial_key]

    # Calculate typical distances
    from scipy.spatial.distance import pdist
    distances = pdist(coords[:min(100, len(coords))])
    median_dist = np.median(distances)

    print(f"Median distance between spots: {median_dist:.2f} units")

    if median_dist < 1:
        warnings.warn(
            "Spatial coordinates appear to be normalized (median distance < 1). "
            "COMMOT works best with coordinates in microns. "
            "Consider scaling your coordinates."
        )
    elif median_dist > 10000:
        warnings.warn(
            "Spatial coordinates appear to be in a very large scale. "
            "Ensure coordinates are in microns for correct distance thresholds."
        )
    else:
        print(f"Coordinates appear to be in appropriate units ({expected_scale})")


# ============================================================================
# Database Functions
# ============================================================================

def get_lr_database(
    database: str = 'CellChat',
    species: str = 'human',
    signaling_type: Optional[str] = 'Secreted Signaling',
) -> pd.DataFrame:
    """
    Get ligand-receptor database from COMMOT.

    Parameters
    ----------
    database : str, default='CellChat'
        Database name: 'CellChat' or 'CellPhoneDB_v4.0'
    species : str, default='human'
        Species: 'human', 'mouse', or 'zebrafish' (CellChat only)
    signaling_type : str, optional, default='Secreted Signaling'
        Type of signaling to include:
        - 'Secreted Signaling': Secreted ligands
        - 'Cell-Cell Contact': Membrane-bound signaling
        - 'ECM-Receptor': ECM-receptor interactions (CellChat only)
        - None: Include all types

    Returns
    -------
    pd.DataFrame
        DataFrame with columns: ligand, receptor, pathway_name, signaling_type

    Examples
    --------
    >>> df_lr = get_lr_database('CellChat', 'human', 'Secreted Signaling')
    >>> print(df_lr.head())
    """
    try:
        import commot as ct
    except ImportError:
        raise ImportError("commot not installed")

    df_ligrec = ct.pp.ligand_receptor_database(
        database=database,
        species=species,
        signaling_type=signaling_type,
    )

    print(f"Loaded {len(df_ligrec)} LR pairs from {database} ({species})")
    print(f"Signaling type: {signaling_type or 'All'}")
    print(f"Unique pathways: {df_ligrec.iloc[:,2].nunique()}")

    return df_ligrec


def filter_lr_database(
    df_ligrec: pd.DataFrame,
    adata: AnnData,
    min_cell_pct: float = 0.05,
    heteromeric: bool = True,
    heteromeric_delimiter: str = '_',
) -> pd.DataFrame:
    """
    Filter LR database to include only pairs expressed in data.

    Parameters
    ----------
    df_ligrec : pd.DataFrame
        LR database from get_lr_database()
    adata : AnnData
        Spatial data
    min_cell_pct : float, default=0.05
        Minimum percentage of cells expressing both ligand and receptor
    heteromeric : bool, default=True
        Whether to handle heteromeric complexes
    heteromeric_delimiter : str, default='_'
        Delimiter for heteromeric units (e.g., 'TGFBR1_TGFBR2')

    Returns
    -------
    pd.DataFrame
        Filtered LR database

    Examples
    --------
    >>> df_lr = get_lr_database('CellChat', 'human')
    >>> df_lr_filtered = filter_lr_database(df_lr, adata, min_cell_pct=0.1)
    """
    try:
        import commot as ct
    except ImportError:
        raise ImportError("commot not installed")

    # Use COMMOT's built-in filtering
    df_filtered = ct.pp.filter_lr_database(
        df_ligrec=df_ligrec,
        adata=adata,
        heteromeric=heteromeric,
        heteromeric_delimiter=heteromeric_delimiter,
        filter_criteria='min_cell_pct',
        min_cell_pct=min_cell_pct,
    )

    print(f"Filtered to {len(df_filtered)} LR pairs "
          f"(expressed in >= {min_cell_pct*100}% of cells)")

    return df_filtered


def create_custom_lr_database(
    ligands: List[str],
    receptors: List[str],
    pathways: Optional[List[str]] = None,
) -> pd.DataFrame:
    """
    Create custom ligand-receptor database.

    Parameters
    ----------
    ligands : List[str]
        List of ligand gene names
    receptors : List[str]
        List of receptor gene names
    pathways : List[str], optional
        List of pathway names for each pair

    Returns
    -------
    pd.DataFrame
        Custom LR database compatible with COMMOT

    Examples
    --------
    >>> df_custom = create_custom_lr_database(
    ...     ligands=['TGFB1', 'IL6', 'WNT5A'],
    ...     receptors=['TGFBR1_TGFBR2', 'IL6R_IL6ST', 'FZD4'],
    ...     pathways=['TGFb', 'IL6', 'WNT']
    ... )
    """
    if len(ligands) != len(receptors):
        raise ValueError("ligands and receptors must have same length")

    if pathways is None:
        pathways = [f'Pathway_{i}' for i in range(len(ligands))]

    if len(pathways) != len(ligands):
        raise ValueError("pathways must have same length as ligands")

    df = pd.DataFrame({
        'ligand': ligands,
        'receptor': receptors,
        'pathway_name': pathways,
    })

    print(f"Created custom LR database with {len(df)} pairs")
    return df


# ============================================================================
# Core Analysis Functions
# ============================================================================

def _derive_database_name(database: str) -> str:
    """Derive a lowercase database_name from database string."""
    name = database.lower()
    # Map common names to COMMOT conventions
    if 'cellphone' in name or 'cpdb' in name:
        return 'cpdb'
    if 'cellchat' in name:
        return 'cellchat'
    return name.replace(' ', '_').replace('.', '_')


def run_commot(
    adata: AnnData,
    df_ligrec: pd.DataFrame,
    database_name: str,
    distance_threshold: float = 200.0,
    heteromeric: bool = True,
    heteromeric_rule: str = 'min',
    heteromeric_delimiter: str = '_',
    cost_type: str = 'euc',
    cot_eps_p: float = 0.1,
    cot_rho: float = 10.0,
    pathway_sum: bool = True,
    copy: bool = False,
) -> Optional[AnnData]:
    """
    Run COMMOT spatial communication analysis.

    Parameters
    ----------
    adata : AnnData
        Prepared spatial data
    df_ligrec : pd.DataFrame
        Ligand-receptor pairs (columns: ligand, receptor, pathway_name)
    database_name : str
        Name for the LR database. Used by COMMOT to namespace results
        (e.g., 'cellchat', 'custom', 'cpdb'). Results will be stored under
        keys like 'commot-{database_name}-sum-sender'.
    distance_threshold : float, default=200.0
        Maximum distance for cell-cell communication (microns)
    heteromeric : bool, default=True
        Handle heteromeric complexes (e.g., TGFBR1_TGFBR2)
    heteromeric_rule : str, default='min'
        Rule for heteromeric quantification: 'min' or 'ave'
    heteromeric_delimiter : str, default='_'
        Delimiter for heteromeric units
    cost_type : str, default='euc'
        Cost function type: 'euc' or 'euc_square'
    cot_eps_p : float, default=0.1
        Entropy regularization parameter for optimal transport
    cot_rho : float, default=10.0
        Marginal relaxation parameter
    pathway_sum : bool, default=True
        Whether to sum communication by pathway
    copy : bool, default=False
        Return copy of adata instead of modifying in place

    Returns
    -------
    AnnData or None
        Data with COMMOT results stored in adata.obsm/obsp/uns.
        Returns adata if copy=True, otherwise modifies in place.

    Examples
    --------
    >>> df_lr = get_lr_database('CellChat', 'human')
    >>> adata = run_commot(adata, df_lr, database_name='cellchat', distance_threshold=250.0)

    Notes
    -----
    Results are stored with the following key patterns:
    - adata.obsp['commot-{database_name}-{ligand}-{receptor}']: communication matrix
    - adata.obsm['commot-{database_name}-sum-sender']: total sent signal per spot
    - adata.obsm['commot-{database_name}-sum-receiver']: total received signal per spot
    - adata.uns['commot-{database_name}-info']: analysis metadata
    """
    try:
        import commot as ct
    except ImportError:
        raise ImportError("commot not installed")

    if 'spatial' not in adata.obsm:
        raise ValueError("'spatial' not found in adata.obsm. Run prepare_data() first.")

    if copy:
        adata = adata.copy()

    print(f"\n{'='*60}")
    print(f"Running COMMOT Analysis")
    print(f"{'='*60}")
    print(f"LR pairs: {len(df_ligrec)}")
    print(f"Database name: {database_name}")
    print(f"Distance threshold: {distance_threshold} microns")
    print(f"Heteromeric complexes: {heteromeric}")
    print(f"{'='*60}\n")

    # Run COMMOT with correct native API parameters
    ct.tl.spatial_communication(
        adata,
        database_name=database_name,
        df_ligrec=df_ligrec,
        dis_thr=distance_threshold,
        heteromeric=heteromeric,
        heteromeric_rule=heteromeric_rule,
        heteromeric_delimiter=heteromeric_delimiter,
        cost_type=cost_type,
        cot_eps_p=cot_eps_p,
        cot_rho=cot_rho,
        pathway_sum=pathway_sum,
        copy=False,  # We already copied if needed
    )

    print(f"\n{'='*60}")
    print(f"COMMOT Analysis Complete!")
    print(f"{'='*60}")
    print(f"Results stored with prefix 'commot-{database_name}'")
    prefix = f'commot-{database_name}'
    print(f"Available keys: {[k for k in adata.obsm.keys() if k.startswith(prefix)]}")

    if copy:
        return adata


def run_commot_database(
    adata: AnnData,
    database: str = 'CellChat',
    species: str = 'human',
    signaling_type: Optional[str] = 'Secreted Signaling',
    filter_pairs: bool = True,
    min_cell_pct: float = 0.05,
    distance_threshold: float = 200.0,
    **kwargs
) -> AnnData:
    """
    Run COMMOT with built-in database.

    Convenience function to run COMMOT with a built-in LR database.

    Parameters
    ----------
    adata : AnnData
        Prepared spatial data
    database : str, default='CellChat'
        Database name: 'CellChat' or 'CellPhoneDB_v4.0'
    species : str, default='human'
        Species: 'human' or 'mouse'
    signaling_type : str, optional
        Type of signaling to include
    filter_pairs : bool, default=True
        Whether to filter pairs by expression
    min_cell_pct : float, default=0.05
        Minimum cell percentage for filtering
    distance_threshold : float, default=200.0
        Maximum distance for communication
    **kwargs
        Additional arguments passed to run_commot()

    Returns
    -------
    AnnData
        Data with COMMOT results (modified in place)

    Examples
    --------
    >>> adata = run_commot_database(
    ...     adata,
    ...     database='CellChat',
    ...     species='human',
    ...     signaling_type='Secreted Signaling',
    ...     distance_threshold=250.0
    ... )
    """
    # Derive database_name from database string
    database_name = _derive_database_name(database)

    # Get database
    df_ligrec = get_lr_database(database, species, signaling_type)

    # Filter if requested
    if filter_pairs:
        df_ligrec = filter_lr_database(df_ligrec, adata, min_cell_pct)

    # Run COMMOT
    run_commot(
        adata,
        df_ligrec=df_ligrec,
        database_name=database_name,
        distance_threshold=distance_threshold,
        **kwargs
    )

    # Store database info (defensively check key exists)
    info_key = f'commot-{database_name}-info'
    if info_key in adata.uns:
        adata.uns[info_key]['wrapper'] = {
            'database': database,
            'species': species,
            'signaling_type': signaling_type,
            'n_pairs': len(df_ligrec),
            'distance_threshold': distance_threshold,
        }
    else:
        warnings.warn(
            f"'{info_key}' not found in adata.uns. "
            "COMMOT may have failed to create metadata. Skipping wrapper info storage."
        )

    return adata


# ============================================================================
# Downstream Analysis Functions
# ============================================================================

def infer_communication_direction(
    adata: AnnData,
    database_name: str,
    pathway_name: Optional[str] = None,
    lr_pair: Optional[Tuple[str, str]] = None,
    k: int = 5,
) -> None:
    """
    Infer communication direction for spatial visualization.

    Parameters
    ----------
    adata : AnnData
        Data with COMMOT results
    database_name : str
        Database name used in run_commot() (e.g., 'cellchat', 'custom')
    pathway_name : str, optional
        Signaling pathway to analyze. Alternative to lr_pair.
    lr_pair : tuple[str, str], optional
        Specific LR pair as (ligand, receptor). Alternative to pathway_name.
        Example: ('TGFB1', 'TGFBR1_TGFBR2')
    k : int, default=5
        Number of nearest neighbors for direction inference

    Examples
    --------
    >>> infer_communication_direction(adata, database_name='cellchat', pathway_name='TGFb')
    >>> infer_communication_direction(adata, database_name='cellchat', lr_pair=('TGFB1', 'TGFBR1_TGFBR2'))
    """
    try:
        import commot as ct
    except ImportError:
        raise ImportError("commot not installed")

    ct.tl.communication_direction(
        adata,
        database_name=database_name,
        pathway_name=pathway_name,
        lr_pair=lr_pair,
        k=k,
    )

    what = pathway_name or (f"{lr_pair[0]}-{lr_pair[1]}" if lr_pair else "all")
    print(f"Communication direction inferred for {database_name}: {what}")


def cluster_communication(
    adata: AnnData,
    cluster_key: str,
    database_name: str,
    pathway_name: Optional[str] = None,
    lr_pair: Optional[Tuple[str, str]] = None,
    n_permutations: int = 100,
) -> pd.DataFrame:
    """
    Summarize communication between cell clusters.

    Parameters
    ----------
    adata : AnnData
        Data with COMMOT results
    cluster_key : str
        Key in adata.obs for cell type/cluster annotations.
        Mapped to native parameter 'clustering'.
    database_name : str
        Database name used in run_commot()
    pathway_name : str, optional
        Pathway to analyze. If None, analyzes all pathways.
    lr_pair : tuple[str, str], optional
        Specific LR pair as (ligand, receptor).
    n_permutations : int, default=100
        Number of permutations for significance testing

    Returns
    -------
    pd.DataFrame
        Communication matrix between clusters

    Examples
    --------
    >>> comm_matrix = cluster_communication(
    ...     adata, cluster_key='cell_type', database_name='cellchat'
    ... )
    """
    try:
        import commot as ct
    except ImportError:
        raise ImportError("commot not installed")

    if cluster_key not in adata.obs:
        raise ValueError(f"'{cluster_key}' not found in adata.obs")

    # Get cluster communication using native API
    ct.tl.cluster_communication(
        adata,
        database_name=database_name,
        pathway_name=pathway_name,
        lr_pair=lr_pair,
        clustering=cluster_key,
        n_permutations=n_permutations,
    )

    # Extract communication matrix from the correct uns key
    # Native stores at: commot_cluster-{clustering}-{database_name}-{pathway_or_lr}
    if lr_pair is not None:
        suffix = f"{lr_pair[0]}-{lr_pair[1]}"
    elif pathway_name is not None:
        suffix = pathway_name
    else:
        suffix = "total-total"

    comm_key = f'commot_cluster-{cluster_key}-{database_name}-{suffix}'

    # Also try without suffix for total
    if comm_key not in adata.uns:
        # Auto-discover matching keys
        prefix = f'commot_cluster-{cluster_key}-{database_name}'
        matching_keys = [k for k in adata.uns.keys() if k.startswith(prefix)]
        if matching_keys:
            comm_key = matching_keys[0]
        else:
            raise KeyError(
                f"'{comm_key}' not found in adata.uns. "
                f"Run COMMOT first. Available cluster keys: "
                f"{[k for k in adata.uns.keys() if 'commot_cluster' in k][:10]}"
            )

    comm_matrix = adata.uns[comm_key]['communication_matrix']

    print(f"Cluster communication computed for {cluster_key}")
    print(f"Clusters: {comm_matrix.shape}")

    return comm_matrix


def detect_communication_deg(
    adata: AnnData,
    database_name: str,
    pathway_name: Optional[str] = None,
    lr_pair: Optional[Tuple[str, str]] = None,
    summary: str = 'receiver',
    n_var_genes: int = 2000,
    nknots: int = 6,
    deg_pvalue_cutoff: float = 0.05,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Detect genes associated with cell-cell communication (requires tradeSeq).

    Uses tradeSeq to identify genes whose expression correlates with
    communication strength.

    Parameters
    ----------
    adata : AnnData
        Data with raw counts in adata.layers['counts']
    database_name : str
        Database name used in run_commot()
    pathway_name : str, optional
        Pathway to analyze (alternative to lr_pair)
    lr_pair : tuple[str, str], optional
        Specific LR pair as (ligand, receptor)
    summary : str, default='receiver'
        'sender' or 'receiver' for signal direction
    n_var_genes : int, default=2000
        Number of variable genes to test
    nknots : int, default=6
        Number of knots for GAM fitting
    deg_pvalue_cutoff : float, default=0.05
        P-value cutoff for significance

    Returns
    -------
    Tuple[pd.DataFrame, pd.DataFrame]
        DEG results and fitted expression patterns

    Notes
    -----
    Requires tradeSeq R package and rpy2. Install with:
    pip install commot[tradeSeq]

    Examples
    --------
    >>> df_deg, df_yhat = detect_communication_deg(
    ...     adata,
    ...     database_name='cellchat',
    ...     pathway_name='TGFb',
    ...     summary='receiver'
    ... )
    """
    try:
        import commot as ct
    except ImportError:
        raise ImportError("commot not installed")

    # Check for tradeSeq dependencies
    try:
        import rpy2
        import anndata2ri
    except ImportError:
        raise ImportError(
            "tradeSeq analysis requires rpy2 and anndata2ri. "
            "Install with: pip install commot[tradeSeq]"
        )

    # Check for counts layer
    if 'counts' not in adata.layers:
        raise ValueError("Raw counts required in adata.layers['counts']")

    # Run DEG detection with correct database_name
    df_deg, df_yhat = ct.tl.communication_deg_detection(
        adata,
        database_name=database_name,
        pathway_name=pathway_name,
        lr_pair=lr_pair,
        summary=summary,
        n_var_genes=n_var_genes,
        nknots=nknots,
        deg_pvalue_cutoff=deg_pvalue_cutoff,
    )

    n_sig = (df_deg['pvalue'] < deg_pvalue_cutoff).sum()
    print(f"Detected {n_sig} significant DEGs (p < {deg_pvalue_cutoff})")

    return df_deg, df_yhat


def communication_spatial_autocorrelation(
    adata: AnnData,
    keys: Optional[List[str]] = None,
    database_name: Optional[str] = None,
    method: str = 'moran',
) -> pd.DataFrame:
    """
    Calculate spatial autocorrelation of communication.

    Parameters
    ----------
    adata : AnnData
        Data with COMMOT results
    keys : list[str], optional
        List of keys in adata.obsm/obsp to analyze.
        If None, auto-discovered from database_name.
    database_name : str, optional
        Database name used in run_commot(). Used to auto-discover keys
        if keys is not provided.
    method : str, default='moran'
        Method for autocorrelation: 'moran' or 'geary'

    Returns
    -------
    pd.DataFrame
        Spatial autocorrelation statistics for each LR pair

    Examples
    --------
    >>> df_autocorr = communication_spatial_autocorrelation(
    ...     adata, database_name='cellchat'
    ... )
    """
    try:
        import commot as ct
    except ImportError:
        raise ImportError("commot not installed")

    # Auto-discover keys if not provided
    if keys is None:
        if database_name is None:
            raise ValueError(
                "Either 'keys' or 'database_name' must be provided"
            )
        prefix = f'commot-{database_name}'
        keys = [k for k in adata.obsp.keys() if k.startswith(prefix)]
        if not keys:
            raise ValueError(
                f"No keys found for database_name='{database_name}'. "
                f"Run COMMOT first."
            )

    df = ct.tl.communication_spatial_autocorrelation(
        adata,
        keys=keys,
        method=method,
    )

    return df


# ============================================================================
# Result Access Functions
# ============================================================================

def get_communication_matrix(
    adata: AnnData,
    lr_pair: str,
    database_name: str = 'cellchat',
) -> 'sparse.spmatrix':
    """
    Get communication matrix for a specific LR pair.

    Parameters
    ----------
    adata : AnnData
        Data with COMMOT results
    lr_pair : str
        LR pair name (format: 'LIGAND-RECEPTOR')
    database_name : str, default='cellchat'
        Database name used in run_commot()

    Returns
    -------
    np.ndarray
        Communication matrix (n_spots x n_spots)

    Examples
    --------
    >>> comm_mat = get_communication_matrix(adata, 'TGFB1-TGFBR1_TGFBR2', database_name='cellchat')
    """
    pair_key = f'commot-{database_name}-{lr_pair}'

    if pair_key not in adata.obsp:
        available = [k for k in adata.obsp.keys() if k.startswith(f'commot-{database_name}')]
        raise KeyError(
            f"'{pair_key}' not found. "
            f"Available LR pairs: {available[:10]}..."
        )

    return adata.obsp[pair_key]


def get_communication_summary(
    adata: AnnData,
    summary: str = 'receiver',
    database_name: str = 'cellchat',
) -> pd.DataFrame:
    """
    Get communication summary per spot.

    Parameters
    ----------
    adata : AnnData
        Data with COMMOT results
    summary : str, default='receiver'
        'sender' or 'receiver'
    database_name : str, default='cellchat'
        Database name used in run_commot()

    Returns
    -------
    pd.DataFrame
        Summary of communication per spot

    Examples
    --------
    >>> df_summary = get_communication_summary(adata, 'receiver', database_name='cellchat')
    """
    summary_key = f'commot-{database_name}-sum-{summary}'

    if summary_key not in adata.obsm:
        raise KeyError(f"'{summary_key}' not found. Run COMMOT first.")

    df = adata.obsm[summary_key].copy()

    return df


def get_top_lr_pairs(
    adata: AnnData,
    n: int = 10,
    database_name: str = 'cellchat',
    by: str = 'total',
) -> pd.DataFrame:
    """
    Get top LR pairs by total communication strength.

    Parameters
    ----------
    adata : AnnData
        Data with COMMOT results
    n : int, default=10
        Number of top pairs to return
    database_name : str, default='cellchat'
        Database name used in run_commot()
    by : str, default='total'
        Summary statistic to use: 'sender', 'receiver', or 'total'

    Returns
    -------
    pd.DataFrame
        Top LR pairs with communication strengths

    Examples
    --------
    >>> df_top = get_top_lr_pairs(adata, n=10, database_name='cellchat')
    """
    # Get summary data (gracefully handle missing)
    try:
        df_sender = get_communication_summary(adata, 'sender', database_name)
    except KeyError:
        df_sender = pd.DataFrame()
    try:
        df_receiver = get_communication_summary(adata, 'receiver', database_name)
    except KeyError:
        df_receiver = pd.DataFrame()

    if df_sender.empty and df_receiver.empty:
        raise ValueError(f"No COMMOT summary data found for database_name='{database_name}'")

    # Extract pair names from column names (strip 's-' / 'r-' prefixes)
    def _extract_pair(col):
        if col.startswith('s-') or col.startswith('r-'):
            return col[2:]
        return col

    all_pairs = set()
    sender_totals = {}
    receiver_totals = {}

    for col in df_sender.columns:
        pair = _extract_pair(col)
        all_pairs.add(pair)
        sender_totals[pair] = df_sender[col].sum()

    for col in df_receiver.columns:
        pair = _extract_pair(col)
        all_pairs.add(pair)
        receiver_totals[pair] = df_receiver[col].sum()

    # Build aligned DataFrame
    totals = []
    pairs = []
    for pair in sorted(all_pairs):
        s = sender_totals.get(pair, 0.0)
        r = receiver_totals.get(pair, 0.0)
        totals.append({
            'lr_pair': pair,
            'sender_total': s,
            'receiver_total': r,
            'total': s + r,
        })

    df = pd.DataFrame(totals)
    df = df.sort_values(by, ascending=False).head(n)

    return df


def export_results(
    adata: AnnData,
    output_dir: str,
    database_name: str = 'cellchat',
    include_matrices: bool = False,
) -> None:
    """
    Export COMMOT results to files.

    Parameters
    ----------
    adata : AnnData
        Data with COMMOT results
    output_dir : str
        Directory to save results
    database_name : str, default='cellchat'
        Database name used in run_commot()
    include_matrices : bool, default=False
        Whether to export full communication matrices (can be large)

    Examples
    --------
    >>> export_results(adata, './commot_output', database_name='cellchat')
    """
    import os
    os.makedirs(output_dir, exist_ok=True)

    # Export summary
    try:
        df_sender = get_communication_summary(adata, 'sender', database_name)
        df_sender.to_csv(os.path.join(output_dir, f'{database_name}_sender_summary.csv'))

        df_receiver = get_communication_summary(adata, 'receiver', database_name)
        df_receiver.to_csv(os.path.join(output_dir, f'{database_name}_receiver_summary.csv'))

        print(f"Exported summaries to {output_dir}")
    except KeyError:
        print("No summary data found to export")

    # Export top pairs
    try:
        df_top = get_top_lr_pairs(adata, n=50, database_name=database_name)
        df_top.to_csv(os.path.join(output_dir, f'{database_name}_top_pairs.csv'), index=False)
    except (KeyError, ValueError):
        pass

    # Export communication matrices if requested
    if include_matrices:
        matrices_dir = os.path.join(output_dir, 'matrices')
        os.makedirs(matrices_dir, exist_ok=True)

        prefix = f'commot-{database_name}'
        for k in adata.obsp.keys():
            if k.startswith(prefix):
                matrix = adata.obsp[k]
                pair_name = k[len(prefix)+1:]  # strip 'commot-{name}-'
                # Save as sparse matrix
                from scipy.sparse import save_npz
                save_npz(
                    os.path.join(matrices_dir, f'{pair_name}.npz'),
                    matrix
                )
        print(f"Exported matrices to {matrices_dir}")

    # Export cluster communication if available
    prefix_cluster = f'commot_cluster-'
    for k in adata.uns.keys():
        if k.startswith(prefix_cluster) and database_name in k:
            if isinstance(adata.uns[k], dict) and 'communication_matrix' in adata.uns[k]:
                comm_matrix = adata.uns[k]['communication_matrix']
                safe_name = k.replace('/', '_')
                # Defensively convert to DataFrame (COMMOT may return ndarray)
                if hasattr(comm_matrix, 'to_csv'):
                    comm_matrix.to_csv(os.path.join(output_dir, f'{safe_name}_cluster_comm.csv'))
                else:
                    pd.DataFrame(comm_matrix).to_csv(
                        os.path.join(output_dir, f'{safe_name}_cluster_comm.csv')
                    )

    print(f"Results exported to {output_dir}")
