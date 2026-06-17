"""Tests for the intent benchmark CLI."""

import asyncio
import json
from pathlib import Path

import pytest

from homomics_lab.cli.commands.benchmark import _evaluate_intent


@pytest.fixture
def sample_dataset(tmp_path: Path):
    data = [
        {"message": "什么是 UMAP？", "expected_analysis_type": "qa"},
        {"message": "帮我分析这组单细胞数据", "expected_analysis_type": "single_cell_analysis"},
        {"message": "把文件转换成 h5ad 格式", "expected_analysis_type": "file_conversion"},
        {"message": "generate code to rename sample files", "expected_analysis_type": "general_help"},
    ]
    path = tmp_path / "intent_benchmark.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


@pytest.mark.asyncio
async def test_intent_benchmark_accuracy(sample_dataset: Path):
    result = await _evaluate_intent(
        dataset_path=sample_dataset,
        field="analysis_type",
        top_k=1,
        use_domain_registry=False,
    )
    assert result["total"] == 4
    assert result["correct"] == 4
    assert result["accuracy"] == 1.0
    assert "qa" in result["per_class"]
    assert result["confusion_matrix"]["qa"]["qa"] == 1


@pytest.mark.asyncio
async def test_intent_benchmark_top_k(sample_dataset: Path):
    # The first example is unambiguous; top-1 is sufficient.
    result = await _evaluate_intent(
        dataset_path=sample_dataset,
        field="analysis_type",
        top_k=3,
        use_domain_registry=False,
    )
    assert result["accuracy"] == 1.0
    assert result["top_k"] == 3


def test_intent_benchmark_cli_missing_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        asyncio.run(
            _evaluate_intent(
                dataset_path=tmp_path / "missing.json",
                field="analysis_type",
                top_k=1,
                use_domain_registry=False,
            )
        )
