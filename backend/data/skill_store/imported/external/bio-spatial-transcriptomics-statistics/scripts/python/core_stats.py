"""
Core Spatial Autocorrelation Statistics

This module provides fundamental spatial autocorrelation statistics for
spatial transcriptomics data analysis.

Methods:
    - Moran's I: Global spatial autocorrelation
    - Geary's C: Global spatial heterogeneity (complementary to Moran's I)
    - LISA: Local Indicators of Spatial Association
    - Bivariate Moran's I: Spatial correlation between two variables
"""

import numpy as np
import pandas as pd
from typing import Optional, Union, List, Dict, Tuple
import warnings


def compute_morans_i(
    adata,
    genes: Optional[List[str]] = None,
    k: int = 6,
    use_weights: bool = True,
    layer: Optional[str] = None
) -> pd.DataFrame:
    """
    Compute Moran's I statistic for spatial autocorrelation.

    Moran's I measures the degree of spatial clustering in gene expression.
    Values range from -1 (dispersed) to 1 (clustered), with 0 indicating
    random spatial distribution.

    Parameters
    ----------
    adata : AnnData
        Spatial transcriptomics data with coordinates in adata.obsm['spatial']
    genes : list, optional
        List of genes to test. If None, tests all highly variable genes
        or all genes if HVGs not computed.
    k : int, default=6
        Number of nearest neighbors for spatial weights
    use_weights : bool, default=True
        Whether to row-standardize the spatial weights matrix
    layer : str, optional
        Which layer to use. If None, uses adata.X

    Returns
    -------
    pd.DataFrame
        DataFrame with columns:
        - gene: Gene name
        - I: Moran's I statistic
        - p_value: Two-tailed p-value
        - z_score: Standardized z-score
        - expected_I: Expected value under null hypothesis (-1/(n-1))

    References
    ----------
    Moran, P.A.P. (1950). Notes on continuous stochastic phenomena.
    Biometrika, 37(1/2), 17-23.

    Example
    -------
    >>> results = compute_morans_i(adata, genes=['GeneA', 'GeneB'], k=6)
    >>> print(results.head())
         gene         I   p_value    z_score  expected_I
    0  GeneA  0.523456  0.000001  12.345678   -0.000101
    1  GeneB  0.234567  0.012345   2.456789   -0.000101
    """
    try:
        from libpysal.weights import KNN
        from esda.moran import Moran
    except ImportError:
        raise ImportError(
            "libpysal and esda are required for Moran's I computation. "
            "Install: pip install libpysal esda"
        )

    # Get expression data
    if layer is not None:
        X = adata.layers[layer]
    else:
        X = adata.X

    # Convert to dense if sparse
    if hasattr(X, 'toarray'):
        X = X.toarray()

    # Determine genes to test
    if genes is None:
        if 'highly_variable' in adata.var.columns:
            genes = adata.var_names[adata.var['highly_variable']].tolist()
        else:
            genes = adata.var_names.tolist()
    else:
        # Filter to genes that exist
        genes = [g for g in genes if g in adata.var_names]

    if len(genes) == 0:
        raise ValueError("No valid genes found")

    # Get spatial coordinates
    coords = adata.obsm['spatial']

    # Build spatial weights
    weights = KNN(coords, k=k)
    if use_weights:
        weights.transform = 'r'  # Row-standardize

    results = []
    gene_indices = [adata.var_names.get_loc(g) for g in genes]

    for gene, idx in zip(genes, gene_indices):
        y = X[:, idx]

        # Handle zero-variance genes
        if np.var(y) == 0:
            results.append({
                'gene': gene,
                'I': np.nan,
                'p_value': np.nan,
                'z_score': np.nan,
                'expected_I': -1 / (len(y) - 1)
            })
            continue

        # Compute Moran's I
        mi = Moran(y, weights)

        results.append({
            'gene': gene,
            'I': mi.I,
            'p_value': mi.p_sim if hasattr(mi, 'p_sim') and mi.p_sim is not None else mi.p_norm,
            'z_score': mi.z_sim if hasattr(mi, 'z_sim') and mi.z_sim is not None else mi.z_norm,
            'expected_I': mi.EI
        })

    return pd.DataFrame(results)


