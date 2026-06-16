---
name: bio-spatial-transcriptomics-niches
description: Cluster spatial transcriptomics spots into tissue microenvironment niches based on cell type proportions from deconvolution. Identifies biologically meaningful regions like TLS, neural niches, tumor-stroma interfaces using unsupervised clustering with optional spatial constraints. Use when analyzing tissue microenvironments and cellular neighborhoods.
tool_type: python
primary_tool: scanpy
supported_tools: [squidpy, scikit-learn, pandas, numpy, leidenalg]
keywords: ["spatial", "niche", "microenvironment", "clustering", "deconvolution", "cell-type-proportions", "tissue-zones", "TLS", "neural-niche"]
---

## Version Compatibility

Reference examples tested with: numpy 1.26+, pandas 2.2+, scanpy 1.10+, squidpy 1.3+, scikit-learn 1.4+

Before using code patterns, verify installed versions match. If versions differ:
- Python: `pip show <package>` then `help(module.function)` to check signatures

If code throws ImportError, AttributeError, or TypeError, introspect the installed
package and adapt the example to match the actual API rather than retrying.

## Quick Selector

### Method Comparison

| Method | Constraint | Speed | Best For | Key Features |
|--------|------------|-------|----------|--------------|
| **KMeans** | None | Fast | Simple clustering | No spatial constraint |
| **Leiden + Spatial** | Spatial | Medium | Spatially coherent niches | Neighbor-aware clustering |
| **Proportion-Based** | Composition | Fast | Deconvolution results | Cell type composition |

### Selection Guide

| Your Situation | Recommended Method | Why |
|----------------|-------------------|-----|
| Have deconvolution results | Proportion-Based | Uses cell type composition |
| Need spatial coherence | Leiden + Spatial | Enforces spatial smoothness |
| Simple/fast clustering | KMeans | No spatial dependencies |
| Large dataset | KMeans | Most scalable |
| Tissue zone analysis | Leiden + Spatial | Respects tissue boundaries |


---

# Spatial Niche Clustering

Cluster spatial transcriptomics spots into niches (tissue microenvironments) based on cell type composition from deconvolution.

## Required Imports

```python
import scanpy as sc
import squidpy as sq
import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
import warnings
```

## Proportion-Based Niche Clustering

**Goal:** Cluster spots into niches based on cell type proportions from deconvolution.

**Input State:** [Deconvolved] (with cell type proportions in `obsm`)
**Output State:** [Deconvolved] + niche assignments in `obs['niche']`

**Approach:** Use PCA on proportion matrix followed by KMeans or Leiden clustering, optionally with spatial constraints.

**"Cluster spots by cell type composition"** -> Group spots with similar cell type proportions into niches/microenvironments.

```python
def cluster_niches_by_proportions(
    adata,
    proportions_key='cell_type_proportions',
    n_clusters=12,
    use_spatial_constraint=True,
    n_neighbors=6,
    random_state=42
):
    """
    Cluster spatial niches based on cell type proportions.

    Parameters:
    -----------
    adata : AnnData
        Spatial data with deconvolution results in obsm
    proportions_key : str
        Key in adata.obsm containing cell type proportions
    n_clusters : int
        Number of niche clusters (for non-spatial methods)
    use_spatial_constraint : bool
        Whether to include spatial coordinates in clustering
    n_neighbors : int
        Number of spatial neighbors (Visium default: 6)
    random_state : int
        Random seed for reproducibility

    Returns:
    --------
    adata : AnnData with niche assignments
    niche_composition : DataFrame of niche × cell_type composition
    """
    proportions = adata.obsm[proportions_key]
    cell_types = proportions.columns.tolist()

    # PCA on proportions
    n_components = min(10, len(cell_types))
    pca = PCA(n_components=n_components, random_state=random_state)
    prop_pca = pca.fit_transform(proportions.values)

    if use_spatial_constraint:
        # Build spatial neighbor graph
        sq.gr.spatial_neighbors(adata, n_neighs=n_neighbors)

        # Normalize spatial coordinates
        coords = adata.obsm['spatial']
        coords_normalized = (coords - coords.min(axis=0)) / (coords.max(axis=0) - coords.min(axis=0) + 1e-8)

        # Combine proportion PCA with spatial coordinates
        combined_features = np.hstack([prop_pca, coords_normalized])
        adata.obsm['X_niche_pca'] = combined_features

        # Leiden clustering with spatial constraint
        sc.pp.neighbors(adata, use_rep='X_niche_pca', n_neighbors=30, key_added='niche_neighbors')
        sc.tl.leiden(adata, neighbors_key='niche_neighbors', key_added='niche', random_state=random_state)
    else:
        # KMeans clustering on proportions only
        kmeans = KMeans(n_clusters=n_clusters, random_state=random_state, n_init=10)
        adata.obs['niche'] = kmeans.fit_predict(prop_pca).astype(str)

    # Calculate niche composition
    niche_composition = adata.obs.groupby('niche')[cell_types].mean()

    return adata, niche_composition


# Usage
adata, niche_comp = cluster_niches_by_proportions(
    adata,
    proportions_key='cell_type_proportions',
    n_clusters=10,
    use_spatial_constraint=True
)

print("Niche composition:")
print(niche_comp)
```

