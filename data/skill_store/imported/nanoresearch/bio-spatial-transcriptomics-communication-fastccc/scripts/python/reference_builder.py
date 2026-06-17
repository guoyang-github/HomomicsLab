"""Reference panel building and query inference for FastCCC.

This module provides functions for building CCC reference panels and
performing reference-based CCC inference on query datasets.

Reference: Hou et al., Nature Communications 2025
"""

import os
import json
import numpy as np
import pandas as pd
import scanpy as sc
from anndata import AnnData
from typing import Optional, Union, List, Dict, Any, Tuple
from pathlib import Path
from collections import Counter


def build_reference_panel(
    adata: AnnData,
    database_file_path: str,
    reference_name: str,
    save_path: str = './reference_panels',
    groupby: Optional[str] = None,
    celltype_file_path: Optional[str] = None,
    meta_key: Optional[str] = None,
    min_percentile: float = 0.1,
    debug_mode: bool = False,
    for_uploading: bool = False
) -> str:
    """Build a CCC reference panel from single-cell data.

    This function creates a reference panel that can be used for
    reference-based CCC analysis on query datasets.

    Args:
        adata: AnnData object with reference data
        database_file_path: Path to LR interaction database
        reference_name: Name for the reference panel
        save_path: Directory to save the reference panel
        groupby: Column name for cell type annotations (if not using celltype_file_path)
        celltype_file_path: Path to cell type annotation file
        meta_key: Metadata key for cell types in adata.obs
        min_percentile: Minimum percentile threshold for expression
        debug_mode: Whether to enable debug mode
        for_uploading: Whether to prepare for uploading (smaller files)

    Returns:
        Path to the created reference panel directory
    """
    try:
        from fastccc import build_reference as fastccc_ref
    except ImportError:
        raise ImportError("FastCCC not installed. Install with: pip install fastccc")

    # Create cell type file if groupby is provided
    if groupby is not None and celltype_file_path is None:
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            celltype_file_path = f.name
            adata.obs[[groupby]].to_csv(f, sep='\t', index=True)
            temp_file_created = True
    else:
        temp_file_created = False

    try:
        # Build reference
        print(f"Building reference panel: {reference_name}")
        print(f"  Cells: {adata.n_obs}")
        print(f"  Genes: {adata.n_vars}")
        if meta_key:
            print(f"  Cell types: {adata.obs[meta_key].nunique()}")

        fastccc_ref.build_reference_workflow(
            database_file_path=database_file_path,
            reference_counts_file_path=adata,
            celltype_file_path=celltype_file_path,
            reference_name=reference_name,
            save_path=save_path,
            meta_key=meta_key,
            min_percentile=min_percentile,
            debug_mode=debug_mode,
            for_uploading=for_uploading
        )

        reference_path = os.path.join(save_path, reference_name)
        print(f"Reference panel created at: {reference_path}")

        return reference_path

    finally:
        if temp_file_created and os.path.exists(celltype_file_path):
            os.remove(celltype_file_path)


def infer_ccc_with_reference(
    adata: AnnData,
    database_file_path: str,
    reference_path: str,
    save_path: str = './reference_results',
    groupby: Optional[str] = None,
    celltype_file_path: Optional[str] = None,
    meta_key: Optional[str] = None,
    celltype_mapping_dict: Optional[Union[Dict[str, str], str]] = None,
    debug_mode: bool = False
) -> pd.DataFrame:
    """Infer CCC on query data using a reference panel.

    This function performs reference-based CCC inference, comparing
    query data against a pre-built reference panel.

    Args:
        adata: AnnData object with query data
        database_file_path: Path to LR interaction database
        reference_path: Path to reference panel directory
        save_path: Directory to save results
        groupby: Column name for cell type annotations
        celltype_file_path: Path to cell type annotation file
        meta_key: Metadata key for cell types in adata.obs
        celltype_mapping_dict: Mapping between query and reference cell types
            Can be a dictionary or path to JSON file
        debug_mode: Whether to enable debug mode

    Returns:
        DataFrame with inference results
    """
    try:
        from fastccc import infer_query as fastccc_infer
    except ImportError:
        raise ImportError("FastCCC not installed.")

    # Validate reference
    if not os.path.exists(reference_path):
        raise ValueError(f"Reference path does not exist: {reference_path}")

    required_files = ['config.toml', 'ref_percents.pkl', 'ref_mean_counts.pkl']
    for f in required_files:
        if not os.path.exists(os.path.join(reference_path, f)):
            raise ValueError(f"Reference file missing: {f}")

    # Create cell type file if groupby is provided
    if groupby is not None and celltype_file_path is None:
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            celltype_file_path = f.name
            adata.obs[[groupby]].to_csv(f, sep='\t', index=True)
            temp_file_created = True
    else:
        temp_file_created = False

    try:
        print(f"Running reference-based CCC inference...")
        print(f"  Query cells: {adata.n_obs}")
        print(f"  Reference: {reference_path}")

        fastccc_infer.infer_query_workflow(
            database_file_path=database_file_path,
            reference_path=reference_path,
            query_counts_file_path=adata,
            celltype_file_path=celltype_file_path,
            save_path=save_path,
            celltype_mapping_dict=celltype_mapping_dict,
            meta_key=meta_key,
            debug_mode=debug_mode
        )

        # Load results
        results_file = os.path.join(save_path, 'query_infer_results.tsv')
        if os.path.exists(results_file):
            results = pd.read_csv(results_file, sep='\t')
            print(f"Inference complete! {len(results)} interactions analyzed.")
            return results
        else:
            print("Warning: Results file not found")
            return pd.DataFrame()

    finally:
        if temp_file_created and os.path.exists(celltype_file_path):
            os.remove(celltype_file_path)


