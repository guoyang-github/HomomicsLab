"""Local sentence-transformers embedding provider."""

import functools
import logging
from typing import List, Optional

import numpy as np

from homomics_lab.embeddings.base import EmbeddingProvider

logger = logging.getLogger(__name__)


class SentenceTransformersProvider(EmbeddingProvider):
    """Embedding provider backed by a local sentence-transformers model."""

    DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"

    def __init__(
        self,
        model_name: Optional[str] = None,
        device: Optional[str] = None,
        normalize: bool = True,
    ) -> None:
        self.model_name = model_name or self.DEFAULT_MODEL
        self.device = device or "cpu"
        self.normalize = normalize
        self._model: Optional[object] = None

    @property
    def dimension(self) -> int:
        model = self._load_model()
        return int(model.get_sentence_embedding_dimension())

    def is_available(self) -> bool:
        try:
            self._load_model()
            return True
        except Exception as exc:
            logger.warning("Sentence-transformers provider unavailable: %s", exc)
            return False

    @functools.lru_cache(maxsize=1)
    def _load_model(self):
        """Lazy-load the sentence-transformers model."""
        from sentence_transformers import SentenceTransformer

        if self._model is None:
            logger.info("Loading sentence-transformers model: %s", self.model_name)
            self._model = SentenceTransformer(self.model_name, device=self.device)
        return self._model

    def encode(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        model = self._load_model()
        embeddings = model.encode(
            texts,
            convert_to_tensor=False,
            show_progress_bar=False,
        )
        if self.normalize:
            embeddings = self._normalize(embeddings)
        return embeddings.tolist()

    @staticmethod
    def _normalize(embeddings: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return embeddings / norms
