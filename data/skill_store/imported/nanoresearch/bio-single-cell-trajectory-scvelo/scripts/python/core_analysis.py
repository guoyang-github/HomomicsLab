"""
Core Analysis Functions for scVelo RNA Velocity Analysis

This module provides wrapper functions for:
- RNA velocity estimation (deterministic, stochastic, dynamical modes)
- Velocity graph construction
- Latent time inference
- Gene dynamics analysis

Author: Yang Guo
Date: 2026-04-03
"""

import numpy as np
import pandas as pd
import scanpy as sc
from typing import Optional, List, Dict, Union, Tuple
import warnings

#==============================================================================
# Data Preparation
#==============================================================================

def prepare_data_for_velocity(
    adata: sc.AnnData,
    min_counts: int = 10,
    min_counts_u: int = 10,
    n_top_genes: int = 2000,
    n_pcs: int = 30,
    n_neighbors: int = 30,
    copy: bool = False,
    verbose: bool = True
) -> Optional[sc.AnnData]:
    """
    Prepare data for RNA velocity analysis.

    This function performs the standard preprocessing pipeline for scVelo:
    filtering, normalization, moments computation, and PCA/neighbors.

    Parameters
    ----------
    adata : sc.AnnData
        Annotated data with 'spliced' and 'unspliced' layers
    min_counts : int, default=10
        Minimum counts for spliced matrix
    min_counts_u : int, default=10
        Minimum counts for unspliced matrix
    n_top_genes : int, default=2000
        Number of highly variable genes
    n_pcs : int, default=30
        Number of principal components
    n_neighbors : int, default=30
        Number of neighbors for moments
    copy : bool, default=False
        Return copy of adata
    verbose : bool, default=True
        Print progress

    Returns
    -------
    sc.AnnData or None
        Preprocessed data if copy=True

    Examples
    --------
    >>> adata = prepare_data_for_velocity(adata, n_top_genes=3000)
    """
    try:
        import scvelo as scv
    except ImportError:
        raise ImportError("scvelo is required. Install with: pip install scvelo")

    if copy:
        adata = adata.copy()

    if verbose:
        print("Preparing data for RNA velocity analysis...")
        print(f"  Input: {adata.n_obs} cells, {adata.n_vars} genes")

    # Check for required layers
    required_layers = ['spliced', 'unspliced']
    missing = [layer for layer in required_layers if layer not in adata.layers]
    if missing:
        raise ValueError(f"Missing required layers: {missing}")

    # Filter and normalize
    # NOTE: scv.pp.filter_and_normalize was removed in scvelo 0.3+.
    # Using equivalent scanpy functions instead.
    sc.pp.filter_cells(adata, min_counts=min_counts)
    sc.pp.filter_genes(adata, min_counts=min_counts)
    if n_top_genes is not None and n_top_genes > 0:
        sc.pp.highly_variable_genes(adata, n_top_genes=n_top_genes, subset=True)
    sc.pp.normalize_total(adata, target_sum=1e4)
    sc.pp.log1p(adata)

    if verbose:
        print(f"  After filtering: {adata.n_obs} cells, {adata.n_vars} genes")

    # Compute moments
    scv.pp.moments(adata, n_pcs=n_pcs, n_neighbors=n_neighbors)

    if verbose:
        print("  Preprocessing complete")

    if copy:
        return adata


def check_velocity_layers(adata: sc.AnnData) -> Dict[str, bool]:
    """
    Check if adata has required layers for RNA velocity analysis.

    Parameters
    ----------
    adata : sc.AnnData
        Input data

    Returns
    -------
    Dict[str, bool]
        Dictionary indicating presence of each layer
    """
    layers = {
        'spliced': 'spliced' in adata.layers,
        'unspliced': 'unspliced' in adata.layers,
        'Ms': 'Ms' in adata.layers,
        'Mu': 'Mu' in adata.layers,
        'velocity': 'velocity' in adata.layers,
        'velocity_graph': 'velocity_graph' in adata.uns
    }
    return layers


#==============================================================================
# Velocity Estimation
#==============================================================================