def update_reference_for_activation(reference_path: str) -> None:
    """Update reference panel for first-time activation.

    This function computes essential reference data during first-time
    usage to minimize storage requirements.

    Args:
        reference_path: Path to reference panel directory
    """
    try:
        from fastccc import infer_query as fastccc_infer
    except ImportError:
        raise ImportError("FastCCC not installed.")

    if not os.path.exists(reference_path):
        raise ValueError(f"Reference path does not exist: {reference_path}")

    print(f"Updating reference panel for activation: {reference_path}")
    fastccc_infer.update_reference_for_first_time_activation(reference_path)
    print("Reference panel updated successfully!")


def create_celltype_mapping(
    query_celltypes: List[str],
    reference_celltypes: List[str],
    mapping: Optional[Dict[str, str]] = None
) -> Dict[str, str]:
    """Create cell type mapping between query and reference.

    Args:
        query_celltypes: List of cell types in query data
        reference_celltypes: List of cell types in reference
        mapping: Optional predefined mapping

    Returns:
        Dictionary mapping reference cell types to query cell types
    """
    if mapping is not None:
        return mapping

    # Auto-mapping: match identical names
    mapping = {}
    for ref_ct in reference_celltypes:
        if ref_ct in query_celltypes:
            mapping[ref_ct] = ref_ct

    return mapping


def save_celltype_mapping(
    mapping: Dict[str, str],
    output_file: str
) -> str:
    """Save cell type mapping to JSON file.

    Args:
        mapping: Dictionary mapping reference to query cell types
        output_file: Output JSON file path

    Returns:
        Path to saved file
    """
    with open(output_file, 'w') as f:
        json.dump(mapping, f, indent=2)
    return output_file


def load_celltype_mapping(
    mapping_file: str
) -> Dict[str, str]:
    """Load cell type mapping from JSON file.

    Args:
        mapping_file: Path to JSON mapping file

    Returns:
        Dictionary mapping reference to query cell types
    """
    with open(mapping_file, 'r') as f:
        return json.load(f)


def get_reference_info(reference_path: str) -> Dict[str, Any]:
    """Get information about a reference panel.

    Args:
        reference_path: Path to reference panel directory

    Returns:
        Dictionary with reference information
    """
    import tomllib

    config_file = os.path.join(reference_path, 'config.toml')
    if not os.path.exists(config_file):
        raise ValueError(f"Config file not found: {config_file}")

    with open(config_file, 'rb') as f:
        config = tomllib.load(f)

    info = {
        'reference_name': config.get('reference_name', 'Unknown'),
        'min_percentile': config.get('min_percentile', 'Unknown'),
        'lri_database': config.get('LRI_database', 'Unknown'),
        'celltypes': dict(config.get('celltype', {}))
    }

    # Calculate total cells
    info['total_cells'] = sum(info['celltypes'].values())
    info['n_celltypes'] = len(info['celltypes'])

    return info


def list_available_references(
    references_dir: str = './reference_panels'
) -> pd.DataFrame:
    """List available reference panels.

    Args:
        references_dir: Directory containing reference panels

    Returns:
        DataFrame with reference information
    """
    if not os.path.exists(references_dir):
        return pd.DataFrame()

    references = []
    for ref_name in os.listdir(references_dir):
        ref_path = os.path.join(references_dir, ref_name)
        if os.path.isdir(ref_path):
            try:
                info = get_reference_info(ref_path)
                info['path'] = ref_path
                references.append(info)
            except Exception as e:
                print(f"Warning: Could not read reference {ref_name}: {e}")

    return pd.DataFrame(references)


def compare_with_reference(
    query_results: pd.DataFrame,
    reference_results: Optional[pd.DataFrame] = None,
    comparison_column: str = 'trend_vs_ref'
) -> Dict[str, int]:
    """Summarize comparison between query and reference.

    Args:
        query_results: DataFrame with query inference results
        reference_results: Optional DataFrame with reference results
        comparison_column: Column name for comparison results

    Returns:
        Dictionary with comparison counts
    """
    if comparison_column not in query_results.columns:
        raise ValueError(f"Comparison column '{comparison_column}' not found")

    comparison_counts = query_results[comparison_column].value_counts().to_dict()

    return comparison_counts


def get_fastccc_reference_panels() -> Dict[str, str]:
    """Get URLs or paths to pre-built FastCCC reference panels.

    Returns:
        Dictionary mapping tissue names to reference panel info
    """
    # These are placeholder - actual panels would be downloaded from FastCCC repository
    panels = {
        'human_pbmc': {
            'description': 'Human PBMC reference panel',
            'celltypes': 45,
            'cells': '~5M'
        },
        'human_lung': {
            'description': 'Human lung tissue reference panel',
            'celltypes': 38,
            'cells': '~2M'
        },
        'human_intestine': {
            'description': 'Human intestine reference panel',
            'celltypes': 52,
            'cells': '~3M'
        }
    }

    return panels