## Automatic Niche Annotation

**Goal:** Automatically annotate niches based on characteristic cell type markers (e.g., TLS, neural, tumor, stroma).

**Input State:** [Deconvolved] + niche assignments
**Output State:** [Deconvolved] + annotated niches in `obs['niche_annotated']`

**Approach:** Score each niche against marker dictionaries for known niche types, assign the highest scoring label.

```python
def annotate_niches_by_markers(niche_composition, marker_dict, threshold=0.1):
    """
    Annotate niches based on characteristic cell types.

    Parameters:
    -----------
    niche_composition : DataFrame
        Niche × cell_type composition matrix
    marker_dict : dict
        Niche type to characteristic cell types mapping
        e.g., {'TLS': ['B_cell', 'T_cell'], 'Neural': ['Schwann_cell']}
    threshold : float
        Minimum score threshold for confident assignment

    Returns:
    --------
    dict : niche_id to annotation mapping
    """
    annotations = {}

    for niche_id, row in niche_composition.iterrows():
        scores = {}
        for niche_type, markers in marker_dict.items():
            score = sum(row.get(m, 0) for m in markers) / len(markers)
            scores[niche_type] = score

        # Select best matching type
        best_match = max(scores, key=scores.get)
        if scores[best_match] > threshold:
            annotations[str(niche_id)] = best_match
        else:
            annotations[str(niche_id)] = 'Mixed'

    return annotations


# Define niche markers for pancreatic cancer
def get_pancreas_niche_markers():
    """Get pancreas-specific niche marker dictionary."""
    return {
        'TLS': ['B_cell', 'T_cell', 'Plasma_cell'],
        'Neural': ['Schwann_cell', 'Neuron'],
        'Tumor': ['Ductal_cell', 'Cancer_cell'],
        'Stroma': ['Fibroblast', 'Myofibroblast'],
        'Immune_infiltrate': ['T_cell', 'Macrophage', 'NK_cell'],
        'Vascular': ['Endothelial_cell', 'Pericyte'],
        'Acinar': ['Acinar_cell'],
    }


# Usage
niche_markers = get_pancreas_niche_markers()
niche_annotations = annotate_niches_by_markers(niche_comp, niche_markers, threshold=0.15)

# Apply annotations
adata.obs['niche_annotated'] = adata.obs['niche'].map(niche_annotations)
```

## Compare Niches by Group

**Goal:** Compare niche proportions between experimental groups (e.g., NI+ vs NI-).

**Input State:** [Deconvolved] + niche assignments + group metadata
**Output State:** Comparison results (tables)

**Approach:** Calculate niche frequencies per group and perform statistical comparison.

```python
def compare_niches_by_group(adata, niche_key='niche', group_key='group'):
    """
    Compare niche distributions across groups.

    Parameters:
    -----------
    adata : AnnData
    niche_key : str
        Niche column name
    group_key : str
        Grouping column (e.g., 'NI_status')

    Returns:
    --------
    DataFrame : Niche proportions per group
    """
    # Count niches per group
    niche_counts = adata.obs.groupby([group_key, niche_key]).size().unstack(fill_value=0)

    # Convert to proportions
    niche_proportions = niche_counts.div(niche_counts.sum(axis=1), axis=0)

    return niche_proportions


# Usage with statistical testing
from scipy.stats import chi2_contingency

niche_props = compare_niches_by_group(adata, niche_key='niche_annotated', group_key='NI_status')
print(niche_props)

# Chi-square test for niche distribution differences
contingency = adata.obs.groupby(['NI_status', 'niche_annotated']).size().unstack(fill_value=0)
chi2, pval, dof, expected = chi2_contingency(contingency)
print(f"Niche distribution difference: p = {pval:.2e}")
```

