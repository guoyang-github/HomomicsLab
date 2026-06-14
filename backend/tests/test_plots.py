"""Tests for plot extraction utilities."""

import base64
from pathlib import Path

import pytest

from homomics_lab.models.common import PlotAttachment
from homomics_lab.plots import extract_plot_attachments


def test_extract_plot_data():
    """Interactive Plotly data should be detected."""
    skill_output = {
        "plot_data": {"data": [{"x": [1, 2], "y": [3, 4]}], "layout": {"title": "Test"}},
        "plot_type": "umap",
        "title": "UMAP Plot",
        "caption": "Cells colored by cluster",
    }

    attachments = extract_plot_attachments(skill_output)

    assert len(attachments) == 1
    assert attachments[0].plot_type == "umap"
    assert attachments[0].title == "UMAP Plot"
    assert attachments[0].caption == "Cells colored by cluster"
    assert attachments[0].data == skill_output["plot_data"]


def test_extract_image_base64():
    """Base64 embedded image should be detected."""
    skill_output = {
        "image_base64": "iVBORw0KGgo=",
        "plot_type": "qc",
        "title": "QC Plot",
    }

    attachments = extract_plot_attachments(skill_output)

    assert len(attachments) == 1
    assert attachments[0].image_base64 == "iVBORw0KGgo="
    assert attachments[0].plot_type == "qc"


def test_extract_plot_path(tmp_path: Path):
    """Static image file path should be detected and converted to base64."""
    image_path = tmp_path / "umap.png"
    image_path.write_bytes(b"fake-png-bytes")

    skill_output = {
        "plot_path": str(image_path),
        "plot_type": "umap",
        "title": "UMAP",
    }

    attachments = extract_plot_attachments(skill_output)

    assert len(attachments) == 1
    assert attachments[0].file_path == str(image_path)
    content = attachments[0].to_chat_content()
    assert content["image_base64"] == base64.b64encode(b"fake-png-bytes").decode("utf-8")


def test_extract_phase_specific_keys():
    """Phase-specific keys like umap_path should be detected."""
    skill_output = {
        "umap_path": "/tmp/umap.png",
        "tsne_path": "/tmp/tsne.png",
    }

    attachments = extract_plot_attachments(skill_output, default_plot_type="clustering")

    assert len(attachments) == 2
    assert attachments[0].file_path == "/tmp/umap.png"
    assert attachments[1].file_path == "/tmp/tsne.png"


def test_no_plots_returns_empty():
    """Non-plot skill output should produce no attachments."""
    assert extract_plot_attachments({"cells": 1000}) == []


def test_non_dict_input_returns_empty():
    """Non-dict skill output should be handled gracefully."""
    assert extract_plot_attachments(None) == []
    assert extract_plot_attachments("raw text") == []


def test_plot_attachment_to_chat_content_prefers_data():
    """PlotAttachment should prefer plot_data over image_base64."""
    attachment = PlotAttachment(
        plot_type="test",
        title="Test",
        data={"x": [1]},
        image_base64="should-not-appear",
    )
    content = attachment.to_chat_content()
    assert "data" in content
    assert "image_base64" not in content
