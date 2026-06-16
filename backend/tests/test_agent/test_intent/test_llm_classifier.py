"""Tests for the LLM intent classifier."""

import json

import pytest

from homomics_lab.agent.intent.classifiers import LLMIntentClassifier
from homomics_lab.agent.intent.models import IntentDefinition
from homomics_lab.config import settings
from homomics_lab.llm_client import FakeLLMClient
from homomics_lab.secrets import reset_secrets_manager


@pytest.fixture(autouse=True)
def isolate_llm_config(tmp_path, monkeypatch):
    """Ensure LLMClient is not accidentally configured from persistent secrets."""
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(settings, "secrets_master_key", None)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    reset_secrets_manager()
    yield
    reset_secrets_manager()


@pytest.fixture
def definitions():
    return [
        IntentDefinition(
            analysis_type="single_cell_analysis",
            keywords=["单细胞"],
            examples=["帮我分析单细胞数据"],
            domain="single_cell",
        ),
        IntentDefinition(
            analysis_type="general_help",
            keywords=["代码", "code"],
            examples=["帮我写个 Python 脚本"],
            domain="builtin",
        ),
    ]


@pytest.fixture
def fake_llm_response():
    return json.dumps({
        "primary_intent": {
            "analysis_type": "single_cell_analysis",
            "confidence": 0.9,
            "reason": "User asks for single-cell analysis",
        },
        "alternative_intents": [],
        "sub_intents": [],
        "needs_clarification": False,
    })


@pytest.mark.asyncio
async def test_llm_classifier_parses_json(definitions, fake_llm_response):
    client = FakeLLMClient(response=fake_llm_response)
    classifier = LLMIntentClassifier(llm_client=client)
    matches = await classifier.classify("analyze single cell data", definitions, {})

    assert len(matches) == 1
    assert matches[0].analysis_type == "single_cell_analysis"
    assert matches[0].source == "llm"


@pytest.mark.asyncio
async def test_llm_classifier_unavailable(definitions):
    """When LLM is not configured, classifier returns empty list."""
    classifier = LLMIntentClassifier()  # no client -> uses LLMClient() which is unconfigured
    assert not classifier.is_available()
    matches = await classifier.classify("analyze data", definitions, {})
    assert matches == []
