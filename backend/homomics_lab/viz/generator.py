"""Plot generation for bioinformatics visualizations.

Generates static plots using matplotlib and returns them as base64 PNG strings
or saves to file.
"""

import base64
import io
from enum import Enum
from typing import Any, Dict, List, Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


class PlotType(str, Enum):
    UMAP = "umap"
    HEATMAP = "heatmap"
    VIOLIN = "violin"
    BAR = "bar"
    SCATTER = "scatter"
    HISTOGRAM = "histogram"


class PlotGenerator:
    """Generate bioinformatics plots from data."""

    def __init__(self, style: str = "default"):
        plt.style.use(style)

    def generate(
        self,
        plot_type: PlotType,
        data: Dict[str, Any],
        title: str = "",
        width: int = 8,
        height: int = 6,
        dpi: int = 100,
    ) -> str:
        """Generate a plot and return as base64 PNG string.

        Args:
            plot_type: Type of plot to generate
            data: Plot data (structure varies by plot type)
            title: Plot title
            width: Figure width in inches
            height: Figure height in inches
            dpi: Resolution

        Returns:
            Base64-encoded PNG image string
        """
        fig, ax = plt.subplots(figsize=(width, height), dpi=dpi)

        try:
            if plot_type == PlotType.UMAP:
                self._render_umap(ax, data)
            elif plot_type == PlotType.HEATMAP:
                self._render_heatmap(ax, data)
            elif plot_type == PlotType.VIOLIN:
                self._render_violin(ax, data)
            elif plot_type == PlotType.BAR:
                self._render_bar(ax, data)
            elif plot_type == PlotType.SCATTER:
                self._render_scatter(ax, data)
            elif plot_type == PlotType.HISTOGRAM:
                self._render_histogram(ax, data)
            else:
                raise ValueError(f"Unsupported plot type: {plot_type}")

            if title:
                ax.set_title(title)

            plt.tight_layout()

            # Save to buffer
            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
            buf.seek(0)
            img_base64 = base64.b64encode(buf.read()).decode("utf-8")
            return img_base64

        finally:
            plt.close(fig)

    def _render_umap(self, ax: plt.Axes, data: Dict[str, Any]) -> None:
        """Render UMAP scatter plot."""
        coords = data.get("coordinates", [])
        labels = data.get("labels", None)
        colors = data.get("colors", None)

        if not coords:
            # Generate dummy data if none provided
            np.random.seed(42)
            n = data.get("n_points", 100)
            coords = np.random.randn(n, 2).tolist()
            labels = [f"C{i % 5}" for i in range(n)]

        coords = np.array(coords)
        x, y = coords[:, 0], coords[:, 1]

        if labels is not None:
            unique_labels = sorted(set(labels))
            cmap = plt.colormaps["tab20"].resampled(len(unique_labels))
            for i, label in enumerate(unique_labels):
                mask = [l == label for l in labels]
                ax.scatter(
                    x[mask], y[mask],
                    c=[cmap(i)], label=str(label),
                    s=10, alpha=0.7, edgecolors="none",
                )
            ax.legend(bbox_to_anchor=(1.05, 1), loc="upper left", fontsize=8)
        else:
            ax.scatter(x, y, s=10, alpha=0.7, c=colors, edgecolors="none")

        ax.set_xlabel("UMAP 1")
        ax.set_ylabel("UMAP 2")

    def _render_heatmap(self, ax: plt.Axes, data: Dict[str, Any]) -> None:
        """Render heatmap."""
        matrix = data.get("matrix", [])
        row_labels = data.get("row_labels", None)
        col_labels = data.get("col_labels", None)

        if not matrix:
            # Dummy data
            np.random.seed(42)
            matrix = np.random.randn(10, 10)

        matrix = np.array(matrix)
        im = ax.imshow(matrix, cmap="viridis", aspect="auto")

        if row_labels:
            ax.set_yticks(range(len(row_labels)))
            ax.set_yticklabels(row_labels, fontsize=8)
        if col_labels:
            ax.set_xticks(range(len(col_labels)))
            ax.set_xticklabels(col_labels, fontsize=8, rotation=45, ha="right")

        plt.colorbar(im, ax=ax)

    def _render_violin(self, ax: plt.Axes, data: Dict[str, Any]) -> None:
        """Render violin plot."""
        groups = data.get("groups", {})

        if not groups:
            # Dummy data
            np.random.seed(42)
            groups = {
                "Group A": np.random.normal(0, 1, 100).tolist(),
                "Group B": np.random.normal(2, 1.5, 100).tolist(),
                "Group C": np.random.normal(-1, 0.5, 100).tolist(),
            }

        positions = range(len(groups))
        values = list(groups.values())
        labels = list(groups.keys())

        parts = ax.violinplot(values, positions=positions, showmeans=True, showmedians=True)
        for pc in parts["bodies"]:
            pc.set_facecolor("steelblue")
            pc.set_alpha(0.7)

        ax.set_xticks(positions)
        ax.set_xticklabels(labels, rotation=45, ha="right")
        ax.set_ylabel("Value")

    def _render_bar(self, ax: plt.Axes, data: Dict[str, Any]) -> None:
        """Render bar chart."""
        categories = data.get("categories", [])
        values = data.get("values", [])

        if not categories:
            categories = ["A", "B", "C", "D"]
            values = [10, 20, 15, 25]

        ax.bar(categories, values, color="steelblue")
        ax.set_ylabel("Count")

    def _render_scatter(self, ax: plt.Axes, data: Dict[str, Any]) -> None:
        """Render scatter plot."""
        x = data.get("x", [])
        y = data.get("y", [])
        c = data.get("color", None)

        if not x:
            np.random.seed(42)
            x = np.random.randn(100).tolist()
            y = np.random.randn(100).tolist()

        ax.scatter(x, y, c=c, s=20, alpha=0.7, edgecolors="none")
        ax.set_xlabel(data.get("xlabel", "X"))
        ax.set_ylabel(data.get("ylabel", "Y"))

    def _render_histogram(self, ax: plt.Axes, data: Dict[str, Any]) -> None:
        """Render histogram."""
        values = data.get("values", [])
        bins = data.get("bins", 20)

        if not values:
            np.random.seed(42)
            values = np.random.randn(1000).tolist()

        ax.hist(values, bins=bins, color="steelblue", edgecolor="white")
        ax.set_xlabel("Value")
        ax.set_ylabel("Frequency")
