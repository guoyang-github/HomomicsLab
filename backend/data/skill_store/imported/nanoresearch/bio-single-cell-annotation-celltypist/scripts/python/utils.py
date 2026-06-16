"""Utility functions for CellTypist annotation workflow.

This module provides helper functions for data preparation, result processing,
and model management.
"""

import os
import json
import numpy as np
import pandas as pd
import scanpy as sc
from scipy import stats
from anndata import AnnData
from typing import Optional, Union, List, Dict, Any, Tuple
import celltypist


def create_test_data(
    n_cells: int = 1000,
    n_genes: int = 2000,
    n_cell_types: int = 5,
    seed: int = 42
) -> AnnData:
    """Create test data for CellTypist annotation.

    Args:
        n_cells: Number of cells
        n_genes: Number of genes
        n_cell_types: Number of cell types to simulate
        seed: Random seed

    Returns:
        AnnData object with simulated data
    """
    np.random.seed(seed)

    # Generate expression data (log-normalized)
    X = np.random.lognormal(3, 1, (n_cells, n_genes))

    # Create gene names (gene symbols)
    var_names = [f"GENE{i:04d}" for i in range(n_genes)]

    # Create cell types
    cell_types = [f"CellType{i}" for i in range(n_cell_types)]
    cell_type_labels = np.random.choice(cell_types, n_cells)

    # Create observation metadata
    obs = pd.DataFrame({
        'true_cell_type': cell_type_labels,
        'sample': np.random.choice(['Sample1', 'Sample2'], n_cells)
    }, index=[f"cell_{i}" for i in range(n_cells)])

    # Create variable metadata
    var = pd.DataFrame(index=var_names)

    # Create AnnData
    adata = AnnData(X=X, obs=obs, var=var)

    # Add UMAP coordinates
    adata.obsm['X_umap'] = np.random.randn(n_cells, 2)

    print(f"Created test data: {n_cells} cells x {n_genes} genes")
    print(f"Simulated {n_cell_types} cell types")

    return adata


def prepare_data_for_celltypist(
    adata: AnnData,
    layer: Optional[str] = None,
    normalize: bool = True,
    target_sum: float = 1e4,
    log_transform: bool = True,
    highly_variable_genes: bool = False,
    n_top_genes: int = 2000
) -> AnnData:
    """Prepare AnnData for CellTypist annotation.

    CellTypist expects log-normalized data. This function ensures
    proper normalization. Uses a robust heuristic to detect raw counts
    (integer values with max > 50), but always errs on the side of
    normalizing if uncertain.

    Args:
        adata: Input AnnData
        layer: Layer to use (None for .X)
        normalize: Whether to normalize to target sum
        target_sum: Target sum for normalization
        log_transform: Whether to log1p transform
        highly_variable_genes: Whether to select HVGs
        n_top_genes: Number of HVGs to select

    Returns:
        Prepared AnnData (copy)
    """
    adata = adata.copy()

    # Use specified layer if provided
    if layer is not None:
        if layer in adata.layers:
            adata.X = adata.layers[layer]
        else:
            raise ValueError(f"Layer '{layer}' not found in adata.layers")

    # Check if data is already log-normalized
    needs_norm = False
    if adata.n_obs > 0 and adata.n_vars > 0:
        try:
            sample_size = min(1000, adata.n_obs)
            x_sample = adata.X[:sample_size]
            if hasattr(x_sample, 'toarray'):
                x_sample = x_sample.toarray()
            max_val = float(np.max(x_sample))
            # Heuristic: raw counts typically have large integer max values (>50)
            # Log-normalized data typically has max < 10 (for target_sum=1e4)
            if max_val > 50 and float(max_val).is_integer():
                needs_norm = True
            elif max_val > 100:
                # Very large values strongly suggest raw counts
                needs_norm = True
        except Exception:
            needs_norm = True  # If we can't tell, normalize to be safe

    if needs_norm or normalize or log_transform:
        if needs_norm:
            print("Data appears to be raw counts. Normalizing...")
        elif normalize or log_transform:
            print("Normalization requested by user. Processing...")
        if normalize:
            sc.pp.normalize_total(adata, target_sum=target_sum)
        if log_transform:
            sc.pp.log1p(adata)
    else:
        print("Data appears to be log-normalized. Skipping normalization.")

    # Select HVGs if requested
    if highly_variable_genes:
        sc.pp.highly_variable_genes(adata, n_top_genes=n_top_genes)
        print(f"Selected {n_top_genes} highly variable genes")

    return adata


