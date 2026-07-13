"""Tests for data-driven result summarization.

The fixture mirrors the CellTypist skill outputs (labels / per-reference /
confusion / report) using the magnitudes reported for PA12_sc.h5ad, but every
assertion is checked against the fixture's own contents — never against a
memorized number — so the test proves the summarizer *computes* correctly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from homomics_lab.artifacts import build_artifact
from homomics_lab.result_summary import summarize_artifacts, user_requested_comparison


# Top cell types (label, count, mean_confidence) used to build the labels CSV.
_TOP_TYPES = [
    ("Tem/Temra cytotoxic T cells", 4456, 0.863),
    ("CD16+ NK cells", 3016, 0.920),
    ("Tcm/Naive helper T cells", 2191, 0.743),
    ("Tem/Trm cytotoxic T cells", 1859, 0.714),
    ("Naive B cells", 815, 0.968),
    ("Memory B cells", 644, 0.945),
    ("Regulatory T cells", 471, 0.777),
    ("Type 1 helper T cells", 241, 0.537),
    ("Epithelial cells", 212, 0.881),
    ("Endothelial cells", 161, 1.000),
    ("Classical monocytes", 180, 0.731),
    ("Fibroblasts", 92, 0.700),
    ("Macrophages", 80, 0.669),
    ("Megakaryocytes/platelets", 37, 0.917),
    ("Unassigned", 535, 0.200),
]

_PER_REFERENCE = [
    ("Endothelial", "Endothelial cells", 0.982, 164),
    ("Plasma", "Memory B cells", 0.938, 16),
    ("Ductal", "Epithelial cells", 0.925, 228),
    ("Stellate", "Fibroblasts", 0.895, 76),
    ("NK", "CD16+ NK cells", 0.877, 3166),
    ("B", "Naive B cells", 0.564, 1445),
    ("CD8T", "Tem/Temra cytotoxic T cells", 0.553, 5683),
    ("CD4T", "Tcm/Naive helper T cells", 0.483, 3639),
    ("Myeloid", "Classical monocytes", 0.391, 445),
]


def _write_labels(path: Path) -> int:
    lines = ["barcode,predicted_labels,conf_score"]
    n = 0
    for label, count, conf in _TOP_TYPES:
        for i in range(count):
            lines.append(f"cell{n:06d},{label},{conf:.3f}")
            n += 1
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return n


def _write_per_reference(path: Path) -> None:
    lines = ["reference,best_match,recall,count"]
    for ref, match, recall, cnt in _PER_REFERENCE:
        lines.append(f"{ref},{match},{recall:.3f},{cnt}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_report(path: Path) -> None:
    path.write_text(
        "输入数据: 14,990 细胞 × 29,057 基因\n"
        "使用模型: Immune_All_Low.pkl\n"
        "基因重叠: 6,023 / 6,639\n"
        "ARI（全部）: 0.415\n"
        "NMI（全部）: 0.589\n",
        encoding="utf-8",
    )


@pytest.fixture()
def celltypist_dir(tmp_path: Path) -> Path:
    _write_labels(tmp_path / "PA12_sc_celltypist_labels.csv")
    _write_per_reference(tmp_path / "PA12_sc_celltypist_per_reference.csv")
    _write_report(tmp_path / "PA12_sc_celltypist_report.txt")
    (tmp_path / "figures").mkdir()
    (tmp_path / "figures" / "summary.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    return tmp_path


def _envelopes(directory: Path):
    arts = []
    for p in directory.rglob("*"):
        env = build_artifact(p)
        if env is not None:
            arts.append(env)
    return arts


def test_metrics_are_computed_from_files(celltypist_dir: Path) -> None:
    summary = summarize_artifacts(
        _envelopes(celltypist_dir),
        skill_id="bio-single-cell-annotation-celltypist",
        user_message="使用 CellTypist 注释，并比较与 all_celltype 的一致性",
    )
    expected_n = sum(c for _, c, _ in _TOP_TYPES)
    assert summary.metrics["细胞数"] == f"{expected_n:,}"
    assert summary.metrics["识别细胞类型"] == f"{len(_TOP_TYPES)} 种"
    assert summary.metrics["ARI"] == "0.415"
    assert summary.metrics["NMI"] == "0.589"
    assert summary.metrics["基因重叠"].startswith("6,023 / 6,639")
    assert "平均置信度" in summary.metrics


def test_top_types_table_is_sorted_and_correct(celltypist_dir: Path) -> None:
    summary = summarize_artifacts(_envelopes(celltypist_dir))
    table = next(t for t in summary.tables if "主要细胞类型" in t.title)
    assert table.headers == ["预测标签", "细胞数", "占比", "平均置信度"]
    first = table.rows[0]
    assert first[0] == "Tem/Temra cytotoxic T cells"
    assert first[1] == "4,456"
    # mean confidence for the top type equals the fixture value
    assert first[3] == "0.863"


def test_comparison_block_present_when_requested(celltypist_dir: Path) -> None:
    summary = summarize_artifacts(
        _envelopes(celltypist_dir),
        user_message="比较注释结果与 all_celltype 的一致性",
    )
    assert summary.comparison is not None
    comp_table = next(t for t in summary.tables if "all_celltype" in t.title)
    assert comp_table.rows[0][0] == "Endothelial"
    assert comp_table.rows[0][2] == "98.2%"
    # high vs low recall findings are generated from the data
    finding_text = " ".join(f.text for f in summary.findings)
    assert "≥80%" in finding_text
    assert "<50%" in finding_text


def test_findings_reference_sources(celltypist_dir: Path) -> None:
    summary = summarize_artifacts(_envelopes(celltypist_dir))
    assert summary.findings, "expected at least one finding"
    assert any(f.sources for f in summary.findings)
    md = summary.to_markdown()
    assert "关键指标" in md and "关键发现" in md


def test_comparison_detection_helper() -> None:
    assert user_requested_comparison("比较与 all_celltype 的一致性")
    assert user_requested_comparison("check agreement with reference")
    assert not user_requested_comparison("对 PA12 做细胞注释")


def test_confusion_matrix_fallback(tmp_path: Path) -> None:
    # No per_reference.csv: derive best-match/recall from the confusion matrix.
    confusion = tmp_path / "PA12_sc_celltypist_confusion.csv"
    confusion.write_text(
        "reference,Endothelial cells,Fibroblasts,Naive B cells\n"
        "Endothelial,160,3,1\n"
        "B,5,2,80\n",
        encoding="utf-8",
    )
    summary = summarize_artifacts([build_artifact(confusion)])
    assert summary.comparison is not None
    rows = summary.comparison["rows"]
    # Endothelial row recall = 160/164 ≈ 97.6%, best match Endothelial cells
    endo = next(r for r in rows if r[0] == "Endothelial")
    assert endo[1] == "Endothelial cells"
    assert endo[2] == "97.6%"


def test_interpretation_and_next_steps(celltypist_dir: Path) -> None:
    summary = summarize_artifacts(
        _envelopes(celltypist_dir),
        skill_id="bio-single-cell-annotation-celltypist",
        user_message="注释并比较与 all_celltype 的一致性",
    )
    assert summary.interpretation, "expected data-driven interpretation"
    assert summary.next_steps, "expected next-step suggestions"
    md = summary.to_markdown()
    assert "**解读**" in md
    assert "**下一步建议**" in md
    # immune-extention line should fire (Endothelial/Ductal/etc. mapped correctly)
    joined = " ".join(f.text for f in summary.interpretation)
    assert "基质" in joined or "细粒度" in joined
    # low-recall labels drive the mapping suggestion
    steps = " ".join(f.text for f in summary.next_steps)
    assert "粗粒度" in steps or "映射" in steps
    # every suggestion is sourced
    assert all(f.sources for f in summary.next_steps)


def test_generic_csv_fallback(tmp_path: Path) -> None:
    generic = tmp_path / "result.csv"
    generic.write_text("a,b\n1,2\n3,4\n", encoding="utf-8")
    summary = summarize_artifacts([build_artifact(generic)])
    assert summary.tables, "generic CSV should still produce a preview table"
    assert summary.tables[0].headers == ["a", "b"]


def test_missing_files_do_not_raise(tmp_path: Path) -> None:
    ghost = tmp_path / "nope_labels.csv"
    summary = summarize_artifacts([{"kind": "table", "path": str(ghost)}])
    assert summary.tables == []
    assert summary.findings == []


def _write_annotated_h5ad(path: Path) -> None:
    """Build a tiny AnnData whose obs carries reference + CellTypist labels."""
    anndata = pytest.importorskip("anndata")
    np = pytest.importorskip("numpy")

    ref: list[str] = []
    pred: list[str] = []
    ref += ["CD8T"] * 40
    pred += ["Tem/Temra cytotoxic T cells"] * 35 + ["CD16+ NK cells"] * 5
    ref += ["NK"] * 30
    pred += ["CD16+ NK cells"] * 28 + ["Tem/Trm cytotoxic T cells"] * 2
    ref += ["B"] * 20
    pred += ["Naive B cells"] * 18 + ["Memory B cells"] * 2

    n = len(ref)
    adata = anndata.AnnData(np.zeros((n, 1)))
    adata.obs["all_celltype"] = ref
    adata.obs["celltypist_label"] = pred
    adata.obs["celltypist_conf_score"] = [0.9] * n
    adata.write_h5ad(path)


def test_comparison_from_annotated_h5ad(tmp_path: Path) -> None:
    # No per_reference.csv / confusion.csv: the summarizer must derive the
    # agreement table + ARI/NMI straight from the annotated AnnData.
    h5ad = tmp_path / "sample_celltypist_annotated.h5ad"
    _write_annotated_h5ad(h5ad)

    summary = summarize_artifacts(
        [build_artifact(h5ad)],
        skill_id="bio-single-cell-annotation-celltypist",
        user_message="使用 CellTypist 注释，并比较与 all_celltype 的一致性",
    )

    assert summary.comparison is not None
    rows = summary.comparison["rows"]
    # Sorted by recall desc after coarse mapping: B 100% > NK 93.3% > CD8T 87.5%
    assert rows[0][0] == "B"
    assert rows[0][1] == "B"
    assert rows[0][2] == "100.0%"
    nk = next(r for r in rows if r[0] == "NK")
    assert nk[1] == "NK"
    assert nk[2] == "93.3%"
    cd8 = next(r for r in rows if r[0] == "CD8T")
    assert cd8[1] == "CD8T"
    assert cd8[2] == "87.5%"
    # Overall clustering agreement is computed when sklearn is available.
    sklearn = pytest.importorskip("sklearn")
    _ = sklearn
    assert isinstance(summary.comparison["ari"], float)
    assert isinstance(summary.comparison["nmi"], float)
    # ARI/NMI flow into headline metrics and the rendered markdown.
    assert "ARI" in summary.metrics and "NMI" in summary.metrics
    md = summary.to_markdown()
    assert "与 all_celltype 的一致性比较" in md
    assert "ARI" in md
    # Findings cite the h5ad they were derived from, not an unrelated file.
    comp_findings = [f for f in summary.findings if "召回率" in f.text or "ARI" in f.text]
    assert comp_findings
    assert all(any(s.endswith(".h5ad") for s in f.sources) for f in comp_findings)


def test_h5ad_comparison_skipped_without_request(tmp_path: Path) -> None:
    h5ad = tmp_path / "sample_celltypist_annotated.h5ad"
    _write_annotated_h5ad(h5ad)
    summary = summarize_artifacts([build_artifact(h5ad)])
    # User did not ask for an agreement check -> no comparison block.
    assert summary.comparison is None


def test_comparison_report_parsing(tmp_path: Path) -> None:
    """Agent-generated comparison_report.txt drives the comparison table."""
    comp_report = tmp_path / "comparison_report.txt"
    comp_report.write_text(
        """CellTypist vs all_celltype comparison (PA12_sc.h5ad)