def compute_gearys_c(
    adata,
    genes: Optional[List[str]] = None,
    k: int = 6,
    layer: Optional[str] = None
) -> pd.DataFrame:
    """
    Compute Geary's C statistic for spatial heterogeneity.

    Geary's C is complementary to Moran's I. It measures differences between
    neighboring observations, making it sensitive to local spatial variation.
    Values range from 0 (high positive spatial autocorrelation) to values
    potentially >1 (negative spatial autocorrelation), with ~1 indicating
    random distribution.

    Parameters
    ----------
    adata : AnnData
        Spatial transcriptomics data
    genes : list, optional
        List of genes to test. If None, uses HVGs or all genes.
    k : int, default=6
        Number of nearest neighbors
    layer : str, optional
        Which layer to use. If None, uses adata.X

    Returns
    -------
    pd.DataFrame
        DataFrame with columns:
        - gene: Gene name
        - C: Geary's C statistic
        - p_value: Two-tailed p-value
        - z_score: Standardized z-score
        - expected_C: Expected value under null hypothesis (1.0)

    References
    ----------
    Geary, R.C. (1954). The contiguity ratio and statistical mapping.
    The Incorporated Statistician, 5(3), 115-146.

    Example
    -------
    >>> results = compute_gearys_c(adata, genes=['GeneA'], k=6)
    >>> print(results.head())
         gene         C   p_value    z_score  expected_C
    0  GeneA  0.456789  0.000001 -15.678901         1.0

    Notes
    -----
    C < 1: Positive spatial autocorrelation (similar values cluster)
    C = 1: Random spatial distribution
    C > 1: Negative spatial autocorrelation (dissimilar values cluster)
    """
    try:
        from libpysal.weights import KNN
        from esda.geary import Geary
    except ImportError:
        raise ImportError(
            "libpysal and esda are required for Geary's C computation. "
            "Install: pip install libpysal esda"
        )

    # Get expression data
    if layer is not None:
        X = adata.layers[layer]
    else:
        X = adata.X

    if hasattr(X, 'toarray'):
        X = X.toarray()

    # Determine genes
    if genes is None:
        if 'highly_variable' in adata.var.columns:
            genes = adata.var_names[adata.var['highly_variable']].tolist()
        else:
            genes = adata.var_names.tolist()
    else:
        genes = [g for g in genes if g in adata.var_names]

    if len(genes) == 0:
        raise ValueError("No valid genes found")

    # Build spatial weights
    coords = adata.obsm['spatial']
    weights = KNN(coords, k=k)
    weights.transform = 'r'

    results = []
    gene_indices = [adata.var_names.get_loc(g) for g in genes]

    for gene, idx in zip(genes, gene_indices):
        y = X[:, idx]

        if np.var(y) == 0:
            results.append({
                'gene': gene,
                'C': np.nan,
                'p_value': np.nan,
                'z_score': np.nan,
                'expected_C': 1.0
            })
            continue

        gc = Geary(y, weights)

        results.append({
            'gene': gene,
            'C': gc.C,
            'p_value': gc.p_sim if hasattr(gc, 'p_sim') and gc.p_sim is not None else gc.p_norm,
            'z_score': gc.z_sim if hasattr(gc, 'z_sim') and gc.z_sim is not None else gc.z_norm,
            'expected_C': gc.EC
        })

    return pd.DataFrame(results)