def compute_velocity(
    adata: sc.AnnData,
    mode: str = 'stochastic',
    fit_offset: bool = False,
    fit_offset2: bool = False,
    min_r2: float = 0.01,
    min_ratio: float = 0.01,
    min_likelihood: float = 0.1,
    use_highly_variable: bool = True,
    copy: bool = False,
    verbose: bool = True
) -> Optional[sc.AnnData]:
    """
    Compute RNA velocity using scVelo.

    Three modes are available:
    - 'deterministic': Steady-state model (fastest, least accurate)
    - 'stochastic': Second-order moments (recommended, good balance)
    - 'dynamical': Full dynamical model (slowest, most accurate)

    Parameters
    ----------
    adata : sc.AnnData
        Preprocessed data with moments
    mode : str, default='stochastic'
        Velocity estimation mode ('deterministic', 'stochastic', 'dynamical')
    fit_offset : bool, default=False
        Fit offset in linear regression
    fit_offset2 : bool, default=False
        Fit offset in second-order moments (stochastic mode)
    min_r2 : float, default=0.01
        Minimum R-squared for velocity genes
    min_ratio : float, default=0.01
        Minimum ratio for velocity genes
    min_likelihood : float, default=0.1
        Minimum likelihood for velocity genes
    use_highly_variable : bool, default=True
        Use only highly variable genes
    copy : bool, default=False
        Return copy of adata
    verbose : bool, default=True
        Print progress

    Returns
    -------
    sc.AnnData or None
        Data with velocity if copy=True

    Examples
    --------
    >>> adata = compute_velocity(adata, mode='dynamical')
    """
    try:
        import scvelo as scv
    except ImportError:
        raise ImportError("scvelo is required")

    if mode not in ['deterministic', 'stochastic', 'dynamical']:
        raise ValueError(f"Invalid mode: {mode}")

    if verbose:
        print(f"Computing RNA velocity (mode: {mode})...")

    if copy:
        adata = adata.copy()

    # Compute velocity
    scv.tl.velocity(
        adata,
        mode=mode,
        fit_offset=fit_offset,
        fit_offset2=fit_offset2,
        min_r2=min_r2,
        min_likelihood=min_likelihood,
        use_highly_variable=use_highly_variable
    )

    # Get velocity genes info
    n_velocity_genes = np.sum(adata.var['velocity_genes']) if 'velocity_genes' in adata.var else 0

    if verbose:
        print(f"  Velocity computed for {n_velocity_genes} genes")

    if copy:
        return adata


def compute_velocity_graph(
    adata: sc.AnnData,
    n_neighbors: Optional[int] = None,
    n_jobs: int = -1,
    copy: bool = False,
    verbose: bool = True
) -> Optional[sc.AnnData]:
    """
    Compute velocity graph based on cosine similarities.

    The velocity graph represents transitions between cells based on
    RNA velocity directions.

    Parameters
    ----------
    adata : sc.AnnData
        Data with velocity
    n_neighbors : Optional[int], default=None
        Number of neighbors (default: from neighbors graph)
    n_jobs : int, default=-1
        Number of parallel jobs
    copy : bool, default=False
        Return copy of adata
    verbose : bool, default=True
        Print progress

    Returns
    -------
    sc.AnnData or None
        Data with velocity_graph if copy=True
    """
    try:
        import scvelo as scv
    except ImportError:
        raise ImportError("scvelo is required")

    if verbose:
        print("Computing velocity graph...")

    if copy:
        adata = adata.copy()

    scv.tl.velocity_graph(adata, n_neighbors=n_neighbors, n_jobs=n_jobs)

    if verbose:
        print("  Velocity graph computed")

    if copy:
        return adata


def run_velocity_analysis(
    adata: sc.AnnData,
    mode: str = 'stochastic',
    n_top_genes: int = 2000,
    n_pcs: int = 30,
    n_neighbors: int = 30,
    compute_latent_time: bool = True,
    copy: bool = False,
    verbose: bool = True
) -> Optional[sc.AnnData]:
    """
    Complete RNA velocity analysis pipeline.

    Runs the full workflow: preprocessing -> velocity -> velocity graph -> latent time.

    Parameters
    ----------
    adata : sc.AnnData
        Raw data with spliced/unspliced layers
    mode : str, default='stochastic'
        Velocity estimation mode
    n_top_genes : int, default=2000
        Number of highly variable genes
    n_pcs : int, default=30
        Number of PCs for moments
    n_neighbors : int, default=30
        Number of neighbors
    compute_latent_time : bool, default=True
        Compute latent time
    copy : bool, default=False
        Return copy of adata
    verbose : bool, default=True
        Print progress

    Returns
    -------
    sc.AnnData or None
        Data with complete velocity analysis if copy=True

    Examples
    --------
    >>> adata = run_velocity_analysis(adata, mode='dynamical', n_top_genes=3000)
    """
    if copy:
        adata = adata.copy()

    # Preprocessing
    prepare_data_for_velocity(
        adata,
        n_top_genes=n_top_genes,
        n_pcs=n_pcs,
        n_neighbors=n_neighbors,
        copy=False,
        verbose=verbose
    )

    # Velocity
    compute_velocity(adata, mode=mode, copy=False, verbose=verbose)

    # Velocity graph
    compute_velocity_graph(adata, copy=False, verbose=verbose)

    # Latent time
    if compute_latent_time:
        compute_latent_time_scvelo(adata, copy=False, verbose=verbose)

    if verbose:
        print("\nRNA velocity analysis complete!")

    if copy:
        return adata


