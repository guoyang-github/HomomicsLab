"""
Comprehensive Spatial Statistics Workflow

This example demonstrates the full range of spatial statistics available
in the bio-spatial-transcriptomics-spatial-statistics skill.

Reference: numpy 1.26+, pandas 2.2+, scanpy 1.10+, scipy 1.12+, squidpy 1.3+,
           esda 2.6+, libpysal 4.12+, networkx 3.2+

Verify API if version differs.
"""

import numpy as np
import pandas as pd
import scanpy as sc
import squidpy as sq
import warnings

# Optional imports for advanced statistics
try:
    from esda.moran import Moran_Local, Moran_BV
    from esda.getisord import G_Local
    from esda.join_counts import Join_Counts
    from libpysal.weights import KNN
    from statsmodels.stats.multitest import multipletests
    PYSAL_AVAILABLE = True
except ImportError:
    PYSAL_AVAILABLE = False
    warnings.warn("PySAL (esda, libpysal) not installed. Some features unavailable.")

try:
    import networkx as nx
    from sklearn.neighbors import kneighbors_graph
    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False
    warnings.warn("NetworkX not installed. Network features unavailable.")


def validate_spatial_data(adata, require_raw=False):
    """
    Validate spatial data for statistical analysis.

    Parameters
    ----------
    adata : AnnData
        Spatial transcriptomics data
    require_raw : bool
        If True, checks that data contains raw counts

    Returns
    -------
    bool : True if validation passes
    """
    if 'spatial' not in adata.obsm:
        raise ValueError("No spatial coordinates found in adata.obsm['spatial']")

    coords = adata.obsm['spatial']
    if np.isnan(coords).any() or np.isinf(coords).any():
        raise ValueError("Spatial coordinates contain NaN or Inf values")

    if require_raw:
        sample = adata.X[:100, :100] if adata.shape[0] > 100 else adata.X
        if hasattr(sample, 'toarray'):
            sample = sample.toarray()
        if sample.min() < 0:
            raise ValueError("Data appears normalized (negative values). Raw counts required.")

    return True


def compute_global_moran(adata, genes=None):
    """Compute global Moran's I for spatial autocorrelation."""
    print("\n=== Computing Global Moran's I ===")

    # Ensure spatial neighbors exist
    if 'spatial_neighbors' not in adata.uns:
        sq.gr.spatial_neighbors(adata, coord_type='generic', n_neighs=6)

    # Compute for specified genes or all
    if genes is not None:
        sq.gr.spatial_autocorr(adata, mode='moran', genes=genes)
    else:
        sq.gr.spatial_autocorr(adata, mode='moran')

    results = adata.uns['moranI']

    # FDR correction
    _, qvals, _, _ = multipletests(results['pval_norm'], method='fdr_bh')
    results['qval'] = qvals

    # Summary
    significant = results[results['qval'] < 0.05]
    print(f"Found {len(significant)} significant spatially variable genes (q < 0.05)")
    print("\nTop 10 spatially variable genes:")
    print(significant.head(10)[['I', 'qval']])

    return results


def compute_getis_ord_gi(adata, gene, k=6, n_permutations=999):
    """
    Compute Getis-Ord Gi* for hotspot detection.

    Returns hotspot classifications added to adata.obs.
    """
    if not PYSAL_AVAILABLE:
        raise ImportError("PySAL required for Getis-Ord Gi*")

    print(f"\n=== Computing Getis-Ord Gi* for {gene} ===")

    coords = adata.obsm['spatial']
    w = KNN.from_array(coords, k=k)
    w.transform = 'r'

    expr = adata[:, gene].X.toarray().flatten()
    gstar = G_Local(expr, w, permutations=n_permutations)

    # Add results to adata
    adata.obs[f'{gene}_gstar_z'] = gstar.Zs
    adata.obs[f'{gene}_gstar_p'] = gstar.p_sim

    # FDR correction
    _, qvals, _, _ = multipletests(gstar.p_sim, method='fdr_bh')
    adata.obs[f'{gene}_gstar_q'] = qvals

    # Categorize hotspots/coldspots
    categories = []
    for z, q in zip(gstar.Zs, qvals):
        if q < 0.05:
            categories.append('Hotspot' if z > 0 else 'Coldspot')
        else:
            categories.append('Not significant')
    adata.obs[f'{gene}_hotspot'] = pd.Categorical(categories)

    # Summary
    hotspot_counts = adata.obs[f'{gene}_hotspot'].value_counts()
    print(f"\nHotspot analysis for {gene}:")
    print(hotspot_counts)

    return gstar


