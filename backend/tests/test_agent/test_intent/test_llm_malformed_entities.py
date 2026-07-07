"""Regression tests for LLM intent classifier returning malformed entities."""

import json

import pytest

from homomics_lab.agent.intent.analyzer import CascadeIntentAnalyzer
from homomics_lab.agent.intent.classifiers import LLMIntentClassifier
from homomics_lab.agent.intent.models import IntentDefinition


class _FakeLLMClient:
    """Returns a structured intent with the requested malformed entities field."""

    def __init__(self, entities):
        self._entities = entities

    def is_configured(self):
        return True

    async def chat_completion(self, *args, **kwargs):
        return json.dumps(
            {
                "primary_intent": {
                    "intent_type": "analysis",
                    "interaction_mode": "execute",
                    "domain": "single-cell-transcriptomics",
                    "target": "single_cell_analysis",
                    "scope": "full",
                    "entities": self._entities,
                    "confidence": 0.95,
                    "reason": "test",
                },
                "alternative_intents": [],
                "sub_intents": [],
                "needs_clarification": False,
            }
        )


@pytest.fixture
def analyzer():
    definitions = [
        IntentDefinition(
            analysis_type="single_cell_analysis",
            keywords=["单细胞"],
            examples=["分析单细胞数据"],
            domain="single-cell-transcriptomics",
        ),
    ]
    return CascadeIntentAnalyzer(
        definitions=definitions,
        use_domain_registry=False,
        llm_classifier=None,
        keyword_classifier=None,
        embedding_classifier=None,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("entities", ["resolution", ["resolution", "louvain"], [["key"]]])
async def test_malformed_entities_do_not_crash_intent_analysis(analyzer, entities):
    """Entities returned as string/list/list-of-tuples must be coerced safely."""
    llm_classifier = LLMIntentClassifier()
    llm_classifier._client = _FakeLLMClient(entities)
    analyzer.llm_classifier = llm_classifier

    intent = await analyzer.analyze("对 PA12 单细胞数据执行 Louvain 聚类")

    assert intent.analysis_type == "single_cell_analysis"
    assert isinstance(intent.metadata, dict)
    # The malformed payload should be preserved under _raw for observability.
    assert "_raw" in intent.structured_intent.entities