#==============================================================================
# Latent Time and Pseudotime
#==============================================================================

def compute_latent_time_scvelo(
    adata: sc.AnnData,
    min_likelihood: float = 0.1,
    min_confidence: float = 0.75,
    root_key: Optional[str] = None,
    end_key: Optional[str] = None,
    copy: bool = False,
    verbose: bool = True
) -> Optional[sc.AnnData]:
    """
    Compute latent time based on velocity-inferred dynamics.

    Latent time represents the progression through a dynamic process
    (e.g., differentiation) inferred from RNA velocity.

    Parameters
    ----------
    adata : sc.AnnData
        Data with velocity and velocity_graph
    min_likelihood : float, default=0.1
        Minimum likelihood for velocity genes
    min_confidence : float, default=0.75
        Minimum confidence for root/end identification
    root_key : Optional[str], default=None
        Key for root cells in adata.obs
    end_key : Optional[str], default=None
        Key for end cells in adata.obs
    copy : bool, default=False
        Return copy of adata
    verbose : bool, default=True
        Print progress

    Returns
    -------
    sc.AnnData or None
        Data with latent_time if copy=True
    """
    try:
        import scvelo as scv
    except ImportError:
        raise ImportError("scvelo is required")

    if verbose:
        print("Computing latent time...")

    if copy:
        adata = adata.copy()

    scv.tl.latent_time(
        adata,
        min_likelihood=min_likelihood,
        min_confidence=min_confidence,
        root_key=root_key,
        end_key=end_key
    )

    if verbose:
        print("  Latent time computed")

    if copy:
        return adata


def compute_terminal_states(
    adata: sc.AnnData,
    vkey: str = 'velocity',
    groupby: Optional[str] = None,
    copy: bool = False,
    verbose: bool = True
) -> Optional[sc.AnnData]:
    """
    Identify terminal states (root and end points) from velocity.

    Parameters
    ----------
    adata : sc.AnnData
        Data with velocity_graph
    vkey : str, default='velocity'
        Key for velocity
    groupby : Optional[str], default=None
        Key for grouping
    copy : bool, default=False
        Return copy of adata
    verbose : bool, default=True
        Print progress

    Returns
    -------
    sc.AnnData or None
        Data with terminal_states if copy=True
    """
    try:
        import scvelo as scv
    except ImportError:
        raise ImportError("scvelo is required")

    if verbose:
        print("Identifying terminal states...")

    if copy:
        adata = adata.copy()

    scv.tl.terminal_states(adata, vkey=vkey, groupby=groupby)

    if verbose:
        print("  Terminal states identified")

    if copy:
        return adata


#==============================================================================
# Velocity Confidence and Gene Analysis
#==============================================================================

def compute_velocity_confidence(
    adata: sc.AnnData,
    vkey: str = 'velocity',
    copy: bool = False,
    verbose: bool = True
) -> Optional[sc.AnnData]:
    """
    Compute velocity confidence scores.

    Confidence scores indicate how reliable the velocity estimate is
    for each cell.

    Parameters
    ----------
    adata : sc.AnnData
        Data with velocity
    vkey : str, default='velocity'
        Key for velocity
    copy : bool, default=False
        Return copy of adata
    verbose : bool, default=True
        Print progress

    Returns
    -------
    sc.AnnData or None
        Data with velocity_confidence if copy=True
    """
    try:
        import scvelo as scv
    except ImportError:
        raise ImportError("scvelo is required")

    if verbose:
        print("Computing velocity confidence...")

    if copy:
        adata = adata.copy()

    scv.tl.velocity_confidence(adata, vkey=vkey)

    if verbose:
        print("  Velocity confidence computed")

    if copy:
        return adata