def compute_lisa(
    adata,
    gene: str,
    k: int = 6,
    permutations: int = 999,
    layer: Optional[str] = None
) -> pd.DataFrame:
    """
    Compute Local Indicators of Spatial Association (LISA) for a gene.

    LISA identifies local spatial clusters and outliers. Each spot is classified
    into one of four categories based on its value and its neighbors' values:
    - HH: High values surrounded by high values (hot spot)
    - LL: Low values surrounded by low values (cold spot)
    - HL: High values surrounded by low values (spatial outlier)
    - LH: Low values surrounded by high values (spatial outlier)

    Parameters
    ----------
    adata : AnnData
        Spatial transcriptomics data
    gene : str
        Gene to analyze
    k : int, default=6
        Number of nearest neighbors
    permutations : int, default=999
        Number of permutations for significance testing
    layer : str, optional
        Which layer to use. If None, uses adata.X

    Returns
    -------
    pd.DataFrame
        DataFrame with columns:
        - spot_id: Spot identifier
        - local_moran: Local Moran's I value
        - p_value: Significance value
        - z_score: Standardized local statistic
        - cluster: Spatial cluster type (HH, LL, HL, LH, NS)
        - expression: Expression value at spot

    References
    ----------
    Anselin, L. (1995). Local indicators of spatial association—LISA.
    Geographical Analysis, 27(2), 93-115.

    Example
    -------
    >>> results = compute_lisa(adata, gene='GeneA', k=6)
    >>> print(results.head())
      spot_id  local_moran   p_value   z_score cluster  expression
    0    spot_0     0.123456  0.012345  2.345678      HH    1.234567
    1    spot_1    -0.234567  0.045678 -1.987654      HL    2.345678
    """
    try:
        from libpysal.weights import KNN
        from esda.moran import Moran_Local
    except ImportError:
        raise ImportError(
            "libpysal and esda are required for LISA computation. "
            "Install: pip install libpysal esda"
        )

    if gene not in adata.var_names:
        raise ValueError(f"Gene '{gene}' not found in adata")

    # Get expression data
    if layer is not None:
        X = adata.layers[layer]
    else:
        X = adata.X

    if hasattr(X, 'toarray'):
        X = X.toarray()

    gene_idx = adata.var_names.get_loc(gene)
    y = X[:, gene_idx]

    # Build spatial weights
    coords = adata.obsm['spatial']
    weights = KNN(coords, k=k)
    weights.transform = 'r'

    # Compute LISA
    lisa = Moran_Local(y, weights, permutations=permutations)

    # Map cluster codes to labels
    # Moran_Local codes: 0=not significant, 1=HH, 2=LH, 3=LL, 4=HL
    cluster_map = {0: 'NS', 1: 'HH', 2: 'LH', 3: 'LL', 4: 'HL'}
    clusters = [cluster_map[c] for c in lisa.q]

    results = pd.DataFrame({
        'spot_id': adata.obs_names,
        'local_moran': lisa.Is,
        'p_value': lisa.p_sim,
        'z_score': lisa.z_sim if hasattr(lisa, 'z_sim') else np.nan,
        'cluster': clusters,
        'expression': y
    })

    return results


