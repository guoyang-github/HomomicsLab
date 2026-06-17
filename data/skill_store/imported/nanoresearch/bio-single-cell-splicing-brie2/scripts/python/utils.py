"""
Utility functions for BRIE2 splicing analysis.
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any
import logging

import numpy as np
import pandas as pd
import scanpy as sc
from anndata import AnnData

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_brie_data(file_path: str, format: str = "auto") -> AnnData:
    """
    Load BRIE2 data from various formats.

    Parameters
    ----------
    file_path : str
        Path to data file
    format : str, default='auto'
        File format: 'h5ad', 'npz', or 'auto'

    Returns
    -------
    AnnData object
    """
    try:
        import brie
    except ImportError:
        raise ImportError("brie is not installed")

    if format == "auto":
        if file_path.endswith(".h5ad"):
            format = "h5ad"
        elif file_path.endswith(".npz"):
            format = "npz"
        else:
            raise ValueError(f"Cannot detect format from {file_path}")

    if format == "h5ad":
        return brie.read_h5ad(file_path)
    elif format == "npz":
        return brie.read_npz(file_path)
    else:
        raise ValueError(f"Unknown format: {format}")


def validate_adata_for_brie(
    adata: AnnData,
    layer_keys: List[str] = ["isoform1", "isoform2", "ambiguous"],
    require_psi: bool = False,
) -> bool:
    """
    Validate AnnData has required structure for BRIE analysis.

    Parameters
    ----------
    adata : AnnData
        Input AnnData
    layer_keys : list
        Required layer names
    require_psi : bool, default=False
        Require PSI layer to exist

    Returns
    -------
    bool : True if valid

    Raises
    ------
    ValueError if validation fails
    """
    import warnings

    # Check layers
    for key in layer_keys:
        if key not in adata.layers:
            raise ValueError(f"Required layer '{key}' not found in adata.layers")

    # Check dimensions match
    shape = adata.layers[layer_keys[0]].shape
    for key in layer_keys:
        if adata.layers[key].shape != shape:
            raise ValueError(f"Layer '{key}' has mismatched shape")

    # Check for PSI layer if required
    if require_psi:
        has_psi = "psi" in adata.layers or (hasattr(adata.X, "shape") and adata.X is not None)
        if not has_psi:
            raise ValueError("PSI values not found. Run brie-quant first.")

    # Check for required var columns (gene info)
    if "GeneID" not in adata.var.columns and adata.var.index.name != "GeneID":
        warnings.warn("GeneID not found in adata.var")

    return True


def prepare_cell_features(
    adata: AnnData,
    features: Union[str, List[str]],
    encode_categorical: bool = True,
    normalize: bool = False,
) -> Tuple[np.ndarray, List[str]]:
    """
    Prepare cell features for BRIE differential analysis.

    Parameters
    ----------
    adata : AnnData
        Input AnnData
    features : str or list
        Column(s) in adata.obs to use as features
    encode_categorical : bool, default=True
        One-hot encode categorical variables
    normalize : bool, default=False
        Normalize continuous features to 0-1

    Returns
    -------
    Tuple of (feature_matrix, feature_names)
    """
    if isinstance(features, str):
        features = [features]

    feature_list = []
    feature_names = []

    for feat in features:
        if feat not in adata.obs.columns:
            raise ValueError(f"Feature '{feat}' not found in adata.obs")

        data = adata.obs[feat]

        if data.dtype == "category" or data.dtype == object:
            if encode_categorical:
                # One-hot encode
                dummies = pd.get_dummies(data, prefix=feat)
                feature_list.append(dummies.values)
                feature_names.extend(dummies.columns.tolist())
            else:
                # Numeric encoding
                codes, _ = pd.factorize(data)
                feature_list.append(codes.reshape(-1, 1))
                feature_names.append(feat)
        else:
            # Continuous
            values = data.values.reshape(-1, 1)
            if normalize:
                values = (values - values.min()) / (values.max() - values.min())
            feature_list.append(values)
            feature_names.append(feat)

    X = np.hstack(feature_list) if len(feature_list) > 1 else feature_list[0]

    return X.astype(np.float32), feature_names


def export_results(
    adata: AnnData,
    output_dir: str,
    prefix: str = "brie",
    export_psi: bool = True,
    export_stats: bool = True,
    export_layers: bool = False,
) -> Dict[str, str]:
    """
    Export BRIE results to multiple formats.

    Parameters
    ----------
    adata : AnnData
        BRIE quantified data
    output_dir : str
        Output directory
    prefix : str, default='brie'
        File prefix
    export_psi : bool, default=True
        Export PSI matrix
    export_stats : bool, default=True
        Export statistics
    export_layers : bool, default=False
        Export count layers

    Returns
    -------
    Dict mapping output type to file path
    """
    try:
        import brie
    except ImportError:
        raise ImportError("brie is not installed")

    os.makedirs(output_dir, exist_ok=True)
    outputs = {}

    # Export full h5ad
    h5ad_path = os.path.join(output_dir, f"{prefix}_results.h5ad")
    adata.write_h5ad(h5ad_path)
    outputs["h5ad"] = h5ad_path

    # Export PSI matrix
    if export_psi:
        psi = adata.X if hasattr(adata.X, "shape") else adata.layers.get("psi", adata.X)
        psi_df = pd.DataFrame(
            psi,
            index=adata.obs_names,
            columns=adata.var_names,
        )
        psi_path = os.path.join(output_dir, f"{prefix}_psi.tsv")
        psi_df.to_csv(psi_path, sep="\t")
        outputs["psi"] = psi_path

    # Export statistics
    if export_stats:
        try:
            stats_df = brie.io.dump_results(adata)
            stats_path = os.path.join(output_dir, f"{prefix}_stats.tsv")
            stats_df.to_csv(stats_path, sep="\t", index=True)
            outputs["stats"] = stats_path
        except Exception as e:
            logger.warning(f"Could not export stats: {e}")

    # Export layers
    if export_layers:
        for layer in ["isoform1", "isoform2", "ambiguous"]:
            if layer in adata.layers:
                layer_df = pd.DataFrame(
                    adata.layers[layer],
                    index=adata.obs_names,
                    columns=adata.var_names,
                )
                layer_path = os.path.join(output_dir, f"{prefix}_{layer}.tsv")
                layer_df.to_csv(layer_path, sep="\t")
                outputs[layer] = layer_path

    return outputs


def summarize_splicing_results(
    adata: AnnData,
    groupby: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate summary statistics for splicing results.

    Parameters
    ----------
    adata : AnnData
        BRIE quantified data
    groupby : str, optional
        Column in adata.obs for grouping

    Returns
    -------
    Dict with summary statistics
    """
    summary = {}

    # Overall statistics
    psi = adata.X if hasattr(adata.X, "shape") else adata.layers.get("psi", adata.X)
    summary["n_cells"] = adata.n_obs
    summary["n_events"] = adata.n_vars
    summary["psi_mean"] = float(np.nanmean(psi))
    summary["psi_std"] = float(np.nanstd(psi))
    summary["psi_range"] = (float(np.nanmin(psi)), float(np.nanmax(psi)))

    # Event statistics
    event_means = np.nanmean(psi, axis=0)
    summary["variable_events"] = int(np.sum(np.nanvar(psi, axis=0) > 0.01))
    summary["bimodal_events"] = int(np.sum((event_means > 0.2) & (event_means < 0.8)))

    # Check for differential results
    if "brie_version" in adata.uns:
        summary["brie_version"] = adata.uns["brie_version"]

    try:
        import brie
        stats_df = brie.io.dump_results(adata)
        if "qval" in stats_df.columns:
            summary["significant_events"] = int(np.sum(stats_df["qval"] < 0.05))
            summary["top_event"] = stats_df.sort_values("qval").index[0]
    except:
        pass

    # Group-specific summaries
    if groupby is not None and groupby in adata.obs.columns:
        summary["groups"] = {}
        for group in adata.obs[groupby].unique():
            mask = adata.obs[groupby] == group
            group_psi = psi[mask]
            summary["groups"][group] = {
                "n_cells": int(mask.sum()),
                "mean_psi": float(np.nanmean(group_psi)),
                "std_psi": float(np.nanstd(group_psi)),
            }

    return summary