def rank_velocity_genes(
    adata: sc.AnnData,
    vkey: str = 'velocity',
    n_genes: int = 100,
    groupby: Optional[str] = None,
    min_corr: Optional[float] = None,
    copy: bool = False,
    verbose: bool = True
) -> Optional[pd.DataFrame]:
    """
    Rank genes by velocity likelihood.

    Parameters
    ----------
    adata : sc.AnnData
        Data with velocity
    vkey : str, default='velocity'
        Key for velocity
    n_genes : int, default=100
        Number of top genes to return
    groupby : Optional[str], default=None
        Key for grouping
    min_corr : Optional[float], default=None
        Minimum correlation threshold
    copy : bool, default=False
        Return copy of adata
    verbose : bool, default=True
        Print progress

    Returns
    -------
    pd.DataFrame or None
        Ranked genes if copy=True
    """
    try:
        import scvelo as scv
    except ImportError:
        raise ImportError("scvelo is required")

    if verbose:
        print(f"Ranking velocity genes (top {n_genes})...")

    if copy:
        adata = adata.copy()

    scv.tl.rank_velocity_genes(
        adata,
        vkey=vkey,
        n_genes=n_genes,
        groupby=groupby,
        min_corr=min_corr
    )

    if verbose:
        print("  Genes ranked")

    if copy:
        return adata.uns.get('rank_velocity_genes')


def get_top_velocity_genes(
    adata: sc.AnnData,
    n_genes: int = 10,
    velocity_key: str = 'velocity'
) -> pd.DataFrame:
    """
    Get top velocity genes sorted by fit likelihood.

    Parameters
    ----------
    adata : sc.AnnData
        Data with velocity
    n_genes : int, default=10
        Number of top genes
    velocity_key : str, default='velocity'
        Key for velocity

    Returns
    -------
    pd.DataFrame
        Top velocity genes with fit statistics
    """
    if 'velocity_genes' not in adata.var:
        raise ValueError("Velocity genes not computed. Run compute_velocity first.")

    # Get velocity genes
    velocity_genes = adata.var[adata.var['velocity_genes']].copy()

    # Sort by fit likelihood if available
    if 'fit_likelihood' in velocity_genes.columns:
        velocity_genes = velocity_genes.sort_values('fit_likelihood', ascending=False)
    elif 'velocity_r2' in velocity_genes.columns:
        velocity_genes = velocity_genes.sort_values('velocity_r2', ascending=False)

    return velocity_genes.head(n_genes)


#==============================================================================
# PAGA Velocity Analysis
#==============================================================================

def compute_paga_velocity(
    adata: sc.AnnData,
    groups: str,
    vkey: str = 'velocity',
    copy: bool = False,
    verbose: bool = True
) -> Optional[sc.AnnData]:
    """
    Compute PAGA velocity graph.

    Combines RNA velocity with PAGA (Partition-based Graph Abstraction)
    for trajectory inference.

    Parameters
    ----------
    adata : sc.AnnData
        Data with velocity and connectivity
    groups : str
        Key in adata.obs for grouping
    vkey : str, default='velocity'
        Key for velocity
    copy : bool, default=False
        Return copy of adata
    verbose : bool, default=True
        Print progress

    Returns
    -------
    sc.AnnData or None
        Data with PAGA velocity if copy=True
    """
    try:
        import scvelo as scv
    except ImportError:
        raise ImportError("scvelo is required")

    if verbose:
        print("Computing PAGA velocity...")

    if copy:
        adata = adata.copy()

    scv.tl.paga(adata, groups=groups, vkey=vkey)

    if verbose:
        print("  PAGA velocity computed")

    if copy:
        return adata


#==============================================================================
# Velocity Embeddings
#==============================================================================