def compute_lisa(adata, gene, k=6, n_permutations=999):
    """
    Compute Local Moran's I (LISA) with quadrant classification.

    Adds LISA statistics and quadrant classifications to adata.obs.
    """
    if not PYSAL_AVAILABLE:
        raise ImportError("PySAL required for LISA")

    print(f"\n=== Computing LISA for {gene} ===")

    coords = adata.obsm['spatial']
    w = KNN.from_array(coords, k=k)
    w.transform = 'r'

    gene_expr = adata[:, gene].X.toarray().flatten()
    lisa = Moran_Local(gene_expr, w, permutations=n_permutations)

    # Add to adata
    adata.obs[f'{gene}_lisa_I'] = lisa.Is
    adata.obs[f'{gene}_lisa_p'] = lisa.p_sim

    # FDR correction
    _, qvals, _, _ = multipletests(lisa.p_sim, method='fdr_bh')
    adata.obs[f'{gene}_lisa_q'] = qvals

    # Quadrant labels
    quadrant_map = {1: 'HH', 2: 'LH', 3: 'LL', 4: 'HL'}
    adata.obs[f'{gene}_lisa_quadrant'] = [quadrant_map.get(q, 'NA') for q in lisa.q]

    # Significant quadrants only
    sig_quadrants = []
    for q, p in zip(lisa.q, qvals):
        if p < 0.05:
            sig_quadrants.append(quadrant_map.get(q, 'NA'))
        else:
            sig_quadrants.append('Not significant')
    adata.obs[f'{gene}_lisa_sig'] = pd.Categorical(sig_quadrants)

    # Summary
    sig_summary = adata.obs[f'{gene}_lisa_sig'].value_counts()
    print(f"\nLISA quadrant analysis for {gene}:")
    print(sig_summary)

    return lisa


def compute_bivariate_moran(adata, gene1, gene2, k=6, n_permutations=999):
    """
    Compute bivariate Moran's I for spatial correlation between two genes.
    """
    if not PYSAL_AVAILABLE:
        raise ImportError("PySAL required for bivariate Moran's I")

    print(f"\n=== Computing Bivariate Moran's I: {gene1} vs {gene2} ===")

    coords = adata.obsm['spatial']
    w = KNN.from_array(coords, k=k)
    w.transform = 'r'

    x = adata[:, gene1].X.toarray().flatten()
    y = adata[:, gene2].X.toarray().flatten()

    moran_bv = Moran_BV(x, y, w, permutations=n_permutations)

    result = {
        'I': moran_bv.I,
        'p_value': moran_bv.p_sim,
        'z_score': moran_bv.z_sim,
        'gene1': gene1,
        'gene2': gene2
    }

    print(f"Bivariate Moran's I: {result['I']:.4f}")
    print(f"P-value: {result['p_value']:.2e}")
    print(f"Z-score: {result['z_score']:.4f}")

    return result


def compute_join_counts(adata, cluster_key, k=6, n_permutations=999):
    """
    Compute join count statistics for categorical spatial data.
    """
    if not PYSAL_AVAILABLE:
        raise ImportError("PySAL required for join count statistics")

    print(f"\n=== Computing Join Count Statistics for {cluster_key} ===")

    coords = adata.obsm['spatial']
    w = KNN.from_array(coords, k=k)
    w.transform = 'r'

    results = {}
    clusters = adata.obs[cluster_key].cat.categories

    for cluster in clusters:
        y = (adata.obs[cluster_key] == cluster).astype(int).values
        jc = Join_Counts(y, w, permutations=n_permutations)

        results[cluster] = {
            'bb': jc.bb,
            'ww': jc.ww,
            'bw': jc.bw,
            'p_value': jc.p_sim,
            'n_spots': int(y.sum())
        }

    # Convert to DataFrame
    jc_df = pd.DataFrame(results).T
    jc_df['spatial_pattern'] = jc_df['p_value'].apply(
        lambda p: 'Clustered' if p < 0.05 else 'Random'
    )

    print("\nJoin count analysis by cluster:")
    print(jc_df[['n_spots', 'bb', 'bw', 'p_value', 'spatial_pattern']])

    return results


