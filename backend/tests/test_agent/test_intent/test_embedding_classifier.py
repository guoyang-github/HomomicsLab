"""Tests for the embedding intent classifier."""

import pytest

from homomics_lab.agent.intent.classifiers import EmbeddingIntentClassifier
from homomics_lab.agent.intent.models import IntentDefinition


@pytest.fixture
def definitions():
    return [
        IntentDefinition(
            analysis_type="single_cell_analysis",
            keywords=["单细胞", "single cell"],
            examples=["帮我分析这组单细胞数据", "run scRNA-seq QC and clustering"],
            domain="single-cell-transcriptomics",
        ),
        IntentDefinition(
            analysis_type="spatial_analysis",
            keywords=["空间", "spatial"],
            examples=["分析空间转录组数据", "run spatial transcriptomics analysis"],
            domain="spatial-transcriptomics",
        ),
    ]


@pytest.mark.asyncio
async def test_embedding_semantic_match(definitions):
    classifier = EmbeddingIntentClassifier()
    matches = await classifier.classify("帮我做单细胞测序分析", definitions, {})
    assert matches
    assert matches[0].analysis_type == "single_cell_analysis"


@pytest.mark.asyncio
async def test_embedding_distinguishes_domains(definitions):
    classifier = EmbeddingIntentClassifier()
    matches = await classifier.classify("分析 visium 空间数据", definitions, {})
    assert matches
    assert matches[0].analysis_type == "spatial_analysis"


@pytest.mark.asyncio
async def test_embedding_no_match(definitions):
    classifier = EmbeddingIntentClassifier()
    matches = await classifier.classify("今天天气怎么样", definitions, {})
    assert not matches
