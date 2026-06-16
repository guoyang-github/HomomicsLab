"""
Niche Annotation Example

Automatically annotate niches based on characteristic cell type markers.
Identifies biologically meaningful microenvironments like TLS, neural niches,
tumor regions, and stromal areas.

Prerequisites:
    - Spatial data with niche assignments (from clustering)
    - Niche composition matrix
"""

import pandas as pd
import numpy as np
import scanpy as sc


def annotate_niches_by_markers(niche_composition, marker_dict, threshold=0.15):
    """
    Annotate niches based on characteristic cell type markers.

    Parameters
    ----------
    niche_composition : DataFrame
        Niche x cell_type composition matrix
    marker_dict : dict
        Dictionary mapping niche types to characteristic cell types
        e.g., {'TLS': ['B_cell', 'T_cell'], 'Neural': ['Schwann_cell']}
    threshold : float
        Minimum score threshold for confident assignment

    Returns
    -------
    dict : niche_id to annotation mapping
    DataFrame : scores for each niche type per niche
    """
    annotations = {}
    all_scores = []

    for niche_id, row in niche_composition.iterrows():
        scores = {}
        for niche_type, markers in marker_dict.items():
            # Calculate mean proportion of marker cell types
            available_markers = [m for m in markers if m in row.index]
            if len(available_markers) == 0:
                scores[niche_type] = 0
                continue

            score = sum(row.get(m, 0) for m in available_markers) / len(available_markers)
            scores[niche_type] = score

        # Select best matching type
        if scores:
            best_match = max(scores, key=scores.get)
            best_score = scores[best_match]

            if best_score > threshold:
                annotations[str(niche_id)] = best_match
            else:
                annotations[str(niche_id)] = 'Mixed'
        else:
            annotations[str(niche_id)] = 'Unknown'
            best_score = 0

        scores['niche_id'] = str(niche_id)
        scores['assigned'] = annotations[str(niche_id)]
        scores['best_score'] = best_score
        all_scores.append(scores)

    scores_df = pd.DataFrame(all_scores).set_index('niche_id')

    print(f"Annotated {len(annotations)} niches")
    print(f"Threshold: {threshold}")
    print(f"\nAnnotation distribution:")
    print(pd.Series(annotations).value_counts())

    return annotations, scores_df


def get_pancreas_niche_markers():
    """
    Get pancreatic cancer-specific niche marker dictionary.

    Returns
    -------
    dict : Niche type to cell type markers mapping
    """
    return {
        'TLS': ['B_cell', 'T_cell', 'Plasma_cell'],
        'Neural': ['Schwann_cell', 'Neuron'],
        'Tumor': ['Ductal_cell', 'Cancer_cell'],
        'Stroma': ['Fibroblast', 'Myofibroblast'],
        'Immune_infiltrate': ['T_cell', 'Macrophage', 'NK_cell'],
        'Vascular': ['Endothelial_cell', 'Pericyte'],
        'Acinar': ['Acinar_cell'],
        'Ductal': ['Ductal_cell'],
    }


def get_tumor_microenvironment_markers():
    """
    Get general tumor microenvironment niche markers.

    Returns
    -------
    dict : Niche type to cell type markers mapping
    """
    return {
        'Tumor_core': ['Cancer_cell', 'Tumor_cell', 'Malignant'],
        'Tumor_stroma': ['Fibroblast', 'Cancer_cell', 'CAF'],
        'Immune_hot': ['T_cell', 'B_cell', 'Macrophage', 'CD8_T', 'CD4_T'],
        'Immune_cold': ['Fibroblast', 'Endothelial_cell'],
        'TLS': ['B_cell', 'T_cell', 'Follicular_B', 'GC_B'],
        'Hypoxic': ['Cancer_cell', 'Fibroblast'],
        'Vascular': ['Endothelial_cell', 'Pericyte'],
        'Necrotic': ['Macrophage', 'Neutrophil'],
    }