def compute_spatial_centrality(adata, n_neighbors=6):
    """
    Compute spatial centrality measures for tissue architecture analysis.
    """
    if not NETWORKX_AVAILABLE:
        raise ImportError("NetworkX required for centrality analysis")

    print("\n=== Computing Spatial Centrality ===")

    coords = adata.obsm['spatial']
    adj = kneighbors_graph(coords, n_neighbors=n_neighbors, mode='distance')
    G = nx.from_scipy_sparse_array(adj)

    # Compute centrality measures
    adata.obs['degree_centrality'] = list(nx.degree_centrality(G).values())
    adata.obs['closeness_centrality'] = list(nx.closeness_centrality(G).values())
    adata.obs['betweenness_centrality'] = list(nx.betweenness_centrality(G).values())
    adata.obs['harmonic_centrality'] = list(nx.harmonic_centrality(G).values())

    # Summary
    print("\nCentrality statistics:")
    print(adata.obs[['degree_centrality', 'betweenness_centrality']].describe())

    # Top bridge spots
    bridge_spots = adata.obs.nlargest(5, 'betweenness_centrality')
    print("\nTop 5 bridge spots (high betweenness centrality):")
    print(bridge_spots[['betweenness_centrality', 'degree_centrality']])

    return adata


def compute_network_properties(adata, n_neighbors=6):
    """
    Compute structural properties of the spatial neighbor graph.
    """
    if not NETWORKX_AVAILABLE:
        raise ImportError("NetworkX required for network analysis")

    print("\n=== Computing Network Properties ===")

    coords = adata.obsm['spatial']
    adj = kneighbors_graph(coords, n_neighbors=n_neighbors, mode='distance')
    G = nx.from_scipy_sparse_array(adj)

    # Properties
    n_components = nx.number_connected_components(G)
    clustering = nx.average_clustering(G)
    density = nx.density(G)

    # Average path length (largest component)
    if n_components == 1:
        avg_path = nx.average_shortest_path_length(G)
    else:
        largest_cc = max(nx.connected_components(G), key=len)
        G_sub = G.subgraph(largest_cc)
        avg_path = nx.average_shortest_path_length(G_sub)

    properties = {
        'n_nodes': G.number_of_nodes(),
        'n_edges': G.number_of_edges(),
        'n_components': n_components,
        'clustering_coefficient': clustering,
        'density': density,
        'avg_path_length': avg_path
    }

    # Add component labels
    components = list(nx.connected_components(G))
    comp_labels = np.zeros(adata.n_obs, dtype=int)
    for i, comp in enumerate(components):
        for node in comp:
            comp_labels[node] = i
    adata.obs['network_component'] = comp_labels

    print("\nNetwork properties:")
    for key, value in properties.items():
        print(f"  {key}: {value}")

    if n_components > 1:
        print(f"\nWarning: {n_components} disconnected components detected.")

    return properties


def compute_cooccurrence(adata, cluster_key):
    """Compute co-occurrence analysis for cluster colocalization."""
    print(f"\n=== Computing Co-occurrence Analysis ===")

    sq.gr.co_occurrence(adata, cluster_key=cluster_key)

    co_occ = adata.uns[f'{cluster_key}_co_occurrence']
    print(f"\nCo-occurrence matrix shape: {co_occ['occ'].shape}")
    print(f"Distance intervals: {co_occ['interval']}")

    return co_occ


def compute_neighborhood_enrichment(adata, cluster_key):
    """Compute neighborhood enrichment analysis."""
    print(f"\n=== Computing Neighborhood Enrichment ===")

    sq.gr.nhood_enrichment(adata, cluster_key=cluster_key)

    enrichment = adata.uns[f'{cluster_key}_nhood_enrichment']
    zscore = enrichment['zscore']
    clusters = adata.obs[cluster_key].cat.categories

    zscore_df = pd.DataFrame(zscore, index=clusters, columns=clusters)

    print("\nNeighborhood enrichment z-scores:")
    print(zscore_df.round(2))

    return zscore_df