def create_splicing_report(
    adata: AnnData,
    output_file: str = "brie_report.html",
    title: str = "BRIE2 Splicing Analysis Report",
) -> str:
    """
    Create HTML report for BRIE2 analysis.

    Parameters
    ----------
    adata : AnnData
        BRIE quantified data
    output_file : str, default='brie_report.html'
        Output HTML file path
    title : str, default='BRIE2 Splicing Analysis Report'
        Report title

    Returns
    -------
    Path to output file
    """
    summary = summarize_splicing_results(adata)

    html = f"""
    <html>
    <head>
        <title>{title}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; }}
            h1 {{ color: #2c3e50; }}
            h2 {{ color: #34495e; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
            table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
            th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
            th {{ background-color: #3498db; color: white; }}
            tr:nth-child(even) {{ background-color: #f2f2f2; }}
            .metric {{ font-size: 24px; font-weight: bold; color: #2980b9; }}
        </style>
    </head>
    <body>
        <h1>{title}</h1>

        <h2>Overview</h2>
        <table>
            <tr><th>Metric</th><th>Value</th></tr>
            <tr><td>Cells</td><td class="metric">{summary['n_cells']}</td></tr>
            <tr><td>Splicing Events</td><td class="metric">{summary['n_events']}</td></tr>
            <tr><td>Mean PSI</td><td>{summary['psi_mean']:.3f}</td></tr>
            <tr><td>PSI Std</td><td>{summary['psi_std']:.3f}</td></tr>
            <tr><td>Variable Events</td><td>{summary.get('variable_events', 'N/A')}</td></tr>
            <tr><td>Bimodal Events</td><td>{summary.get('bimodal_events', 'N/A')}</td></tr>
    """

    if "significant_events" in summary:
        html += f"""
            <tr><td>Significant Events (q<0.05)</td><td class="metric">{summary['significant_events']}</td></tr>
        """

    html += "</table>"

    # Group summary if available
    if "groups" in summary:
        html += "<h2>Group Summary</h2><table>"
        html += "<tr><th>Group</th><th>Cells</th><th>Mean PSI</th><th>Std PSI</th></tr>"
        for group, stats in summary["groups"].items():
            html += f"""
                <tr>
                    <td>{group}</td>
                    <td>{stats['n_cells']}</td>
                    <td>{stats['mean_psi']:.3f}</td>
                    <td>{stats['std_psi']:.3f}</td>
                </tr>
            """
        html += "</table>"

    html += "</body></html>"

    with open(output_file, "w") as f:
        f.write(html)

    logger.info(f"Report saved to {output_file}")
    return output_file


def check_brie_installation() -> Dict[str, Any]:
    """
    Check BRIE2 installation and dependencies.

    Returns
    -------
    Dict with installation status
    """
    results = {
        "brie_installed": False,
        "version": None,
        "tensorflow": False,
        "pysam": False,
        "errors": [],
    }

    try:
        import brie
        results["brie_installed"] = True
        results["version"] = brie.__version__
    except ImportError as e:
        results["errors"].append(f"brie not installed: {e}")

    try:
        import tensorflow as tf
        results["tensorflow"] = True
        results["tensorflow_version"] = tf.__version__
    except ImportError:
        results["errors"].append("tensorflow not installed (required for quantification)")

    try:
        import pysam
        results["pysam"] = True
        results["pysam_version"] = pysam.__version__
    except ImportError:
        results["errors"].append("pysam not installed (required for counting)")

    return results