def compute_bivariate_moran(
    adata,
    var1: str,
    var2: str,
    var1_layer: Optional[str] = None,
    var2_layer: Optional[str] = None,
    k: int = 6
) -> Dict:
    """
    Compute Bivariate Moran's I for spatial correlation between two variables.

    Bivariate Moran's I measures the degree to which values of one variable
    at a location are correlated with the average values of another variable
    at neighboring locations. This is useful for examining co-expression
    patterns in spatial context.

    Parameters
    ----------
    adata : AnnData
        Spatial transcriptomics data
    var1 : str
        First variable (gene name or column in adata.obs)
    var2 : str
        Second variable (gene name or column in adata.obs)
    var1_layer : str, optional
        Layer for var1 if it's a gene
    var2_layer : str, optional
        Layer for var2 if it's a gene
    k : int, default=6
        Number of nearest neighbors

    Returns
    -------
    dict
        Dictionary with keys:
        - I: Bivariate Moran's I statistic
        - p_value: Two-tailed p-value
        - z_score: Standardized z-score
        - n: Number of observations
        - expected_I: Expected value under null

    References
    ----------
    Anselin, L., Syabri, I., & Smirnov, O. (2002). Visualizing multivariate
    spatial correlation with dynamically linked windows. In Proceedings of the
    CSISS Workshop on New Tools for Spatial Data Analysis.

    Example
    -------
    >>> result = compute_bivariate_moran(adata, var1='GeneA', var2='GeneB', k=6)
    >>> print(f"I = {result['I']:.3f}, p = {result['p_value']:.3e}")
    I = 0.456, p = 1.234e-05
    """
    try:
        from libpysal.weights import KNN
        from esda.moran import Moran_BV
    except ImportError:
        raise ImportError(
            "libpysal and esda are required for Bivariate Moran's I. "
            "Install: pip install libpysal esda"
        )

    # Get variable values
    def get_values(var, layer):
        if var in adata.var_names:
            # It's a gene
            if layer is not None:
                X = adata.layers[layer]
            else:
                X = adata.X
            if hasattr(X, 'toarray'):
                X = X.toarray()
            return X[:, adata.var_names.get_loc(var)]
        elif var in adata.obs.columns:
            # It's an observation annotation
            return adata.obs[var].values
        else:
            raise ValueError(f"Variable '{var}' not found in genes or obs")

    x = get_values(var1, var1_layer)
    y = get_values(var2, var2_layer)

    # Build spatial weights
    coords = adata.obsm['spatial']
    weights = KNN(coords, k=k)
    weights.transform = 'r'

    # Compute bivariate Moran's I
    # Moran_BV computes correlation between x at i and y at neighbors of i
    moran_bv = Moran_BV(x, y, weights)

    return {
        'I': moran_bv.I,
        'p_value': moran_bv.p_sim if hasattr(moran_bv, 'p_sim') else moran_bv.p_norm,
        'z_score': moran_bv.z_sim if hasattr(moran_bv, 'z_sim') else moran_bv.z_norm,
        'n': len(x),
        'expected_I': moran_bv.EI if hasattr(moran_bv, 'EI') else -1 / (len(x) - 1)
    }


def compare_morans_geary(
    adata,
    genes: Optional[List[str]] = None,
    k: int = 6,
    alpha: float = 0.05
) -> pd.DataFrame:
    """
    Compare Moran's I and Geary's C statistics for the same genes.

    This function computes both statistics and provides a comparative analysis,
    highlighting genes where the two measures agree or disagree about spatial
    autocorrelation.

    Parameters
    ----------
    adata : AnnData
        Spatial transcriptomics data
    genes : list, optional
        List of genes to test. If None, uses HVGs or all genes.
    k : int, default=6
        Number of nearest neighbors
    alpha : float, default=0.05
        Significance threshold

    Returns
    -------
    pd.DataFrame
        DataFrame with columns:
        - gene: Gene name
        - moran_I: Moran's I statistic
        - moran_p: Moran's I p-value
        - geary_C: Geary's C statistic
        - geary_p: Geary's C p-value
        - agreement: Whether both tests agree on significance
        - interpretation: Human-readable interpretation

    Example
    -------
    >>> results = compare_morans_geary(adata, genes=['GeneA', 'GeneB'])
    >>> print(results[['gene', 'moran_I', 'geary_C', 'interpretation']])
         gene   moran_I   geary_C      interpretation
    0  GeneA  0.523456  0.456789  Strong clustering
    1  GeneB -0.123456  1.234567  Dispersed pattern
    """
    # Compute both statistics
    moran_results = compute_morans_i(adata, genes=genes, k=k)
    geary_results = compute_gearys_c(adata, genes=genes, k=k)

    # Merge results
    merged = moran_results.merge(
        geary_results[['gene', 'C', 'p_value', 'z_score']],
        on='gene',
        suffixes=('_moran', '_geary')
    )

    # Rename columns
    merged = merged.rename(columns={
        'p_value_moran': 'moran_p',
        'z_score_moran': 'moran_z',
        'p_value_geary': 'geary_p',
        'z_score_geary': 'geary_z',
        'C': 'geary_C',
        'I': 'moran_I'
    })

    # Determine agreement
    merged['moran_significant'] = merged['moran_p'] < alpha
    merged['geary_significant'] = merged['geary_p'] < alpha
    merged['agreement'] = merged['moran_significant'] == merged['geary_significant']

    # Generate interpretation
    def interpret(row):
        if row['moran_significant'] and row['geary_significant']:
            if row['moran_I'] > 0 and row['geary_C'] < 1:
                return "Strong spatial clustering"
            elif row['moran_I'] < 0 and row['geary_C'] > 1:
                return "Spatial dispersion"
            else:
                return "Complex spatial pattern"
        elif row['moran_significant']:
            return "Moran's I detects pattern"
        elif row['geary_significant']:
            return "Geary's C detects pattern"
        else:
            return "No significant pattern"

    merged['interpretation'] = merged.apply(interpret, axis=1)

    return merged


