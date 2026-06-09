"""Tests for Plotly JSON adapter."""

import pytest
from homomics_lab.viz.plotly_adapter import to_plotly_json
from homomics_lab.viz.generator import PlotType


def test_umap_conversion():
    figure = to_plotly_json(
        PlotType.UMAP,
        data={
            "coordinates": [[1, 2], [3, 4], [5, 6], [7, 8]],
            "labels": ["A", "B", "A", "B"],
        },
        title="Test UMAP",
    )
    assert "data" in figure
    assert "layout" in figure
    assert figure["layout"]["title"]["text"] == "Test UMAP"
    assert len(figure["data"]) == 2  # Two unique labels


def test_heatmap_conversion():
    figure = to_plotly_json(
        PlotType.HEATMAP,
        data={"matrix": [[1, 2], [3, 4]], "row_labels": ["R1", "R2"], "col_labels": ["C1", "C2"]},
    )
    assert figure["data"][0]["type"] == "heatmap"
    assert figure["data"][0]["z"] == [[1, 2], [3, 4]]


def test_violin_conversion():
    figure = to_plotly_json(
        PlotType.VIOLIN,
        data={"groups": {"A": [1, 2, 3], "B": [4, 5, 6]}},
    )
    assert len(figure["data"]) == 2
    assert figure["data"][0]["type"] == "violin"


def test_bar_conversion():
    figure = to_plotly_json(
        PlotType.BAR,
        data={"categories": ["X", "Y"], "values": [10, 20]},
    )
    assert figure["data"][0]["type"] == "bar"


def test_scatter_conversion():
    figure = to_plotly_json(
        PlotType.SCATTER,
        data={"x": [1, 2, 3], "y": [4, 5, 6]},
    )
    assert figure["data"][0]["type"] == "scatter"


def test_histogram_conversion():
    figure = to_plotly_json(
        PlotType.HISTOGRAM,
        data={"values": [1, 2, 2, 3, 3, 3], "bins": 5},
    )
    assert figure["data"][0]["type"] == "histogram"


def test_default_data_generation():
    """When no data provided, dummy data is generated."""
    figure = to_plotly_json(PlotType.UMAP, data={})
    assert len(figure["data"]) > 0