====================================================
Model: Immune_All_Low.pkl (majority voting, best match)
Total cells: 14990

Per-reference-label summary:
  CD8T         n=5683  recall=0.873  top_pred=Tem/Temra cytotoxic T cells
  CD4T         n=3639  recall=0.653  top_pred=Tcm/Naive helper T cells
  Endothelial  n=164   recall=0.970  top_pred=Endothelial cells
  Ductal       n=228   recall=0.974  top_pred=Epithelial cells
  Stellate     n=76    recall=0.000  top_pred=Fibroblasts
""",
        encoding="utf-8",
    )
    summary = summarize_artifacts(
        [build_artifact(comp_report)],
        user_message="比较注释结果与 all_celltype 的一致性",
    )
    assert summary.comparison is not None
    rows = summary.comparison["rows"]
    # Non-immune classes are preserved.
    endothelial = next(r for r in rows if r[0] == "Endothelial")
    assert endothelial[1] == "Endothelial cells"
    assert endothelial[2] == "97.0%"
    ductal = next(r for r in rows if r[0] == "Ductal")
    assert ductal[1] == "Epithelial cells"
    md = summary.to_markdown()
    assert "与 all_celltype 的一致性比较" in md
    assert "Endothelial cells" in md


def test_cell_level_comparison_csv(tmp_path: Path) -> None:
    """A cell-level comparison CSV yields per-reference best match + ARI/NMI."""
    cell_csv = tmp_path / "celltypist_comparison.csv"
    cell_csv.write_text(
        "barcode,all_celltype,celltypist_predicted,celltypist_conf_score,celltypist_label_filtered\n"
        "c1,CD8T,Tem/Temra cytotoxic T cells,0.95,Tem/Temra cytotoxic T cells\n"
        "c2,CD8T,CD16+ NK cells,0.91,CD16+ NK cells\n"
        "c3,NK,CD16+ NK cells,0.99,CD16+ NK cells\n"
        "c4,NK,Tem/Trm cytotoxic T cells,0.88,Tem/Trm cytotoxic T cells\n"
        "c5,B,Naive B cells,0.97,Naive B cells\n"
        "c6,Endothelial,Endothelial cells,0.98,Endothelial cells\n"
        "c7,Endothelial,Fibroblasts,0.45,Unassigned\n",
        encoding="utf-8",
    )
    summary = summarize_artifacts(
        [build_artifact(cell_csv)],
        user_message="比较注释结果与 all_celltype 的一致性",
    )
    assert summary.comparison is not None
    rows = summary.comparison["rows"]
    endothelial = next(r for r in rows if r[0] == "Endothelial")
    assert endothelial[1] == "Endothelial cells"
    assert endothelial[2] == "50.0%"
    # Unassigned rate comes from the filtered column.
    assert summary.metrics["Unassigned 占比"] == "14.3%"
    # ARI/NMI are computed when sklearn is present.
    sklearn = pytest.importorskip("sklearn")
    _ = sklearn
    assert isinstance(summary.comparison["ari"], float)