def compute_velocity_embedding(
    adata: sc.AnnData,
    basis: str = 'umap',
    vkey: str = 'velocity',
    copy: bool = False,
    verbose: bool = True
) -> Optional[sc.AnnData]:
    """
    Project velocity onto embedding (e.g., UMAP).

    Parameters
    ----------
    adata : sc.AnnData
        Data with velocity and embedding
    basis : str, default='umap'
        Embedding basis
    vkey : str, default='velocity'
        Key for velocity
    copy : bool, default=False
        Return copy of adata
    verbose : bool, default=True
        Print progress

    Returns
    -------
    sc.AnnData or None
        Data with velocity_embedding if copy=True
    """
    try:
        import scvelo as scv
    except ImportError:
        raise ImportError("scvelo is required")

    if f'X_{basis}' not in adata.obsm:
        raise ValueError(f"Embedding '{basis}' not found. Compute it first.")

    if verbose:
        print(f"Computing velocity embedding on {basis}...")

    if copy:
        adata = adata.copy()

    scv.tl.velocity_embedding(adata, basis=basis, vkey=vkey)

    if verbose:
        print("  Velocity embedding computed")

    if copy:
        return adata


#==============================================================================
# Cell Cycle Analysis
#==============================================================================

def score_cell_cycle(
    adata: sc.AnnData,
    s_genes: Optional[List[str]] = None,
    g2m_genes: Optional[List[str]] = None,
    copy: bool = False,
    verbose: bool = True
) -> Optional[sc.AnnData]:
    """
    Score cell cycle using velocity-based approach.

    Parameters
    ----------
    adata : sc.AnnData
        Data with velocity
    s_genes : Optional[List[str]], default=None
        S phase genes
    g2m_genes : Optional[List[str]], default=None
        G2M phase genes
    copy : bool, default=False
        Return copy of adata
    verbose : bool, default=True
        Print progress

    Returns
    -------
    sc.AnnData or None
        Data with cell cycle scores if copy=True
    """
    try:
        import scvelo as scv
    except ImportError:
        raise ImportError("scvelo is required")

    if verbose:
        print("Scoring cell cycle...")

    if copy:
        adata = adata.copy()

    scv.tl.score_genes_cell_cycle(adata, s_genes=s_genes, g2m_genes=g2m_genes)

    if verbose:
        print("  Cell cycle scored")

    if copy:
        return adata


#==============================================================================
# Export Functions
#==============================================================================

def export_velocity_results(
    adata: sc.AnnData,
    output_dir: str,
    export_layers: bool = True,
    export_obs: bool = True
):
    """
    Export velocity analysis results.

    Parameters
    ----------
    adata : sc.AnnData
        Data with velocity
    output_dir : str
        Output directory
    export_layers : bool, default=True
        Export velocity layers
    export_obs : bool, default=True
        Export velocity-related obs columns
    """
    import os
    os.makedirs(output_dir, exist_ok=True)

    # Export velocity matrix
    if export_layers and 'velocity' in adata.layers:
        velocity_df = pd.DataFrame(
            adata.layers['velocity'],
            index=adata.obs_names,
            columns=adata.var_names
        )
        velocity_df.to_csv(f"{output_dir}/velocity_matrix.csv")

    # Export obs
    if export_obs:
        velocity_obs = adata.obs.filter(regex='velocity|latent_time', axis=1)
        velocity_obs.to_csv(f"{output_dir}/velocity_obs.csv")

    # Export var
    if 'velocity_genes' in adata.var:
        velocity_var = adata.var[adata.var['velocity_genes']]
        velocity_var.to_csv(f"{output_dir}/velocity_genes.csv")

    print(f"Results exported to {output_dir}")


def get_velocity_summary(
    adata: sc.AnnData,
    groupby: Optional[str] = None
) -> pd.DataFrame:
    """
    Get summary statistics of velocity analysis.

    Parameters
    ----------
    adata : sc.AnnData
        Data with velocity
    groupby : Optional[str], default=None
        Key for grouping

    Returns
    -------
    pd.DataFrame
        Summary statistics
    """
    summary = {}

    # Basic stats
    summary['n_cells'] = adata.n_obs
    summary['n_genes'] = adata.n_vars
    summary['n_velocity_genes'] = np.sum(adata.var['velocity_genes']) if 'velocity_genes' in adata.var else 0

    # Velocity stats
    if 'velocity' in adata.layers:
        velocity = adata.layers['velocity']
        summary['velocity_mean'] = np.mean(velocity)
        summary['velocity_std'] = np.std(velocity)

    # Confidence
    if 'velocity_confidence' in adata.obs:
        summary['confidence_mean'] = adata.obs['velocity_confidence'].mean()
        summary['confidence_std'] = adata.obs['velocity_confidence'].std()

    # Latent time
    if 'latent_time' in adata.obs:
        summary['latent_time_range'] = adata.obs['latent_time'].max() - adata.obs['latent_time'].min()

    return pd.DataFrame([summary])
