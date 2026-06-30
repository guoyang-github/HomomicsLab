"""Tests for embedding providers."""

from homomics_lab.embeddings.factory import get_embedding_provider, reset_embedding_provider
from homomics_lab.embeddings.sentence_transformers import SentenceTransformersProvider


CACHED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def test_sentence_transformers_encode():
    provider = SentenceTransformersProvider(model_name=CACHED_MODEL)
    embeddings = provider.encode(["hello world", "bioinformatics"])
    assert len(embeddings) == 2
    assert len(embeddings[0]) == provider.dimension
    # Vectors should be normalized.
    import math

    assert math.isclose(math.sqrt(sum(x * x for x in embeddings[0])), 1.0, rel_tol=1e-5)


def test_factory_returns_provider(monkeypatch):
    from homomics_lab.config import settings

    reset_embedding_provider()
    monkeypatch.setattr(settings, "embedding_provider", "sentence_transformers")
    monkeypatch.setattr(settings, "embedding_model", CACHED_MODEL)
    provider = get_embedding_provider(settings)
    assert isinstance(provider, SentenceTransformersProvider)
    embeddings = provider.encode(["test"])
    assert len(embeddings) == 1
