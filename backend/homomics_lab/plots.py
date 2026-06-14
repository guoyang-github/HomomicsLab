"""Shared utilities for extracting plot attachments from skill outputs.

This module provides a lightweight, reusable helper that can be used by any
component (TurnRunner, chat API, InterpretationEngine, etc.) to detect
visualization outputs and convert them into chat-friendly ``PlotAttachment``
objects.
"""

from typing import Any, Dict, List

from homomics_lab.models.common import PlotAttachment


def extract_plot_attachments(
    skill_output: Dict[str, Any],
    default_plot_type: str = "visualization",
    default_title: str = "Visualization",
) -> List[PlotAttachment]:
    """Extract plot attachments from a skill execution result.

    Supports the following conventions:

    - ``plot_data``: interactive Plotly/JSON data (rendered as ``plot_data``
      message type).
    - ``plot_path`` / ``figure`` / ``image_path``: path to a static image file
      (rendered as ``plot`` message type).
    - Phase-specific keys such as ``umap_path``, ``tsne_path``,
      ``volcano_plot_path``, etc.

    Args:
        skill_output: The dictionary returned by a skill execution.
        default_plot_type: Fallback plot type when not specified.
        default_title: Fallback title when not specified.

    Returns:
        A list of ``PlotAttachment`` objects ready to be turned into chat
        messages.
    """
    if not isinstance(skill_output, dict):
        return []

    plots: List[PlotAttachment] = []
    plot_type = skill_output.get("plot_type", default_plot_type)
    title = skill_output.get("title", default_title)
    caption = skill_output.get("caption", "")

    # Case 1: Interactive Plotly-like data.
    if "plot_data" in skill_output:
        plots.append(
            PlotAttachment(
                plot_type=plot_type,
                title=title,
                caption=caption,
                data=skill_output["plot_data"],
            )
        )
        return plots

    # Case 2: Generic image path or figure reference.
    for key in ("plot_path", "figure", "image_path"):
        if key in skill_output:
            plots.append(
                PlotAttachment(
                    plot_type=plot_type,
                    title=title,
                    caption=caption,
                    file_path=skill_output[key],
                )
            )
            return plots

    # Case 3: Image already embedded as base64.
    if "image_base64" in skill_output:
        plots.append(
            PlotAttachment(
                plot_type=plot_type,
                title=title,
                caption=caption,
                image_base64=skill_output["image_base64"],
            )
        )
        return plots

    # Case 4: Phase-specific known output keys.
    phase_plot_keys = {
        "qc": [("qc_plot_path", "QC distribution")],
        "clustering": [
            ("umap_path", "UMAP visualization"),
            ("tsne_path", "t-SNE visualization"),
        ],
        "dim_reduction": [
            ("pca_plot_path", "PCA plot"),
            ("umap_path", "UMAP visualization"),
        ],
        "differential_expression": [
            ("volcano_plot_path", "Volcano plot"),
            ("heatmap_path", "DE heatmap"),
        ],
        "spatial_clustering": [("spatial_plot_path", "Spatial cluster plot")],
        "visualization": [
            ("plot_path", "Visualization"),
            ("figure", "Visualization"),
        ],
    }

    for key, key_title in phase_plot_keys.get(default_plot_type, []):
        if key in skill_output:
            plots.append(
                PlotAttachment(
                    plot_type=plot_type,
                    title=skill_output.get("title", key_title),
                    caption=caption,
                    file_path=skill_output[key],
                )
            )

    return plots
