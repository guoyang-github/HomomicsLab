"""LLM-based entity/relation extraction and summarization."""

import json
import logging
from dataclasses import dataclass
from typing import Optional

from homomics_lab.knowledge.ingestion.models import (
    ExtractedEntity,
    ExtractedRelation,
    KnowledgeGraphFragment,
)
from homomics_lab.llm_client import LLMClient

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """You are a knowledge-graph extraction assistant.
Analyze the following text and extract entities and relationships as JSON.

Output exactly this JSON structure (no markdown, no extra text):
{{
  "entities": [
    {{"name": "...", "type": "...", "description": "..."}}
  ],
  "relations": [
    {{"source": "...", "target": "...", "relation_type": "..."}}
  ]
}}

Rules:
- entity types: concept, person, organization, method, dataset, gene, protein, disease, chemical, or other.
- Only include entities that are explicitly mentioned or strongly implied.
- Only include relations that are supported by the text.
- Keep descriptions concise (one sentence).

Text:
{text}
"""

SUMMARY_PROMPT = """Summarize the following text in one or two concise sentences.
Return only the summary, no markdown, no extra commentary.

Text:
{text}
"""


@dataclass
class ExtractorOptions:
    enable_extraction: bool = True
    enable_summarization: bool = True
    extraction_model: Optional[str] = None
    summary_model: Optional[str] = None
    max_summary_tokens: int = 200
    max_extraction_tokens: int = 1500


class LLMEntityRelationExtractor:
    """Extract entities and relations from text using an LLM."""

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        options: Optional[ExtractorOptions] = None,
    ) -> None:
        self.llm_client = llm_client
        self.options = options or ExtractorOptions()

    async def extract(self, text: str) -> KnowledgeGraphFragment:
        if not self.options.enable_extraction or not text.strip():
            return KnowledgeGraphFragment()
        if self.llm_client is None:
            return KnowledgeGraphFragment()

        try:
            response = await self.llm_client.chat_completion(
                messages=[
                    {"role": "system", "content": "You output valid JSON only."},
                    {"role": "user", "content": EXTRACTION_PROMPT.format(text=text[:8000])},
                ],
                temperature=0.1,
                max_tokens=self.options.max_extraction_tokens,
                response_format={"type": "json_object"},
                model=self.options.extraction_model,
                prefer_cheap=True,
            )
            return self._parse(response)
        except Exception as exc:
            logger.warning("Entity/relation extraction failed: %s", exc)
            return KnowledgeGraphFragment()

    @staticmethod
    def _parse(response: str) -> KnowledgeGraphFragment:
        try:
            data = json.loads(response or "{}")
        except json.JSONDecodeError:
            # Try to extract JSON from a markdown code block.
            import re
            match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response, re.S)
            if match:
                data = json.loads(match.group(1))
            else:
                return KnowledgeGraphFragment()

        entities = [
            ExtractedEntity(
                name=str(e.get("name", "")).strip(),
                entity_type=str(e.get("type", "concept")).strip().lower() or "concept",
                description=str(e.get("description", "")).strip(),
            )
            for e in data.get("entities", [])
            if e.get("name")
        ]
        relations = [
            ExtractedRelation(
                source=str(r.get("source", "")).strip(),
                target=str(r.get("target", "")).strip(),
                relation_type=str(r.get("relation_type", "relates_to")).strip().lower() or "relates_to",
            )
            for r in data.get("relations", [])
            if r.get("source") and r.get("target")
        ]
        return KnowledgeGraphFragment(entities=entities, relations=relations)


class LLMSummarizer:
    """Generate short summaries using an LLM."""

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        options: Optional[ExtractorOptions] = None,
    ) -> None:
        self.llm_client = llm_client
        self.options = options or ExtractorOptions()

    async def summarize(self, text: str) -> str:
        if not self.options.enable_summarization or not text.strip():
            return ""
        if self.llm_client is None:
            return text[:500]

        try:
            return await self.llm_client.chat_completion(
                messages=[
                    {"role": "user", "content": SUMMARY_PROMPT.format(text=text[:12000])},
                ],
                temperature=0.1,
                max_tokens=self.options.max_summary_tokens,
                model=self.options.summary_model,
                prefer_cheap=True,
            )
        except Exception as exc:
            logger.warning("Summarization failed: %s", exc)
            return text[:500]