def get_model_catalog() -> Dict[str, Any]:
    """Get catalog of available CellTypist models.

    Returns:
        Dictionary with model information
    """
    catalog = {
        "human": {
            "Immune_All_Low.pkl": {
                "description": "General immune cells (28 types, broad)",
                "cell_types": 28,
                "tissue": "Immune",
                "use_case": "General immune annotation"
            },
            "Immune_All_High.pkl": {
                "description": "Detailed immune cells (98 types, fine-grained)",
                "cell_types": 98,
                "tissue": "Immune",
                "use_case": "Detailed immune subtypes"
            },
            "Cells_Intestinal_Training.pkl": {
                "description": "Intestinal epithelial cells (56 types)",
                "cell_types": 56,
                "tissue": "Intestine",
                "use_case": "Colon/small intestine epithelial"
            },
            "Cells_Lung_Airway_Training.pkl": {
                "description": "Lung airway epithelial cells (38 types)",
                "cell_types": 38,
                "tissue": "Lung",
                "use_case": "Airway epithelial cells"
            },
            "COVID19_Immune_Landscape.pkl": {
                "description": "COVID-19 immune landscape",
                "cell_types": None,
                "tissue": "Blood",
                "use_case": "COVID-specific immune states"
            }
        },
        "mouse": {
            "NLP_Mouse_Immune.pkl": {
                "description": "Mouse immune cells (22 types)",
                "cell_types": 22,
                "tissue": "Immune",
                "use_case": "Mouse immune annotation"
            }
        }
    }
    return catalog


def recommend_model(
    tissue: str = 'immune',
    species: str = 'human',
    resolution: str = 'low'
) -> str:
    """Recommend a CellTypist model based on sample characteristics.

    Args:
        tissue: Tissue type ('immune', 'intestine', 'lung', etc.)
        species: 'human' or 'mouse'
        resolution: 'low' (broad) or 'high' (fine-grained)

    Returns:
        Recommended model name
    """
    recommendations = {
        'human': {
            'immune': {
                'low': 'Immune_All_Low.pkl',
                'high': 'Immune_All_High.pkl'
            },
            'intestine': {
                'low': 'Cells_Intestinal_Training.pkl',
                'high': 'Cells_Intestinal_Training.pkl'
            },
            'lung': {
                'low': 'Cells_Lung_Airway_Training.pkl',
                'high': 'Cells_Lung_Airway_Training.pkl'
            },
            'blood': {
                'low': 'Immune_All_Low.pkl',
                'high': 'Immune_All_High.pkl'
            },
            'covid': {
                'low': 'COVID19_Immune_Landscape.pkl',
                'high': 'COVID19_Immune_Landscape.pkl'
            }
        },
        'mouse': {
            'immune': {
                'low': 'NLP_Mouse_Immune.pkl',
                'high': 'NLP_Mouse_Immune.pkl'
            }
        }
    }

    tissue = tissue.lower()
    species = species.lower()
    resolution = resolution.lower()

    if species not in recommendations:
        raise ValueError(f"Species '{species}' not supported. Use 'human' or 'mouse'.")

    if tissue not in recommendations[species]:
        print(f"Tissue '{tissue}' not in recommendations. Using default 'immune'.")
        tissue = 'immune'

    model = recommendations[species][tissue][resolution]
    print(f"Recommended model for {species} {tissue} ({resolution} resolution): {model}")

    return model


def _resolve_columns(adata: AnnData, col: str, alternatives: List[str]) -> str:
    """Resolve a column name using fallbacks."""
    if col in adata.obs.columns:
        return col
    for alt in alternatives:
        if alt in adata.obs.columns:
            return alt
    return col  # Return original if none found; caller should handle missing


