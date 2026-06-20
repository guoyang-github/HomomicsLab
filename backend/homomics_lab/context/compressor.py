"""Context compression for HomomicsLab Agent.

Intelligently compresses conversation context by:
1. Filtering irrelevant items via RelevanceFilter
2. Summarizing long items via ContextSummarizer
3. Removing redundant or outdated information
"""

from typing import List

from .relevance_filter import ContextItem, RelevanceFilter
from .summarizer import ContextSummarizer


class ContextCompressor:
    """Compress context to fit within token budget while preserving relevance."""

    def __init__(
        self,
        max_items: int = 20,
        max_chars_per_item: int = 2000,
        use_dense_embeddings: bool = False,
    ):
        self.max_items = max_items
        self.max_chars_per_item = max_chars_per_item
        self.filter = RelevanceFilter(use_dense_embeddings=use_dense_embeddings)
        self.summarizer = ContextSummarizer(max_length=max_chars_per_item)

    def compress(
        self,
        items: List[ContextItem],
        current_goal: str,
    ) -> List[ContextItem]:
        """Compress context items to fit within budget.

        Strategy:
        1. Filter items by relevance to current goal
        2. Summarize items that exceed length budget
        3. Remove redundant items (same type, similar content)
        """
        if not items:
            return []

        # Step 1: Filter by relevance
        filtered = self.filter.filter(items, budget=self.max_items, current_goal=current_goal)

        # Step 2: Summarize long items
        compressed = []
        for item in filtered:
            if len(item.content) > self.max_chars_per_item:
                summary = self.summarizer.summarize(item.content, summary_type=item.type)
                # Build concise summary text
                summary_parts = []
                if summary.key_conclusions:
                    summary_parts.append("Key points: " + "; ".join(summary.key_conclusions[:3]))
                if summary.key_parameters:
                    params_str = ", ".join(f"{k}={v}" for k, v in list(summary.key_parameters.items())[:5])
                    summary_parts.append(f"Parameters: {params_str}")
                if summary.warnings:
                    summary_parts.append("⚠ " + "; ".join(summary.warnings[:2]))

                compressed_content = " | ".join(summary_parts) if summary_parts else item.content[:self.max_chars_per_item]

                compressed.append(ContextItem(
                    content=compressed_content,
                    type=item.type,
                    is_pinned=item.is_pinned,
                    is_upstream_result=item.is_upstream_result,
                    agent_importance=item.agent_importance,
                    hours_since_created=item.hours_since_created,
                ))
            else:
                compressed.append(item)

        # Step 3: Deduplicate similar items
        deduped = self._deduplicate(compressed)

        return deduped

    def _deduplicate(self, items: List[ContextItem]) -> List[ContextItem]:
        """Remove redundant items with similar content."""
        if len(items) <= 1:
            return items

        result = [items[0]]
        for item in items[1:]:
            is_duplicate = False
            for existing in result:
                if item.type == existing.type and self._similarity(item.content, existing.content) > 0.8:
                    is_duplicate = True
                    break
            if not is_duplicate:
                result.append(item)
        return result

    @staticmethod
    def _similarity(a: str, b: str) -> float:
        """Simple Jaccard similarity between two strings."""
        if not a or not b:
            return 0.0
        set_a = set(a.lower().split())
        set_b = set(b.lower().split())
        if not set_a or not set_b:
            return 0.0
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        return intersection / union if union > 0 else 0.0
