"""ContextEngine — unified context assembly for HomomicsLab.

Builds a token-safe, relevance-ranked prompt from layered memory sources.
"""

import logging
from collections import Counter
from typing import Any, Dict, List, Optional

from homomics_lab.context.cbkb_retriever import CBKBRetriever
from homomics_lab.context.context_engine.compressor import DynamicContextCompressor
from homomics_lab.context.context_engine.models import (
    CompressionLevel,
    ContextBundle,
    ContextPart,
    ContextSource,
)
from homomics_lab.context.context_engine.ranker import ContextRanker
from homomics_lab.context.episodic_summary import EpisodicSummarizer
from homomics_lab.context.project_state import ProjectStateManager
from homomics_lab.context.semantic_memory import SemanticMemory
from homomics_lab.context.token_budget import TokenBudgetManager
from homomics_lab.context.working_memory import WorkingMemory
from homomics_lab.knowledge.cbkb import CBKB
from homomics_lab.llm_client import LLMClient
from homomics_lab.metrics import record_context_build

logger = logging.getLogger(__name__)


class ContextEngine:
    """Assemble a context bundle for an LLM call."""

    def __init__(
        self,
        cbkb: CBKB,
        semantic_memory: Optional[SemanticMemory] = None,
        project_state_manager: Optional[ProjectStateManager] = None,
        cbkb_retriever: Optional[CBKBRetriever] = None,
        episodic_summarizer: Optional[EpisodicSummarizer] = None,
        embedding_model_name: Optional[str] = None,
        default_model: str = "default",
        enable_llm_summary: bool = True,
        llm_client: Optional[LLMClient] = None,
    ):
        self.cbkb = cbkb
        self.semantic_memory = semantic_memory
        self.project_state_manager = project_state_manager or ProjectStateManager(cbkb)
        self.cbkb_retriever = cbkb_retriever or CBKBRetriever(
            cbkb=cbkb,
            embedding_model_name=embedding_model_name,
        )
        self.episodic_summarizer = episodic_summarizer or EpisodicSummarizer(llm_client)
        self.ranker = ContextRanker(embedding_model_name=embedding_model_name)
        self.default_model = default_model
        self.enable_llm_summary = enable_llm_summary
        self.llm_client = llm_client

    async def build(
        self,
        user_message: str,
        working_memory: WorkingMemory,
        project_id: str,
        model: Optional[str] = None,
        intent: Optional[Any] = None,
        reserved_output_tokens: Optional[int] = None,
    ) -> ContextBundle:
        """Build a token-safe context bundle for the current turn."""
        model = model or self.default_model
        budget_manager = TokenBudgetManager(
            model=model,
            output_reserve_tokens=reserved_output_tokens,
        )
        input_budget = budget_manager.available_input_tokens()

        # Collect candidate context parts
        parts: List[ContextPart] = []

        # 1. System prompt (always included, high priority)
        system_prompt = self._system_prompt()
        parts.append(
            ContextPart(
                content=system_prompt,
                source=ContextSource.SYSTEM,
                priority=10,
                tokens=budget_manager.count(system_prompt),
                is_critical=True,
            )
        )

        # 2. Project state
        try:
            project_state = self.project_state_manager.load(project_id)
            state_text = project_state.to_prompt_text()
            if state_text:
                parts.append(
                    ContextPart(
                        content=state_text,
                        source=ContextSource.PROJECT_STATE,
                        priority=10,
                        tokens=budget_manager.count(state_text),
                        is_critical=True,
                    )
                )
        except Exception as exc:
            logger.warning("Failed to load project state: %s", exc)

        # 3. CBKB retrieval
        try:
            cbkb_items = await self.cbkb_retriever.retrieve(
                project_id=project_id,
                query=user_message,
                intent=intent,
                top_k=10,
            )
            for item in cbkb_items:
                parts.append(
                    ContextPart(
                        content=item.content,
                        source=ContextSource.CBKB,
                        priority=item.priority,
                        tokens=budget_manager.count(item.content),
                        is_critical=item.source == "anomaly" and item.priority >= 9,
                        metadata=item.metadata,
                    )
                )
        except Exception as exc:
            logger.warning("CBKB retrieval failed: %s", exc)

        # 4. Semantic memory
        if self.semantic_memory is not None:
            try:
                memories = await self.semantic_memory.search(
                    query=user_message,
                    top_k=5,
                    project_id=project_id,
                )
                for mem in memories:
                    text = mem.get("text", "")
                    if text:
                        parts.append(
                            ContextPart(
                                content=text,
                                source=ContextSource.SEMANTIC_MEMORY,
                                priority=6,
                                tokens=budget_manager.count(text),
                                metadata={
                                    "memory_id": mem.get("id"),
                                    "memory_type": mem.get("memory_type"),
                                },
                            )
                        )
            except Exception as exc:
                logger.warning("Semantic memory retrieval failed: %s", exc)

        # 5. Episodic summary
        try:
            summary = await self.episodic_summarizer.summarize(
                working_memory.get_recent_messages(10)
            )
            summary_text = summary.to_text()
            if summary_text:
                parts.append(
                    ContextPart(
                        content=summary_text,
                        source=ContextSource.EPISODIC_SUMMARY,
                        priority=7,
                        tokens=budget_manager.count(summary_text),
                    )
                )
        except Exception as exc:
            logger.warning("Episodic summary failed: %s", exc)

        # 6. Working memory chat messages
        chat_items = working_memory.to_context_items()
        for item in chat_items:
            item.tokens = budget_manager.count(item.content)
            item.source = ContextSource.CHAT
            parts.append(item)

        # Capture source-level token counts before deduplication/compression.
        source_tokens: Dict[str, int] = Counter()
        for part in parts:
            source_tokens[part.source.value] += part.tokens or 0

        before_counts: Dict[str, int] = Counter(p.source.value for p in parts)

        # Rank and deduplicate
        parts = self.ranker.deduplicate(parts)
        parts = self.ranker.rank(parts, query=user_message)

        after_counts: Dict[str, int] = Counter(p.source.value for p in parts)
        dropped_by_duplicate = {
            source: before_counts[source] - after_counts[source]
            for source in before_counts
            if before_counts[source] > after_counts.get(source, 0)
        }

        # Compress to budget
        compressor = DynamicContextCompressor(
            budget_manager=budget_manager,
            llm_client=self.llm_client,
            enable_llm_summary=self.enable_llm_summary,
        )
        compressed = compressor.compress(parts, input_budget)

        # Assemble messages
        messages = self._assemble_messages(compressed, user_message)

        # Validate
        used_tokens = budget_manager.count_messages(messages)
        metadata = {
            "model": model,
            "max_context": budget_manager.max_context_tokens,
            "input_budget": input_budget,
            "used_tokens": used_tokens,
            "compression_levels": self._compression_summary(compressed),
            "dropped_count": len(parts) - len(compressed),
        }

        dropped_by_source: Dict[str, int] = {}
        kept_ids = {id(p) for p in compressed}
        for part in parts:
            if id(part) not in kept_ids and part.compression_level == CompressionLevel.DROPPED:
                dropped_by_source[part.source.value] = dropped_by_source.get(part.source.value, 0) + 1

        record_context_build(
            model=model,
            used_tokens=used_tokens,
            kept_parts=len(compressed),
            total_parts=len(parts),
            dropped_by_source=dropped_by_source,
            source_tokens=dict(source_tokens),
            dropped_by_duplicate=dropped_by_duplicate,
        )

        return ContextBundle(messages=messages, metadata=metadata)

    @staticmethod
    def _system_prompt() -> str:
        return (
            "You are HomomicsLab, an AI assistant specialized in bioinformatics analysis. "
            "You help researchers design experiments, analyze omics data, and interpret results. "
            "Be concise, accurate, and ask for clarification when needed."
        )

    def _assemble_messages(
        self,
        parts: List[ContextPart],
        user_message: str,
    ) -> List[Dict[str, str]]:
        """Assemble OpenAI-style messages from compressed parts."""
        system_parts: List[str] = []
        recent_messages: List[Dict[str, str]] = []

        for part in parts:
            if part.compression_level == CompressionLevel.DROPPED:
                continue
            if part.source in (
                ContextSource.SYSTEM,
                ContextSource.PROJECT_STATE,
                ContextSource.CBKB,
                ContextSource.SEMANTIC_MEMORY,
                ContextSource.EPISODIC_SUMMARY,
            ):
                system_parts.append(part.content)
            elif part.source == ContextSource.CHAT:
                # Chat items are already prefixed with sender.
                content = part.content
                if content.startswith("user: "):
                    recent_messages.append({"role": "user", "content": content[6:]})
                elif content.startswith("agent: "):
                    recent_messages.append({"role": "assistant", "content": content[7:]})
                else:
                    recent_messages.append({"role": "system", "content": content})

        messages: List[Dict[str, str]] = []
        if system_parts:
            messages.append({"role": "system", "content": "\n\n".join(system_parts)})
        messages.extend(recent_messages)
        messages.append({"role": "user", "content": user_message})
        return messages

    @staticmethod
    def _compression_summary(parts: List[ContextPart]) -> Dict[str, int]:
        summary: Dict[str, int] = {}
        for part in parts:
            level = part.compression_level.value
            summary[level] = summary.get(level, 0) + 1
        return summary
