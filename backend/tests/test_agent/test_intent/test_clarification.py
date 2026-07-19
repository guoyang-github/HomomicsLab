"""Tests for active clarification behavior."""

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
                examples=[],
                domain="single-cell-transcriptomics",
            ),
            IntentDefinition(
                analysis_type="spatial_analysis",
                keywords=["空间"],
                examples=[],
                domain="spatial-transcriptomics",
            ),
        ],
        use_domain_registry=False,
        keyword_classifier=KeywordIntentClassifier(weight=0.05),
        llm_classifier=None,
        clarification_threshold=0.7,
        high_confidence_threshold=2.0,
    )


@pytest.mark.asyncio
async def test_low_confidence_returns_clarification(analyzer):
    # Both "single_cell" and "spatial" keywords are present but weakly.
    intent = await analyzer.analyze("做单细胞或空间分析")
    assert intent.interaction_mode == "clarify"
    assert "clarification_question" in intent.metadata
    assert intent.confidence == 0.0


@pytest.mark.asyncio
async def test_clarification_includes_alternatives(analyzer):
    intent = await analyzer.analyze("做单细胞或空间分析")
    alternatives = intent.metadata.get("alternatives", [])
    assert len(alternatives) > 0
