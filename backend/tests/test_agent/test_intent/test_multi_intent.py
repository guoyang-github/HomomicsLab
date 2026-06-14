"""Tests for multi-intent detection."""

import pytest

from homomics_lab.agent.intent.analyzer import CascadeIntentAnalyzer
from homomics_lab.agent.intent.models import IntentDefinition


@pytest.fixture
def analyzer():
    from homomics_lab.agent.intent.classifiers import KeywordIntentClassifier
    return CascadeIntentAnalyzer(
        definitions=[
            IntentDefinition(
                analysis_type="single_cell_analysis",
                keywords=["单细胞"],
                examples=["分析单细胞数据", "做质控和聚类"],
                complexity_indicators=["流程"],
                domain="single_cell",
            ),
            IntentDefinition(
                analysis_type="qc",
                keywords=["质控", "qc"],
                examples=["做质控"],
                domain="single_cell",
            ),
            IntentDefinition(
                analysis_type="clustering",
                keywords=["聚类", "cluster"],
                examples=["做聚类"],
                domain="single_cell",
            ),
        ],
        use_domain_registry=False,
        keyword_classifier=KeywordIntentClassifier(weight=0.2),
        llm_classifier=None,
        high_confidence_threshold=2.0,
    )


@pytest.mark.asyncio
async def test_detects_sub_intents(analyzer):
    intent = await analyzer.analyze("先做单细胞质控，然后聚类")
    assert intent.analysis_type == "single_cell_analysis"
    sub_types = {sub.analysis_type for sub in intent.sub_intents}
    assert "qc" in sub_types
    assert "clustering" in sub_types


@pytest.mark.asyncio
async def test_complexity_from_sequential_markers(analyzer):
    intent = await analyzer.analyze("先质控再聚类")
    # With explicit sub-intents the request is treated as a workflow.
    assert intent.complexity == "complex"
    sub_types = {sub.analysis_type for sub in intent.sub_intents}
    assert "qc" in sub_types