def run_autocorrelation_analysis(
    adata,
    genes: Optional[List[str]] = None,
    k: int = 6,
    compute_local: bool = False,
    top_genes: int = 10,
    layer: Optional[str] = None
) -> Dict:
    """
    Run comprehensive spatial autocorrelation analysis.

    This function provides a unified interface to run multiple spatial
    autocorrelation tests and return combined results.

    Parameters
    ----------
    adata : AnnData
        Spatial transcriptomics data
    genes : list, optional
        List of genes to test. If None, uses HVGs.
    k : int, default=6
        Number of nearest neighbors
    compute_local : bool, default=False
        Whether to also compute LISA for top genes (slower)
    top_genes : int, default=10
        Number of top genes for LISA if compute_local=True
    layer : str, optional
        Which layer to use

    Returns
    -------
    dict
        Dictionary containing:
        - 'moran': Moran's I results (DataFrame)
        - 'geary': Geary's C results (DataFrame)
        - 'comparison': Comparison of both statistics (DataFrame)
        - 'lisa': LISA results for top genes (dict of DataFrames, optional)
        - 'top_clustered': Top spatially clustered genes
        - 'top_dispersed': Top spatially dispersed genes

    Example
    -------
    >>> results = run_autocorrelation_analysis(adata, k=6, compute_local=True)
    >>> print(f"Top clustered gene: {results['top_clustered'][0]}")
    >>> print(results['moran'].head())
    """
    # Compute global statistics
    print("Computing Moran's I...")
    moran_results = compute_morans_i(adata, genes=genes, k=k, layer=layer)

    print("Computing Geary's C...")
    geary_results = compute_gearys_c(adata, genes=genes, k=k, layer=layer)

    print("Comparing statistics...")
    comparison = compare_morans_geary(adata, genes=genes, k=k)

    results = {
        'moran': moran_results,
        'geary': geary_results,
        'comparison': comparison,
        'top_clustered': [],
        'top_dispersed': [],
        'lisa': {}
    }

    # Identify top clustered genes
    sig_moran = moran_results[moran_results['p_value'] < 0.05]
    if len(sig_moran) > 0:
        clustered = sig_moran.nlargest(top_genes, 'I')['gene'].tolist()
        results['top_clustered'] = clustered

        dispersed = sig_moran.nsmallest(top_genes, 'I')['gene'].tolist()
        results['top_dispersed'] = dispersed

    # Compute LISA for top genes if requested
    if compute_local and len(results['top_clustered']) > 0:
        print("Computing LISA for top clustered genes...")
        for gene in results['top_clustered'][:5]:  # Limit to top 5
            try:
                lisa_df = compute_lisa(adata, gene=gene, k=k, layer=layer)
                results['lisa'][gene] = lisa_df
            except Exception as e:
                warnings.warn(f"Failed to compute LISA for {gene}: {e}")

    return results