def get_neural_niche_markers():
    """
    Get brain/neural tissue niche markers.

    Returns
    -------
    dict : Niche type to cell type markers mapping
    """
    return {
        'Neural_cortex': ['Neuron', 'Astrocyte', 'Excitatory', 'Inhibitory'],
        'White_matter': ['Oligodendrocyte', 'Microglia', 'OPC'],
        'Neurogenic_niche': ['Neural_stem', 'Astrocyte', 'NSC'],
        'Hippocampus': ['Neuron', 'Granule'],
        'Vascular': ['Endothelial_cell', 'Pericyte'],
        'Inflammatory': ['Microglia', 'Macrophage', 'T_cell'],
        'Meninges': ['Fibroblast', 'Endothelial_cell'],
    }


def apply_niche_annotations(adata, annotations, niche_key='niche', new_key='niche_annotated'):
    """
    Apply niche annotations to AnnData object.

    Parameters
    ----------
    adata : AnnData
        Spatial data with niche assignments
    annotations : dict
        Niche ID to annotation mapping
    niche_key : str
        Original niche column name
    new_key : str
        New column name for annotated niches

    Returns
    -------
    adata : AnnData with new annotation column
    """
    adata.obs[new_key] = adata.obs[niche_key].astype(str).map(annotations)

    # Fill unmapped with original niche ID
    unmapped = adata.obs[new_key].isna()
    if unmapped.any():
        adata.obs.loc[unmapped, new_key] = adata.obs.loc[unmapped, niche_key].astype(str)

    print(f"Added '{new_key}' to adata.obs")
    print(f"Unique annotations: {adata.obs[new_key].nunique()}")

    return adata


def summarize_niches(adata, niche_key='niche_annotated', group_key=None):
    """
    Create summary statistics for annotated niches.

    Parameters
    ----------
    adata : AnnData
        Spatial data with niche annotations
    niche_key : str
        Column with niche annotations
    group_key : str, optional
        Column for grouping (e.g., 'sample', 'condition')

    Returns
    -------
    DataFrame : Summary statistics
    """
    if group_key:
        summary = adata.obs.groupby([group_key, niche_key]).size().unstack(fill_value=0)
        summary_pct = summary.div(summary.sum(axis=1), axis=0) * 100
        print(f"\nNiche distribution by {group_key} (counts):")
        print(summary)
        print(f"\nNiche distribution by {group_key} (percentages):")
        print(summary_pct.round(1))
        return summary, summary_pct
    else:
        counts = adata.obs[niche_key].value_counts()
        percentages = adata.obs[niche_key].value_counts(normalize=True) * 100
        summary = pd.DataFrame({
            'count': counts,
            'percentage': percentages.round(1)
        })
        print("\nOverall niche distribution:")
        print(summary)
        return summary


# Example usage
if __name__ == "__main__":
    # Example workflow:

    # 1. Load your data with niche assignments
    # adata = sc.read_h5ad('spatial_data_with_niches.h5ad')
    # niche_comp = adata.uns['niche_composition']

    # 2. Select appropriate marker dictionary
    # niche_markers = get_pancreas_niche_markers()
    # niche_markers = get_tumor_microenvironment_markers()
    # niche_markers = get_neural_niche_markers()

    # 3. Or create custom markers
    # custom_markers = {
    #     'My_Niche': ['CellType1', 'CellType2'],
    #     'Other_Niche': ['CellType3'],
    # }

    # 4. Annotate niches
    # annotations, scores = annotate_niches_by_markers(
    #     niche_comp,
    #     niche_markers,
    #     threshold=0.15
    # )

    # 5. Apply to adata
    # adata = apply_niche_annotations(adata, annotations)

    # 6. Summarize results
    # summary = summarize_niches(adata, niche_key='niche_annotated')

    # 7. Compare by group if available
    # summary_by_group = summarize_niches(
    #     adata,
    #     niche_key='niche_annotated',
    #     group_key='condition'
    # )

    print("Niche annotation example loaded successfully!")
    print("\nTo use:")
    print("1. Load your niche composition matrix")
    print("2. Select or create a marker dictionary")
    print("3. Call annotate_niches_by_markers()")
    print("4. Apply annotations with apply_niche_annotations()")
    print("5. Summarize with summarize_niches()")
