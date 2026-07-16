import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import math

_CJK_RE = re.compile(r'[一-鿿぀-ゟ゠-ヿ가-힯]')


@dataclass
class ContextItem:
    content: str
    type: str  # chat, result, parameter, error
    is_pinned: bool = False
    is_upstream_result: bool = False
    agent_importance: float = 0.5  # 0-1
    hours_since_created: float = 0.0

    # Optional precomputed embedding
    embedding: Optional[List[float]] = field(default=None, repr=False)


class RelevanceFilter:
    """Filter context items based on relevance to current goal."""

    def __init__(self, use_dense_embeddings: bool = False):
        self.use_dense_embeddings = use_dense_embeddings
        self._embedding_model = None

    def _get_embedding_model(self):
        if self._embedding_model is None and self.use_dense_embeddings:
            try:
                from sentence_transformers import SentenceTransformer

                try:
                    self._embedding_model = SentenceTransformer(
                        "all-MiniLM-L6-v2", local_files_only=True
                    )
                except Exception:
                    self._embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
            except ImportError:
                self.use_dense_embeddings = False
        return self._embedding_model

    def score(self, item: ContextItem, current_goal: str) -> float:
        scores = {
            'semantic_similarity': self._semantic_similarity(item, current_goal),
            'temporal_proximity': self._temporal_decay(item.hours_since_created),
            'user_pin': 1.0 if item.is_pinned else 0.0,
            'result_dependency': 1.0 if item.is_upstream_result else 0.3,
            'agent_importance': item.agent_importance,
        }

        weights = {
            'semantic_similarity': 0.34,
            'temporal_proximity': 0.15,
            'user_pin': 0.26,
            'result_dependency': 0.15,
            'agent_importance': 0.10,
        }

        return sum(scores[k] * weights[k] for k in scores)

    def score_all(self, items: List[ContextItem], current_goal: str) -> List[Tuple[ContextItem, float]]:
        return [(item, self.score(item, current_goal)) for item in items]

    def filter(self, items: List[ContextItem], budget: int, current_goal: str) -> List[ContextItem]:
        """Return top-k items within budget, keeping pinned items."""
        pinned = [item for item in items if item.is_pinned]
        unpinned = [item for item in items if not item.is_pinned]

        scored = self.score_all(unpinned, current_goal)
        scored.sort(key=lambda x: x[1], reverse=True)

        budget_for_unpinned = max(0, budget - len(pinned))
        selected_unpinned = [item for item, _ in scored[:budget_for_unpinned]]

        return pinned + selected_unpinned

    def _semantic_similarity(self, item: ContextItem, goal: str) -> float:
        if not item.content or not goal:
            return 0.0

        # Use dense embeddings if available
        if self.use_dense_embeddings:
            model = self._get_embedding_model()
            if model is not None:
                import numpy as np
                embeddings = model.encode([item.content, goal], convert_to_tensor=False)
                a = embeddings[0] / np.linalg.norm(embeddings[0])
                b = embeddings[1] / np.linalg.norm(embeddings[1])
                return float(np.dot(a, b))

        # Fallback to lexical overlap
        has_cjk = bool(_CJK_RE.search(item.content) or _CJK_RE.search(goal))

        if has_cjk:
            # Character-level overlap for CJK text
            content_chars = set(item.content)
            goal_chars = set(goal)
        else:
            # Word-level overlap for English/other
            content_chars = set(item.content.lower().split())
            goal_chars = set(goal.lower().split())

        if not content_chars or not goal_chars:
            return 0.0

        overlap = len(content_chars & goal_chars)
        return overlap / max(len(content_chars | goal_chars), 1)

    def _temporal_decay(self, hours: float) -> float:
        return math.exp(-hours / 24.0)  # Decay over 24 hours
