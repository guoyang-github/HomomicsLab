"""Factory for creating embedding providers from settings."""

import logging
import time
from typing import Optional

from homomics_lab.config import Settings, settings as default_settings
from homomics_lab.embeddings.base import EmbeddingProvider
from homomics_lab.embeddings.ollama import OllamaEmbeddingProvider
from homomics_lab.embeddings.openai import OpenAIEmbeddingProvider
from homomics_lab.embeddings.sentence_transformers import SentenceTransformersProvider

logger = logging.getLogger(__name__)


_provider_instance: Optional[EmbeddingProvider] = None


def get_embedding_provider(settings: Optional[Settings] = None) -> EmbeddingProvider:
    """Return the configured embedding provider singleton."""
    global _provider_instance
    if _provider_instance is not None:
        return _provider_instance

    settings = settings or default_settings
    provider_name = (settings.embedding_provider or "sentence_transformers").lower()

    if provider_name in ("openai", "custom"):
        api_key = settings.embedding_api_key
        if not api_key:
            logger.warning(
                "embedding_provider=%s but embedding_api_key is not set", provider_name
            )
        _provider_instance = OpenAIEmbeddingProvider(
            model=settings.embedding_model or "text-embedding-3-small",
            api_key=api_key or "",
            base_url=settings.embedding_base_url,
        )
    elif provider_name == "ollama":
        _provider_instance = OllamaEmbeddingProvider(
            model=settings.embedding_model or "nomic-embed-text",
            base_url=settings.embedding_base_url,
        )
    else:
        _provider_instance = SentenceTransformersProvider(
            model_name=settings.embedding_model or None,
        )

    return _provider_instance


def warmup_embedding_provider(provider: Optional[EmbeddingProvider]) -> None:
    """Force local embedding models to load so first-request latency is avoided.

    API-backed providers are skipped to avoid unnecessary token/call costs.
    """
    if provider is None:
        return
    if isinstance(provider, SentenceTransformersProvider):
        start = time.perf_counter()
        try:
            provider.encode(["warmup"])
            logger.info(
                "Sentence-transformers embedding provider warmed up in %.2fs",
                time.perf_counter() - start,
            )
        except Exception:
            logger.exception("Failed to warm up sentence-transformers embedding provider")


def reset_embedding_provider() -> None:
    """Reset the singleton, primarily for tests."""
    global _provider_instance
    _provider_instance = None