def compute_roe(adata, cell_type_key, niche_key, min_counts=5):
    """
    Compute Ro/e (Ratio of observed to expected) for cell type enrichment in niches.

    Ro/e quantifies the enrichment (Ro/e > 1) or depletion (Ro/e < 1) of a cell type
    in a specific niche compared to random expectation.

    Formula: Ro/e_ij = (O_ij / O_i+) / (O_+j / O_++)
    Where:
    - O_ij: observed count of cell type i in niche j
    - O_i+: total count of cell type i across all niches
    - O_+j: total count of all cells in niche j
    - O_++: total count of all cells

    Parameters:
    -----------
    adata : AnnData
        Spatial transcriptomics data with cell type and niche annotations
    cell_type_key : str
        Column in adata.obs containing cell type labels
    niche_key : str
        Column in adata.obs containing niche/zone labels
    min_counts : int
        Minimum count threshold for reliable Ro/e estimation (default: 5)

    Returns:
    --------
    pd.DataFrame : Ro/e matrix (cell types x niches)
    pd.DataFrame : Observed counts matrix
    pd.DataFrame : Expected counts matrix
    """
    print(f"\n=== Computing Ro/e Analysis ===")
    print(f"Cell types: {cell_type_key}")
    print(f"Niches: {niche_key}")

    # Create contingency table
    observed = pd.crosstab(adata.obs[cell_type_key], adata.obs[niche_key])

    # Calculate expected counts under random distribution
    row_totals = observed.sum(axis=1).values.reshape(-1, 1)
    col_totals = observed.sum(axis=0).values.reshape(1, -1)
    grand_total = observed.sum().sum()

    expected = (row_totals @ col_totals) / grand_total

    # Calculate Ro/e
    # Avoid division by zero
    with np.errstate(divide='ignore', invalid='ignore'):
        roe = observed / expected

    # Replace inf/nan with 0 where expected is 0
    roe = roe.replace([np.inf, -np.inf], np.nan).fillna(0)

    # Apply minimum count threshold
    roe_masked = roe.where(observed >= min_counts, np.nan)

    # Calculate enrichment categories
    def categorize(roe_val):
        if pd.isna(roe_val):
            return 'low_count'
        elif roe_val > 2:
            return 'strongly_enriched'
        elif roe_val > 1.5:
            return 'enriched'
        elif roe_val > 0.67:
            return 'neutral'
        elif roe_val > 0.5:
            return 'depleted'
        else:
            return 'strongly_depleted'

    categories = roe_masked.applymap(categorize)

    # Summary statistics
    print(f"\nObserved counts (cell types x niches):")
    print(observed)

    print(f"\nRo/e matrix (cell types x niches):")
    print(roe_masked.round(3))

    print(f"\nEnrichment summary:")
    for niche in roe_masked.columns:
        enriched = roe_masked[niche][roe_masked[niche] > 1.5].dropna()
        if len(enriched) > 0:
            print(f"  {niche}: {', '.join([f'{idx}({v:.2f})' for idx, v in enriched.items()])}")

    # Store results in adata
    adata.uns['roe_analysis'] = {
        'roe': roe_masked,
        'observed': observed,
        'expected': expected,
        'categories': categories,
        'cell_type_key': cell_type_key,
        'niche_key': niche_key
    }

    return roe_masked, observed, expected


