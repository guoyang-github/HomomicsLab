"""Tests for artifact classification and collection."""

from types import SimpleNamespace

from homomics_lab.artifacts import (
    build_artifact,
    classify,
    collect_result_artifacts,
)


def test_classify_by_extension(tmp_path):
    assert classify(tmp_path / "fig.png")[0] == "image"
    assert classify(tmp_path / "table.csv")[0] == "table"
    assert classify(tmp_path / "report.html")[0] == "html"
    assert classify(tmp_path / "paper.pdf")[0] == "pdf"
    assert classify(tmp_path / "data.json")[0] == "json"
    assert classify(tmp_path / "cells.h5ad")[0] == "anndata"
    assert classify(tmp_path / "archive.bin")[0] == "file"


def test_build_artifact_returns_none_for_missing(tmp_path):
    assert build_artifact(tmp_path / "nope.csv") is None


def test_build_artifact_for_existing_file(tmp_path):
    p = tmp_path / "out.csv"
    p.write_text("a,b\n1,2\n", encoding="utf-8")
    artifact = build_artifact(p)
    assert artifact is not None
    assert artifact["kind"] == "table"
    assert artifact["name"] == "out.csv"
    assert artifact["size"] == p.stat().st_size
    assert artifact["path"] == str(p)


def test_collect_result_artifacts_scopes_to_workspace_and_dedupes(tmp_path):
    inside = tmp_path / "plot.png"
    inside.write_bytes(b"\x89PNG\r\n\x1a\n")
    outside_file = tmp_path.parent / "external.csv"
    outside_file.write_text("x\n", encoding="utf-8")

    workspace = SimpleNamespace(workspace_dir=tmp_path)
    result = {
        "figure": str(inside),
        "figure_again": str(inside),  # duplicate path
        "external": str(outside_file),  # outside workspace
        "missing": str(tmp_path / "missing.csv"),
        "note": "not a path",
    }
    artifacts = collect_result_artifacts(workspace, result)
    assert len(artifacts) == 1
    assert artifacts[0]["kind"] == "image"
    assert artifacts[0]["name"] == "plot.png"


def test_collect_result_artifacts_handles_no_workspace():
    assert collect_result_artifacts(None, {"a": "/x"}) == []
