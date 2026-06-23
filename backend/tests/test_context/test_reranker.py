"""Tests for context rerankers."""

import pytest

from homomics_lab.context.reranker import BiEncoderReranker, CrossEncoderReranker


class _Candidate:
    def __init__(self, content: str, priority: int = 5):
        self.content = content
        self.priority = priority


@pytest.fixture
def candidates():
    return [
        _Candidate("RNA sequencing quality control"),
        _Candidate("protein mass spectrometry analysis"),
        _Candidate("RNA-seq differential expression"),
    ]


def test_cross_encoder_reranker_fallback_lexical(candidates):
    """When no model is loaded, the reranker falls back to lexical overlap."""
    reranker = CrossEncoderReranker(model_name="definitely-not-a-real-model")
    ordered = reranker.rerank(
        query="RNA-seq QC",
        candidates=candidates,
        text_fn=lambda c: c.content,
        top_k=2,
    )
    assert len(ordered) == 2
    # The two RNA-seq related candidates should outrank the proteomics one.
    texts = {c.content for c in ordered}
    assert "protein mass spectrometry analysis" not in texts


def test_bi_encoder_reranker_orders_by_similarity(candidates):
    reranker = BiEncoderReranker(model_name="all-MiniLM-L6-v2")
    ordered = reranker.rerank(
        query="RNA sequencing",
        candidates=candidates,
        text_fn=lambda c: c.content,
    )
    assert len(ordered) == 3
    # RNA-seq items should be top two.
    assert "RNA" in ordered[0].content or "RNA" in ordered[1].content


def test_shared_embedding_model_accepts_sentence_transformers_kwargs():
    """SharedEmbeddingModel is used as a sentence-transformers compatible drop-in."""
    from homomics_lab.context.embedding_cache import get_shared_embedding_model

    model = get_shared_embedding_model("sentence-transformers/all-MiniLM-L6-v2")
    embeddings = model.encode(["hello", "world"], convert_to_tensor=False)
    assert len(embeddings) == 2
    assert len(embeddings[0]) > 0