## Visualize Niches

**Goal:** Visualize niche spatial distribution and composition.

**Input State:** [Deconvolved] + niche assignments
**Output State:** [Deconvolved] (visualization only, no data modification)

> **Note:** `sc.pl.spatial()` was removed in scanpy 1.12+. Use `sq.pl.spatial_scatter()` from squidpy instead.  
> Parameter mapping: `spot_size` → `size`. `alpha_img`, `bw`, and `scale_factor` are not supported in squidpy.
```python
import matplotlib.pyplot as plt

# Spatial niche map
sq.pl.spatial_scatter(adata, color='niche_annotated', title='Spatial Niches')

# Niche composition heatmap
plt.figure(figsize=(10, 8))
import seaborn as sns
sns.heatmap(niche_comp.T, cmap='YlOrRd', annot=True, fmt='.2f')
plt.title('Niche Cell Type Composition')
plt.xlabel('Niche')
plt.ylabel('Cell Type')
plt.tight_layout()
plt.savefig('niche_composition_heatmap.png')
```

## Niche Differential Abundance

**Goal:** Identify niches with significantly different abundance between groups.

**Input State:** [Deconvolved] + niche assignments + group metadata
**Output State:** Differential abundance results (DataFrame)

```python
def niche_differential_abundance(adata, niche_key='niche', group_key='group', test='chi2'):
    """
    Test for differential niche abundance between groups.

    Parameters:
    -----------
    adata : AnnData
    niche_key : str
    group_key : str
    test : str
        'chi2' for chi-square test

    Returns:
    --------
    DataFrame : Differential abundance results per niche
    """
    groups = adata.obs[group_key].unique()
    results = []

    for niche in adata.obs[niche_key].unique():
        # Build 2x2 contingency table
        niche_in_group = []
        niche_not_in_group = []

        for group in groups:
            group_data = adata.obs[adata.obs[group_key] == group]
            in_niche = (group_data[niche_key] == niche).sum()
            not_in_niche = len(group_data) - in_niche
            niche_in_group.append(in_niche)
            niche_not_in_group.append(not_in_niche)

        contingency = np.array([niche_in_group, niche_not_in_group])

        chi2, pval, dof, expected = chi2_contingency(contingency)

        results.append({
            'niche': niche,
            'chi2': chi2,
            'pval': pval,
            'group1_count': niche_in_group[0],
            'group2_count': niche_in_group[1] if len(groups) > 1 else None
        })

    results_df = pd.DataFrame(results)

    # FDR correction
    from statsmodels.stats.multitest import multipletests
    _, qvals, _, _ = multipletests(results_df['pval'], method='fdr_bh')
    results_df['qval'] = qvals

    return results_df.sort_values('qval')


# Usage
da_results = niche_differential_abundance(adata, niche_key='niche_annotated', group_key='NI_status')
print(da_results[da_results['qval'] < 0.05])
```

## Output Details

| Output | Location | Type | Description |
|--------|----------|------|-------------|
| Niche | `obs['niche']` | string | Niche cluster assignment |
| Niche Annotated | `obs['niche_annotated']` | string | Biologically annotated niche label |
| Niche PCA | `obsm['X_niche_pca']` | matrix | Combined proportion + spatial features |
| Niche Composition | `niche_comp` (returned) | DataFrame | Cell type proportions per niche |
| Differential Abundance | `da_results` (returned) | DataFrame | Statistical test results |

## Related Skills

- bio-spatial-transcriptomics-deconvolution - Get cell type proportions
- bio-spatial-transcriptomics-neighbors - Build spatial graphs
- bio-spatial-transcriptomics-visualization - Advanced visualization
- bio-spatial-transcriptomics-statistics - Spatial statistics on niches
