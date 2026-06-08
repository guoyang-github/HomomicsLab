from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import math


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
        """Simple keyword overlap similarity (replace with embedding in Phase 2).

        For CJK text (Chinese, Japanese, Korean) without word boundaries,
        falls back to character-level overlap.
        """
        if not item.content or not goal:
            return 0.0

        content_lower = item.content.lower()
        goal_lower = goal.lower()

        content_words = set(content_lower.split())
        goal_words = set(goal_lower.split())

        # Detect CJK text: if splitting by whitespace yields single tokens
        # that are long strings, use character-level overlap instead
        is_cjk_content = len(content_words) == 1 and len(next(iter(content_words))) > 3
        is_cjk_goal = len(goal_words) == 1 and len(next(iter(goal_words))) > 3

        if is_cjk_content or is_cjk_goal:
            content_chars = set(content_lower)
            goal_chars = set(goal_lower)
            if not content_chars or not goal_chars:
                return 0.0
            overlap = len(content_chars & goal_chars)
            return overlap / max(len(goal_chars), 1)

        if not content_words or not goal_words:
            return 0.0

        overlap = len(content_words & goal_words)
        return overlap / max(len(goal_words), 1)

    def _temporal_decay(self, hours: float) -> float:
        return math.exp(-hours / 24.0)  # Decay over 24 hours