def compute_niche_enrichment_stats(adata, cell_type_key, niche_key, method='chi2'):
    """
    Compute statistical significance of cell type enrichment in niches.

    Parameters:
    -----------
    adata : AnnData
    cell_type_key : str
    niche_key : str
    method : str
        'chi2' for chi-square test or 'fisher' for Fisher's exact test

    Returns:
    --------
    pd.DataFrame : Statistics for each cell type-niche pair
    """
    from scipy.stats import chi2_contingency, fisher_exact
    import itertools

    print(f"\n=== Computing Niche Enrichment Statistics ===")

    observed = pd.crosstab(adata.obs[cell_type_key], adata.obs[niche_key])
    results = []

    for cell_type in observed.index:
        for niche in observed.columns:
            # Create 2x2 contingency table
            in_niche = observed.loc[cell_type, niche]
            not_in_niche = observed.loc[cell_type].sum() - in_niche
            niche_total = observed[niche].sum() - in_niche
            other_total = observed.sum().sum() - in_niche - not_in_niche - niche_total

            contingency = [[in_niche, not_in_niche],
                          [niche_total, other_total]]

            if method == 'chi2':
                try:
                    chi2, pval, dof, expected = chi2_contingency(contingency)
                except ValueError:
                    pval = np.nan
            elif method == 'fisher':
                try:
                    _, pval = fisher_exact(contingency)
                except ValueError:
                    pval = np.nan

            # Calculate Ro/e for context
            total_cells = observed.sum().sum()
            total_cell_type = observed.loc[cell_type].sum()
            total_niche = observed[niche].sum()
            expected_count = (total_cell_type * total_niche) / total_cells
            roe = in_niche / expected_count if expected_count > 0 else np.nan

            results.append({
                'cell_type': cell_type,
                'niche': niche,
                'observed': in_niche,
                'expected': expected_count,
                'roe': roe,
                'p_value': pval
            })

    results_df = pd.DataFrame(results)

    # FDR correction
    valid_pvals = results_df['p_value'].dropna()
    if len(valid_pvals) > 0:
        _, qvals, _, _ = multipletests(valid_pvals, method='fdr_bh')
        results_df.loc[valid_pvals.index, 'q_value'] = qvals

    print(f"\nSignificant enrichments (q < 0.05):")
    sig = results_df[results_df['q_value'] < 0.05].sort_values('q_value')
    print(sig[['cell_type', 'niche', 'roe', 'q_value']].head(20))

    return results_df


def run_complete_workflow(adata_path, output_path='spatial_stats_results.h5ad'):
    """
    Run the complete spatial statistics workflow.

    Parameters
    ----------
    adata_path : str
        Path to input h5ad file
    output_path : str
        Path to save results
    """
    # Load data
    print(f"Loading data from {adata_path}")
    adata = sc.read_h5ad(adata_path)
    print(f"Loaded: {adata.n_obs} spots, {adata.n_vars} genes")

    # Validate data
    validate_spatial_data(adata)

    # Build spatial graph
    print("\nBuilding spatial neighbor graph...")
    sq.gr.spatial_neighbors(adata, coord_type='generic', n_neighs=6)

    # 1. Global Moran's I
    try:
        hvg = adata.var_names[adata.var['highly_variable']][:500]
        compute_global_moran(adata, genes=hvg)
    except Exception as e:
        print(f"Global Moran's I failed: {e}")

    # 2. Getis-Ord Gi* (hotspot detection)
    try:
        top_gene = adata.uns['moranI'].index[0]
        compute_getis_ord_gi(adata, top_gene)
    except Exception as e:
        print(f"Getis-Ord Gi* failed: {e}")

    # 3. LISA
    try:
        compute_lisa(adata, top_gene)
    except Exception as e:
        print(f"LISA failed: {e}")

    # 4. Network properties
    try:
        compute_network_properties(adata)
    except Exception as e:
        print(f"Network properties failed: {e}")

    # 5. Spatial centrality
    try:
        compute_spatial_centrality(adata)
    except Exception as e:
        print(f"Spatial centrality failed: {e}")

    # 6. Cluster-based analyses (if clusters exist)
    cluster_key = None
    for key in ['leiden', 'louvain', 'cluster', 'cell_type']:
        if key in adata.obs.columns:
            cluster_key = key
            break

    if cluster_key:
        print(f"\nUsing cluster key: {cluster_key}")

        try:
            compute_join_counts(adata, cluster_key)
        except Exception as e:
            print(f"Join counts failed: {e}")

        try:
            compute_cooccurrence(adata, cluster_key)
        except Exception as e:
            print(f"Co-occurrence failed: {e}")

        try:
            compute_neighborhood_enrichment(adata, cluster_key)
        except Exception as e:
            print(f"Neighborhood enrichment failed: {e}")

    # 7. Bivariate Moran's I (example with top 2 genes)
    try:
        top_genes = adata.uns['moranI'].head(2).index.tolist()
        if len(top_genes) >= 2:
            compute_bivariate_moran(adata, top_genes[0], top_genes[1])
    except Exception as e:
        print(f"Bivariate Moran's I failed: {e}")

    # Save results
    print(f"\nSaving results to {output_path}")
    adata.write_h5ad(output_path)
    print("Done!")

    return adata


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage: python compute_statistics.py <input.h5ad> [output.h5ad]")
        print("\nExample:")
        print("  python compute_statistics.py preprocessed.h5ad results.h5ad")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else 'spatial_stats_results.h5ad'

    run_complete_workflow(input_path, output_path)
