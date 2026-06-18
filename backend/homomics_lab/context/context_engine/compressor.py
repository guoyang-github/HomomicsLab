"""Dynamic context compression for the ContextEngine.

Compresses a ranked list of ContextParts to fit within a token budget using a
gradient of strategies: truncate → structured extract → LLM summarize → drop.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from homomics_lab.context.context_engine.models import (
    CompressionLevel,
    ContextPart,
)
from homomics_lab.context.summarizer import ContextSummarizer
from homomics_lab.context.token_budget import TokenBudgetManager
from homomics_lab.llm_client import LLMClient

logger = logging.getLogger(__name__)


class DynamicContextCompressor:
    """Compress context parts to fit a token budget."""

    def __init__(
        self,
        budget_manager: TokenBudgetManager,
        llm_client: Optional[LLMClient] = None,
        enable_llm_summary: bool = True,
    ):
        self.budget_manager = budget_manager
        self.llm_client = llm_client
        self.enable_llm_summary = enable_llm_summary
        self.rule_summarizer = ContextSummarizer(max_length=400)

    def _get_llm(self) -> Optional[LLMClient]:
        if self.llm_client is None and self.enable_llm_summary:
            self.llm_client = LLMClient()
        return self.llm_client

    def compress(
        self,
        parts: List[ContextPart],
        budget: int,
    ) -> List[ContextPart]:
        """Compress parts until they fit within budget.

        Always keeps pinned/critical parts. Returns the surviving parts with
        compression_level set.
        """
        if not parts:
            return []

        # Compute initial tokens and mark uncompressed
        for part in parts:
            if part.tokens <= 0:
                part.tokens = self.budget_manager.count(part.content)
            part.compression_level = CompressionLevel.NONE

        reserved = [p for p in parts if p.is_pinned or p.is_critical]
        reserved_tokens = sum(p.tokens for p in reserved)
        flexible = [p for p in parts if not (p.is_pinned or p.is_critical)]

        if reserved_tokens > budget:
            logger.warning(
                "Reserved context exceeds budget (%d > %d); truncating reserved parts",
                reserved_tokens,
                budget,
            )
            reserved = self._truncate_parts(reserved, budget)
            return reserved

        remaining_budget = budget - reserved_tokens

        # Step 1: sort flexible by priority and try to fit as-is
        flexible.sort(key=lambda p: (-p.priority, p.tokens))
        kept: List[ContextPart] = []
        for part in flexible:
            if part.tokens <= remaining_budget:
                kept.append(part)
                remaining_budget -= part.tokens

        if not kept and remaining_budget > 0:
            # Budget too small even for the highest priority flexible part.
            # Summarize the single most important part if possible.
            if flexible:
                summarized = self._summarize_part(flexible[0], remaining_budget)
                if summarized.tokens <= remaining_budget:
                    kept.append(summarized)

        result = reserved + kept
        return self._ensure_budget(result, budget)

    def _ensure_budget(
        self,
        parts: List[ContextPart],
        budget: int,
    ) -> List[ContextPart]:
        """Final safety pass: if still over budget, truncate/drop until fit."""
        total = sum(p.tokens for p in parts)
        if total <= budget:
            return parts

        # Try truncating the longest non-critical non-pinned parts first
        parts.sort(key=lambda p: (-p.tokens, not p.is_critical, not p.is_pinned))
        for part in parts:
            if part.is_pinned or part.is_critical:
                continue
            over = total - budget
            if over <= 0:
                break
            new_max = max(20, part.tokens - over)
            part.content = self.budget_manager.truncate(part.content, new_max)
            part.tokens = self.budget_manager.count(part.content)
            part.compression_level = CompressionLevel.TRUNCATED
            total = sum(p.tokens for p in parts)

        if total <= budget:
            return parts

        # Drop lowest-priority non-reserved parts
        parts.sort(key=lambda p: (not p.is_pinned, not p.is_critical, -p.priority, p.tokens))
        survivors = []
        used = 0
        for part in parts:
            if used + part.tokens <= budget:
                survivors.append(part)
                used += part.tokens
            else:
                part.compression_level = CompressionLevel.DROPPED
        return survivors

    def _truncate_parts(
        self,
        parts: List[ContextPart],
        budget: int,
    ) -> List[ContextPart]:
        """Truncate parts proportionally to fit a small budget."""
        total = sum(p.tokens for p in parts)
        if total <= budget:
            return parts
        ratio = budget / max(total, 1)
        for part in parts:
            target = max(20, int(part.tokens * ratio))
            part.content = self.budget_manager.truncate(part.content, target)
            part.tokens = self.budget_manager.count(part.content)
            part.compression_level = CompressionLevel.TRUNCATED
        return parts

    def _summarize_part(
        self,
        part: ContextPart,
        max_tokens: int,
    ) -> ContextPart:
        """Summarize a single part, first by rules and optionally by LLM."""
        if part.tokens <= max_tokens:
            return part

        # Rule-based structured extraction
        extracted = self._structured_extract(part)
        if extracted:
            extracted_tokens = self.budget_manager.count(extracted)
            if extracted_tokens <= max_tokens:
                return ContextPart(
                    content=extracted,
                    source=part.source,
                    priority=part.priority,
                    tokens=extracted_tokens,
                    compression_level=CompressionLevel.STRUCTURED,
                    is_pinned=part.is_pinned,
                    is_critical=part.is_critical,
                    created_at=part.created_at,
                    metadata=part.metadata,
                )

        # LLM summary if enabled
        llm = self._get_llm()
        if llm is not None and llm.is_configured():
            try:
                summary = self._llm_summarize(part.content, max_tokens)
                if summary:
                    summary_tokens = self.budget_manager.count(summary)
                    if summary_tokens <= max_tokens:
                        return ContextPart(
                            content=summary,
                            source=part.source,
                            priority=part.priority,
                            tokens=summary_tokens,
                            compression_level=CompressionLevel.SUMMARIZED,
                            is_pinned=part.is_pinned,
                            is_critical=part.is_critical,
                            created_at=part.created_at,
                            metadata=part.metadata,
                        )
            except Exception as exc:
                logger.warning("LLM summarization failed: %s", exc)

        # Fallback: truncate
        content = self.budget_manager.truncate(part.content, max_tokens)
        return ContextPart(
            content=content,
            source=part.source,
            priority=part.priority,
            tokens=self.budget_manager.count(content),
            compression_level=CompressionLevel.TRUNCATED,
            is_pinned=part.is_pinned,
            is_critical=part.is_critical,
            created_at=part.created_at,
            metadata=part.metadata,
        )

    def _structured_extract(self, part: ContextPart) -> Optional[str]:
        """Extract key parameters, warnings, and file paths from skill outputs."""
        text = part.content
        lines = []

        # Parameters
        params = re.findall(r"(\w+)[=:]([^\s,;]+)", text)
        if params:
            lines.append("Key parameters: " + ", ".join(f"{k}={v}" for k, v in params[:10]))

        # Warnings / errors
        warnings = []
        for sentence in re.split(r"(?<=[.!?])\s+", text):
            lowered = sentence.lower()
            if any(kw in lowered for kw in ["warning", "error", "caution", "note", "attention", "fail"]):
                warnings.append(sentence.strip())
        if warnings:
            lines.append("Warnings: " + "; ".join(warnings[:3]))

        # File paths
        paths = re.findall(r"[\w/\\.-]+\.(?:csv|h5ad|tsv|txt|pdf|png|json|mtx|loom|h5)", text, re.IGNORECASE)
        if paths:
            lines.append("Files: " + ", ".join(paths[:5]))

        if not lines:
            return None
        return " | ".join(lines)

    async def _llm_summarize(self, text: str, max_tokens: int) -> str:
        """Ask LLM to compress a long text into a short summary."""
        llm = self._get_llm()
        if llm is None:
            return ""

        target_words = max(30, int(max_tokens * 0.75))
        prompt = (
            f"Summarize the following bioinformatics context into at most {target_words} words. "
            "Preserve key parameters, warnings, and output files.\n\n"
            f"{text[:4000]}"
        )
        summary = await llm.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=max_tokens,
        )
        return summary.strip()
