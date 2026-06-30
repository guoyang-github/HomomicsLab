"""OpenAI-compatible embedding provider."""

import logging
from typing import List, Optional

import httpx

from homomics_lab.embeddings.base import EmbeddingProvider

logger = logging.getLogger(__name__)


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """Embedding provider using an OpenAI-compatible API."""

    def __init__(
        self,
        model: str,
        api_key: str,
        base_url: Optional[str] = None,
        dimensions: Optional[int] = None,
    ) -> None:
        self.model = model
        self.api_key = api_key
        self.base_url = base_url or "https://api.openai.com/v1"
        self._dimensions = dimensions

    @property
    def dimension(self) -> int:
        if self._dimensions is not None:
            return self._dimensions
        # text-embedding-3-small
        if "3-small" in self.model:
            return 1536
        if "3-large" in self.model:
            return 3072
        if "ada-002" in self.model:
            return 1536
        return 1536

    def encode(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        # Use synchronous httpx for a uniform sync interface.
        with httpx.Client(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=60.0,
        ) as client:
            response = client.post(
                "/embeddings",
                json={
                    "input": texts,
                    "model": self.model,
                    "encoding_format": "float",
                },
            )
            response.raise_for_status()
            data = response.json()["data"]
            data.sort(key=lambda x: x["index"])
            return [item["embedding"] for item in data]
