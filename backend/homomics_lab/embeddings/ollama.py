"""Ollama embedding provider."""

import logging
from typing import List, Optional

import httpx

from homomics_lab.embeddings.base import EmbeddingProvider

logger = logging.getLogger(__name__)


class OllamaEmbeddingProvider(EmbeddingProvider):
    """Embedding provider using a local or remote Ollama server."""

    def __init__(
        self,
        model: str,
        base_url: Optional[str] = None,
        dimensions: Optional[int] = None,
    ) -> None:
        self.model = model
        self.base_url = (base_url or "http://localhost:11434").rstrip("/")
        self._dimensions = dimensions

    @property
    def dimension(self) -> int:
        if self._dimensions is not None:
            return self._dimensions
        # Common Ollama embedding model dimensions.
        if "nomic-embed" in self.model.lower():
            return 768
        if "mxbai-embed" in self.model.lower():
            return 1024
        if "snowflake" in self.model.lower():
            return 1024
        return 768

    def encode(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        with httpx.Client(base_url=self.base_url, timeout=60.0) as client:
            embeddings: List[List[float]] = []
            # Ollama /embeddings endpoint accepts one text per request.
            for text in texts:
                response = client.post(
                    "/api/embeddings",
                    json={"model": self.model, "prompt": text},
                )
                response.raise_for_status()
                embeddings.append(response.json()["embedding"])
            return embeddings