def summarize_annotations(
    adata: AnnData,
    label_col: str = 'celltypist_label',
    conf_col: str = 'celltypist_conf_score'
) -> pd.DataFrame:
    """Summarize CellTypist annotation results.

    Args:
        adata: AnnData with CellTypist predictions
        label_col: Column with predicted labels
        conf_col: Column with confidence scores

    Returns:
        DataFrame with summary statistics
    """
    label_col = _resolve_columns(adata, label_col,
                                  ['celltypist_label', 'majority_voting', 'predicted_labels'])
    conf_col = _resolve_columns(adata, conf_col,
                                 ['celltypist_conf_score', 'conf_score'])

    if label_col not in adata.obs.columns:
        raise ValueError(f"Label column '{label_col}' not found in adata.obs")

    has_conf = conf_col in adata.obs.columns

    summary = []
    for cell_type in adata.obs[label_col].unique():
        mask = adata.obs[label_col] == cell_type
        cells = adata[mask]

        row = {
            'cell_type': cell_type,
            'n_cells': int(mask.sum()),
            'proportion': float(mask.mean()),
        }
        if has_conf:
            row['mean_confidence'] = float(cells.obs[conf_col].mean())
            row['median_confidence'] = float(cells.obs[conf_col].median())
            row['min_confidence'] = float(cells.obs[conf_col].min())
            row['max_confidence'] = float(cells.obs[conf_col].max())
        summary.append(row)

    summary_df = pd.DataFrame(summary)
    summary_df = summary_df.sort_values('n_cells', ascending=False)

    return summary_df


def export_annotations(
    adata: AnnData,
    output_file: str,
    label_col: str = 'celltypist_label',
    conf_col: str = 'celltypist_conf_score'
) -> None:
    """Export CellTypist annotations to CSV.

    Args:
        adata: AnnData with CellTypist predictions
        output_file: Output CSV file path
        label_col: Column with predicted labels
        conf_col: Column with confidence scores
    """
    label_col = _resolve_columns(adata, label_col,
                                  ['celltypist_label', 'majority_voting', 'predicted_labels'])
    conf_col = _resolve_columns(adata, conf_col,
                                 ['celltypist_conf_score', 'conf_score'])

    # Build export columns from actual adata.obs columns
    cols_to_export = []
    if label_col in adata.obs.columns:
        cols_to_export.append(label_col)
    if conf_col in adata.obs.columns:
        cols_to_export.append(conf_col)

    if not cols_to_export:
        raise ValueError("No annotation columns found to export")

    # Create export DataFrame
    export_df = adata.obs[cols_to_export].copy()
    export_df.insert(0, 'cell_barcode', adata.obs.index)

    export_df.to_csv(output_file, index=False)
    print(f"Exported annotations to: {output_file}")


def merge_predictions(
    adata: AnnData,
    method: str = 'highest_confidence',
    conf_threshold: float = 0.5,
    pred_cols: Optional[List[str]] = None,
    conf_cols: Optional[List[str]] = None
) -> pd.Series:
    """Merge predictions from multiple CellTypist models.

    Args:
        adata: AnnData with multiple prediction columns
        method: 'highest_confidence' or 'majority_vote'
        conf_threshold: Minimum confidence for inclusion
        pred_cols: Explicit prediction column names. If None, auto-detects.
        conf_cols: Explicit confidence column names. If None, auto-detects.
                   Required when pred_cols has more than one element.

    Returns:
        Series with merged predictions
    """
    # Auto-detect columns if not provided
    if pred_cols is None:
        pred_cols = [col for col in adata.obs.columns
                     if 'celltypist' in col and 'label' in col
                     and col != 'celltypist_label' and 'filtered' not in col]
    if conf_cols is None:
        conf_cols = [col for col in adata.obs.columns
                     if 'celltypist' in col and 'conf' in col]

    if len(pred_cols) == 0:
        raise ValueError("No CellTypist prediction columns found")

    if len(pred_cols) == 1 and len(conf_cols) == 1:
        # Single model: no merge needed, return the only prediction
        return adata.obs[pred_cols[0]]

    if method == 'highest_confidence' and len(conf_cols) > 0:
        if len(pred_cols) != len(conf_cols):
            raise ValueError(
                f"Number of prediction columns ({len(pred_cols)}) must match "
                f"number of confidence columns ({len(conf_cols)}) for 'highest_confidence' method. "
                f"Prediction columns: {pred_cols}, Confidence columns: {conf_cols}. "
                f"Provide explicit pred_cols and conf_cols to ensure correct mapping."
            )
        # Use prediction with highest confidence
        conf_matrix = adata.obs[conf_cols].values
        best_idx = conf_matrix.argmax(axis=1)
        merged = pd.Series([adata.obs.iloc[i, adata.obs.columns.get_loc(pred_cols[idx])]
                           for i, idx in enumerate(best_idx)], index=adata.obs.index)
    else:
        # Use majority vote
        pred_matrix = adata.obs[pred_cols].values
        mode_result = stats.mode(pred_matrix, axis=1, keepdims=False)
        merged = pd.Series(mode_result.mode, index=adata.obs.index)

    return merged


