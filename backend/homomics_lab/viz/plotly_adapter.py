"""Convert internal plot data to Plotly-compatible JSON format.

Allows frontend to render interactive charts using react-plotly.js
instead of static base64 PNG images.
"""

from typing import Any, Dict, List

from homomics_lab.viz.generator import PlotType


def to_plotly_json(
    plot_type: PlotType,
    data: Dict[str, Any],
    title: str = "",
    width: int = 800,
    height: int = 600,
) -> Dict[str, Any]:
    """Convert plot data to Plotly figure JSON.

    Returns a dict with 'data' (traces) and 'layout' keys.
    """
    converters = {
        PlotType.UMAP: _convert_umap,
        PlotType.HEATMAP: _convert_heatmap,
        PlotType.VIOLIN: _convert_violin,
        PlotType.BAR: _convert_bar,
        PlotType.SCATTER: _convert_scatter,
        PlotType.HISTOGRAM: _convert_histogram,
    }

    converter = converters.get(plot_type)
    if converter is None:
        raise ValueError(f"Unsupported plot type for Plotly: {plot_type}")

    figure = converter(data)
    figure["layout"].update(
        {
            "title": {"text": title} if title else None,
            "width": width,
            "height": height,
            "paper_bgcolor": "rgba(0,0,0,0)",
            "plot_bgcolor": "rgba(0,0,0,0)",
            "font": {"family": "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"},
        }
    )
    return figure


def _convert_umap(data: Dict[str, Any]) -> Dict[str, Any]:
    coords = data.get("coordinates", [])
    labels = data.get("labels", None)
    colors = data.get("colors", None)

    import numpy as np

    if not coords:
        np.random.seed(42)
        n = data.get("n_points", 100)
        coords = np.random.randn(n, 2).tolist()
        labels = [f"C{i % 5}" for i in range(n)]

    coords = np.array(coords)
    x, y = coords[:, 0].tolist(), coords[:, 1].tolist()

    traces = []
    if labels is not None:
        unique_labels = sorted(set(labels))
        palette = [
            "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
            "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
        ]
        for i, label in enumerate(unique_labels):
            mask = [l == label for l in labels]
            traces.append(
                {
                    "type": "scatter",
                    "mode": "markers",
                    "name": str(label),
                    "x": [x[j] for j in range(len(x)) if mask[j]],
                    "y": [y[j] for j in range(len(y)) if mask[j]],
                    "marker": {
                        "size": 6,
                        "opacity": 0.7,
                        "color": palette[i % len(palette)],
                    },
                    "hovertemplate": f"<b>Cluster {label}</b><br>UMAP 1: %{{x:.2f}}<br>UMAP 2: %{{y:.2f}}<extra></extra>",
                }
            )
    else:
        traces.append(
            {
                "type": "scatter",
                "mode": "markers",
                "x": x,
                "y": y,
                "marker": {"size": 6, "opacity": 0.7, "color": colors or "#1f77b4"},
            }
        )

    return {
        "data": traces,
        "layout": {
            "xaxis": {"title": "UMAP 1", "showgrid": False},
            "yaxis": {"title": "UMAP 2", "showgrid": False},
            "hovermode": "closest",
        },
    }


def _convert_heatmap(data: Dict[str, Any]) -> Dict[str, Any]:
    matrix = data.get("matrix", [])
    row_labels = data.get("row_labels", None)
    col_labels = data.get("col_labels", None)

    import numpy as np

    if not matrix:
        np.random.seed(42)
        matrix = np.random.randn(10, 10).tolist()

    return {
        "data": [
            {
                "type": "heatmap",
                "z": matrix,
                "x": col_labels,
                "y": row_labels,
                "colorscale": "Viridis",
                "hovertemplate": "%{y} / %{x}<br>Value: %{z:.3f}<extra></extra>",
            }
        ],
        "layout": {
            "xaxis": {"title": None, "tickangle": -45},
            "yaxis": {"title": None},
        },
    }


def _convert_violin(data: Dict[str, Any]) -> Dict[str, Any]:
    groups = data.get("groups", {})

    import numpy as np

    if not groups:
        np.random.seed(42)
        groups = {
            "Group A": np.random.normal(0, 1, 100).tolist(),
            "Group B": np.random.normal(2, 1.5, 100).tolist(),
            "Group C": np.random.normal(-1, 0.5, 100).tolist(),
        }

    traces = []
    for group_name, values in groups.items():
        traces.append(
            {
                "type": "violin",
                "y": values,
                "name": group_name,
                "box": {"visible": True},
                "meanline": {"visible": True},
                "opacity": 0.7,
                "hovertemplate": f"<b>{group_name}</b><br>Value: %{{y:.3f}}<extra></extra>",
            }
        )

    return {
        "data": traces,
        "layout": {
            "yaxis": {"title": "Value", "zeroline": False},
            "violingroupgap": 0.1,
        },
    }


def _convert_bar(data: Dict[str, Any]) -> Dict[str, Any]:
    categories = data.get("categories", [])
    values = data.get("values", [])

    if not categories:
        categories = ["A", "B", "C", "D"]
        values = [10, 20, 15, 25]

    return {
        "data": [
            {
                "type": "bar",
                "x": categories,
                "y": values,
                "marker": {"color": "#4682b4"},
                "hovertemplate": "%{x}<br>Count: %{y}<extra></extra>",
            }
        ],
        "layout": {"yaxis": {"title": "Count"}},
    }


def _convert_scatter(data: Dict[str, Any]) -> Dict[str, Any]:
    x = data.get("x", [])
    y = data.get("y", [])
    c = data.get("color", None)

    import numpy as np

    if not x:
        np.random.seed(42)
        x = np.random.randn(100).tolist()
        y = np.random.randn(100).tolist()

    marker = {"size": 8, "opacity": 0.7}
    if c is not None:
        marker["color"] = c
        marker["colorscale"] = "Viridis"
        marker["showscale"] = True

    return {
        "data": [
            {
                "type": "scatter",
                "mode": "markers",
                "x": x,
                "y": y,
                "marker": marker,
                "hovertemplate": "%{xlabel}: %{x:.3f}<br>%{ylabel}: %{y:.3f}<extra></extra>",
            }
        ],
        "layout": {
            "xaxis": {"title": data.get("xlabel", "X")},
            "yaxis": {"title": data.get("ylabel", "Y")},
        },
    }


def _convert_histogram(data: Dict[str, Any]) -> Dict[str, Any]:
    values = data.get("values", [])
    bins = data.get("bins", 20)

    import numpy as np

    if not values:
        np.random.seed(42)
        values = np.random.randn(1000).tolist()

    return {
        "data": [
            {
                "type": "histogram",
                "x": values,
                "nbinsx": bins,
                "marker": {"color": "#4682b4", "line": {"color": "white", "width": 1}},
                "hovertemplate": "Bin: %{x}<br>Count: %{y}<extra></extra>",
            }
        ],
        "layout": {
            "xaxis": {"title": "Value"},
            "yaxis": {"title": "Frequency"},
            "bargap": 0.05,
        },
    }
