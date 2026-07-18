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


@pytest.mark.asyncio
async def test_tfidf_index_shared_across_instances():
    """Same definitions → the fitted TF-IDF index is reused process-wide."""
    unique_defs = [
        IntentDefinition(
            analysis_type="cache_probe_shared_index",
            keywords=["独一无二关键词"],
            examples=["独一无二的例子"],
            domain="cache-probe",
        ),
    ]
    c1 = EmbeddingIntentClassifier()
    await c1.classify("独一无二关键词", unique_defs, {})
    c2 = EmbeddingIntentClassifier()
    await c2.classify("独一无二的例子", unique_defs, {})

    assert c1._vectorizer is c2._vectorizer
    assert c1._embeddings is c2._embeddings


@pytest.mark.asyncio
async def test_tfidf_fit_runs_once_per_definitions_fingerprint(monkeypatch):
    """fit_transform runs only once while definitions are unchanged; a real
    definitions change forces a refit."""
    from sklearn.feature_extraction.text import TfidfVectorizer

    fit_calls = []
    original = TfidfVectorizer.fit_transform

    def counting_fit_transform(self, raw_documents, y=None):
        fit_calls.append(1)
        return original(self, raw_documents, y)

    monkeypatch.setattr(TfidfVectorizer, "fit_transform", counting_fit_transform)

    defs = [
        IntentDefinition(
            analysis_type="cache_probe_fit_once",
            keywords=["缓存探针"],
            examples=["缓存探针例子"],
            domain="cache-probe",
        ),
    ]
    # Two separate classifier instances (as produced per chat message).
    await EmbeddingIntentClassifier().classify("缓存探针", defs, {})
    await EmbeddingIntentClassifier().classify("缓存探针", defs, {})
    assert len(fit_calls) == 1

    changed_defs = [
        IntentDefinition(
            analysis_type="cache_probe_fit_once",
            keywords=["缓存探针改"],
            examples=["缓存探针例子"],
            domain="cache-probe",
        ),
    ]
    await EmbeddingIntentClassifier().classify("缓存探针改", changed_defs, {})
    assert len(fit_calls) == 2