def check_gene_overlap(
    adata: AnnData,
    model: Union[str, celltypist.models.Model]
) -> Dict[str, Any]:
    """Check overlap between adata genes and model genes.

    Args:
        adata: Input AnnData
        model: CellTypist model name or Model object

    Returns:
        Dictionary with overlap statistics
    """
    # Load model if needed
    if isinstance(model, str):
        try:
            model = celltypist.models.Model.load(model)
        except FileNotFoundError:
            print(f"Model '{model}' not found locally. Downloading...")
            celltypist.models.download_models(model=model)
            model = celltypist.models.Model.load(model)

    adata_genes = set(adata.var_names)
    model_genes = set(model.features)

    overlap = adata_genes.intersection(model_genes)
    adata_only = adata_genes - model_genes
    model_only = model_genes - adata_genes

    results = {
        'n_adata_genes': len(adata_genes),
        'n_model_genes': len(model_genes),
        'n_overlap': len(overlap),
        'overlap_fraction': len(overlap) / len(model_genes) if len(model_genes) > 0 else 0.0,
        'adata_only_genes': list(adata_only)[:10],  # First 10
        'model_only_genes': list(model_only)[:10]   # First 10
    }

    print(f"Gene overlap statistics:")
    print(f"  Data genes: {len(adata_genes)}")
    print(f"  Model genes: {len(model_genes)}")
    print(f"  Overlap: {len(overlap)} ({results['overlap_fraction']*100:.1f}%)")

    return results


def create_annotation_report(
    adata: AnnData,
    model_name: str,
    output_file: Optional[str] = None,
    label_col: str = 'celltypist_label',
    conf_col: str = 'celltypist_conf_score'
) -> str:
    """Create a text report of CellTypist annotation results.

    Args:
        adata: AnnData with CellTypist predictions
        model_name: Name of model used
        output_file: Optional file path to save report
        label_col: Column with predicted labels
        conf_col: Column with confidence scores

    Returns:
        Report text
    """
    label_col = _resolve_columns(adata, label_col,
                                  ['celltypist_label', 'majority_voting', 'predicted_labels'])
    conf_col = _resolve_columns(adata, conf_col,
                                 ['celltypist_conf_score', 'conf_score'])

    has_conf = conf_col in adata.obs.columns
    has_label = label_col in adata.obs.columns

    # Generate summary
    if has_label:
        summary = summarize_annotations(adata, label_col, conf_col)
        n_cell_types = len(summary)
    else:
        n_cell_types = 0
        summary = None

    report = f"""CellTypist Annotation Report
============================

Model: {model_name}
Date: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}

Dataset Summary
---------------
Total cells: {adata.n_obs}
Total genes: {adata.n_vars}
"""

    if has_label:
        report += f"""
Annotation Summary
------------------
Cell types identified: {n_cell_types}
"""
        if has_conf:
            mean_conf = adata.obs[conf_col].mean()
            median_conf = adata.obs[conf_col].median()
            high_conf = (adata.obs[conf_col] > 0.5).sum()
            high_conf_pct = (adata.obs[conf_col] > 0.5).mean() * 100
            report += f"""Mean confidence: {mean_conf:.3f}
Median confidence: {median_conf:.3f}
High confidence (>0.5): {high_conf} ({high_conf_pct:.1f}%)
"""

        report += """
Cell Type Breakdown
-------------------
"""
        if summary is not None:
            for _, row in summary.iterrows():
                report += f"\n{row['cell_type']}:\n"
                report += f"  Cells: {row['n_cells']} ({row['proportion']*100:.1f}%)\n"
                if has_conf and 'mean_confidence' in row:
                    report += f"  Mean confidence: {row['mean_confidence']:.3f}\n"

    if output_file:
        with open(output_file, 'w') as f:
            f.write(report)
        print(f"Report saved to: {output_file}")

    return report
