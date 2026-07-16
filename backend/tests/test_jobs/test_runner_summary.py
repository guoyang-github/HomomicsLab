"""Queued-job chat message should carry a rich, sourced result summary.

The background runner updates the original "已提交后台执行" TODO message once a
job finishes. These tests pin that the update uses the deterministic
``result_summary`` markdown (inline tables/findings) and attaches artifact
envelopes, rather than the legacy one-line "分析已完成" text.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from homomics_lab.artifacts import build_artifact
from homomics_lab.jobs.constants import JobStatus
from homomics_lab.jobs.runner import BackgroundJobRunner


def _labels_csv(path: Path) -> None:
    lines = ["barcode,predicted_labels,conf_score"]
    n = 0
    for label, count, conf in [
        ("CD16+ NK cells", 30, 0.92),
        ("Tem/Temra cytotoxic T cells", 20, 0.86),
        ("Naive B cells", 10, 0.95),
    ]:
        for _ in range(count):
            lines.append(f"cell{n:04d},{label},{conf:.3f}")
            n += 1
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _per_reference_csv(path: Path) -> None:
    path.write_text(
        "reference,best_match,recall,count\n"
        "NK,CD16+ NK cells,0.930,30\n"
        "CD8T,Tem/Temra cytotoxic T cells,0.850,20\n"
        "B,Naive B cells,0.900,10\n",
        encoding="utf-8",
    )


def _tree(tmp_path: Path, user_request: str):
    labels = tmp_path / "sample_celltypist_labels.csv"
    per_ref = tmp_path / "sample_celltypist_per_reference.csv"
    _labels_csv(labels)
    _per_reference_csv(per_ref)
    arts = [build_artifact(labels), build_artifact(per_ref)]
    task_result = {"success": True, "artifacts": arts, "final_output": {}}
    task = SimpleNamespace(
        status="completed",
        result=task_result,
        parameters={"user_request": user_request},
        skills_required=["bio-single-cell-annotation-celltypist"],
    )
    tree = SimpleNamespace(tasks=[task])
    return task_result, tree


@pytest.mark.asyncio
async def test_compose_returns_rich_markdown_and_envelopes(tmp_path: Path) -> None:
    task_result, tree = _tree(tmp_path, "注释并比较与 all_celltype 的一致性")
    summary, envelopes = await BackgroundJobRunner._compose_result_message(
        task_result, tree, JobStatus.COMPLETED
    )
    text = summary.to_markdown()
    assert envelopes, "artifact envelopes should be attached for inline rendering"
    assert all({"kind", "mime", "name", "path", "size"} <= set(e) for e in envelopes)
    assert "关键指标" in text
    assert "主要细胞类型" in text
    # comparison request + per_reference.csv -> agreement table rendered
    assert "all_celltype" in text
    assert "NK" in text and "CD16+ NK cells" in text


@pytest.mark.asyncio
async def test_compose_falls_back_without_artifacts() -> None:
    summary, envelopes = await BackgroundJobRunner._compose_result_message(
        {"success": True}, None, JobStatus.COMPLETED
    )
    text = summary.to_markdown()
    assert envelopes == []
    # fallback never returns empty; the legacy one-liner is surfaced as the
    # single interpretation entry.
    assert "分析已完成" in text


@pytest.mark.asyncio
async def test_compose_failed_status_uses_legacy_summary(tmp_path: Path) -> None:
    task_result, tree = _tree(tmp_path, "比较 all_celltype")
    summary, envelopes = await BackgroundJobRunner._compose_result_message(
        task_result, tree, JobStatus.FAILED
    )
    text = summary.to_markdown()
    # envelopes are still harvested for inspection, but the text is the failure blurb
    assert envelopes
    assert "执行结束，结果概要如下。" in text


def test_derive_helpers(tmp_path: Path) -> None:
    _, tree = _tree(tmp_path, "比较 all_celltype")
    assert BackgroundJobRunner._derive_user_message(tree) == "比较 all_celltype"
    assert (
        BackgroundJobRunner._derive_skill_id(tree)
        == "bio-single-cell-annotation-celltypist"
    )
