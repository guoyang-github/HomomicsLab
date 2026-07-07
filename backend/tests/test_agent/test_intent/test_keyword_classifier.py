"""Tests for the keyword intent classifier."""

import pytest

from homomics_lab.agent.intent.classifiers import KeywordIntentClassifier
from homomics_lab.agent.intent.models import IntentDefinition


@pytest.fixture
def definitions():
    return [
        IntentDefinition(
            analysis_type="single_cell_analysis",
            keywords=["单细胞", "single cell", "scRNA", "10x", "scanpy"],
            complexity_indicators=["分析", "流程", "pipeline"],
            domain="single-cell-transcriptomics",
        ),
        IntentDefinition(
            analysis_type="file_conversion",
            keywords=["转换", "convert", "格式", "format"],
            domain="general",
        ),
    ]


@pytest.mark.asyncio
async def test_keyword_match_single_cell(definitions):
    classifier = KeywordIntentClassifier()
    matches = await classifier.classify("帮我分析单细胞数据", definitions, {})
    assert matches
    assert matches[0].analysis_type == "single_cell_analysis"
    assert matches[0].source == "keyword"


@pytest.mark.asyncio
async def test_keyword_match_file_conversion(definitions):
    classifier = KeywordIntentClassifier()
    matches = await classifier.classify("把文件转成 h5ad 格式", definitions, {})
    assert any(m.analysis_type == "file_conversion" for m in matches)


@pytest.mark.asyncio
async def test_qa_keyword_priority(definitions):
    """QA keywords should be detected even without domain keywords."""
    classifier = KeywordIntentClassifier()
    matches = await classifier.classify("什么是 UMAP？", definitions, {})
    assert matches[0].analysis_type == "qa"


@pytest.mark.asyncio
async def test_general_help_overrides_qa(definitions):
    """'generate code' should push toward general_help rather than qa."""
    classifier = KeywordIntentClassifier()
    matches = await classifier.classify("generate code to explain clustering", definitions, {})
    types = [m.analysis_type for m in matches]
    assert "general_help" in types
