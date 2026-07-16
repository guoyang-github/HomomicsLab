"""LLM Wiki engine: generate pages, links, and answer questions."""

import logging
import uuid
from typing import Any, Dict, List, Optional

from homomics_lab.knowledge.ingestion.index import KnowledgeIndex
from homomics_lab.knowledge.wiki.models import WikiLink, WikiPage, WikiQueryResult
from homomics_lab.knowledge.wiki.store import WikiStore
from homomics_lab.llm_client import LLMClient

logger = logging.getLogger(__name__)


class WikiEngine:
    """Generate and query an LLM-assisted wiki on top of ingested documents.

    The engine is intentionally decoupled from the ingestion graph backend:
    it uses ``KnowledgeIndex`` for retrieval and ``WikiStore`` for the wiki
    pages/links, so it works even when the graph backend is disabled.
    """

    def __init__(
        self,
        store: Optional[WikiStore] = None,
        knowledge_index: Optional[KnowledgeIndex] = None,
        llm_client: Optional[LLMClient] = None,
    ):
        self.store = store or WikiStore()
        self.knowledge_index = knowledge_index
        self._llm_client = llm_client

    def _get_llm_client(self) -> Optional[LLMClient]:
        if self._llm_client is None:
            try:
                self._llm_client = LLMClient()
            except Exception as exc:
                logger.warning("WikiEngine could not create LLMClient: %s", exc)
        return self._llm_client

    async def generate_pages_from_document(
        self,
        document_id: str,
        project_id: str,
        knowledge_index: Optional[KnowledgeIndex] = None,
    ) -> List[WikiPage]:
        """Create or update wiki pages from the entities/chunks of a document."""
        index = knowledge_index or self.knowledge_index
        if index is None:
            return []

        graph = await index.get_document_graph(document_id)
        chunks: List[Dict[str, Any]] = graph.get("chunks", [])
        entities: List[Dict[str, Any]] = graph.get("entities", [])

        created: List[WikiPage] = []
        # One page per entity.
        for entity in entities:
            name = entity.get("name") or entity.get("id", "")
            entity_type = entity.get("type") or "concept"
            if not name:
                continue
            related_chunks = [
                c["text"] for c in chunks if name.lower() in (c.get("text") or "").lower()
            ][:3]
            content = self._entity_page_content(name, entity_type, related_chunks)
            page = WikiPage(
                page_id=str(uuid.uuid4()),
                project_id=project_id,
                title=name,
                content=content,
                source_document_ids=[document_id],
                source_chunk_ids=[c.get("id") for c in chunks if name.lower() in (c.get("text") or "").lower()][:5],
                entity_types=[entity_type],
                created_by="system",
                metadata={"auto_generated": True, "entity_id": entity.get("id")},
            )
            created.append(self.store.create_page(page))

        if not entities and chunks:
            # No entities: synthesize one page from the first few chunks.
            title = f"Document {document_id[:8]}"
            content = "\n\n".join(c.get("text", "") for c in chunks[:5])
            page = WikiPage(
                page_id=str(uuid.uuid4()),
                project_id=project_id,
                title=title,
                content=content,
                source_document_ids=[document_id],
                source_chunk_ids=[c.get("id") for c in chunks[:5]],
                created_by="system",
                metadata={"auto_generated": True, "synthesized": True},
            )
            created.append(self.store.create_page(page))

        # Build simple co-occurrence links between pages from the same document.
        self._link_cooccurring_pages(created)
        return created

    def _entity_page_content(
        self,
        name: str,
        entity_type: str,
        snippets: List[str],
    ) -> str:
        parts = [f"# {name}", f"**Type:** {entity_type}", ""]
        if snippets:
            parts.append("## Mentions")
            for s in snippets:
                parts.append(f"- {s[:300]}{'...' if len(s) > 300 else ''}")
        else:
            parts.append("_No direct mentions extracted from source documents._")
        return "\n\n".join(parts)

    def _link_cooccurring_pages(self, pages: List[WikiPage]) -> None:
        """Create 'related' links between pages that share source chunks."""
        for i, src in enumerate(pages):
            for tgt in pages[i + 1 :]:
                shared = set(src.source_chunk_ids) & set(tgt.source_chunk_ids)
                if not shared:
                    continue
                self.store.create_or_update_link(
                    WikiLink(
                        source_id=src.page_id,
                        target_id=tgt.page_id,
                        relation="related",
                        strength=min(1.0, 0.3 + 0.1 * len(shared)),
                        evidence=list(shared)[:5],
                        metadata={"auto": True},
                    )
                )

    async def answer(
        self,
        question: str,
        project_id: str,
        top_k: int = 5,
    ) -> WikiQueryResult:
        """Answer a question using wiki pages + document chunks."""
        pages = self.store.list_pages(project_id, query=question, limit=top_k)
        chunks: List[Dict[str, Any]] = []
        if self.knowledge_index is not None:
            try:
                chunks = await self.knowledge_index.search_chunks(
                    question, project_id=project_id, top_k=top_k
                )
            except Exception as exc:
                logger.warning("Wiki answer chunk retrieval failed: %s", exc)

        context_parts: List[str] = []
        for p in pages:
            context_parts.append(f"## Wiki: {p.title}\n{p.content[:1200]}")
        for c in chunks:
            text = c.get("text", "")
            context_parts.append(f"## Source snippet\n{text[:800]}")

        if not context_parts:
            return WikiQueryResult(
                answer="No relevant wiki pages or document chunks were found.",
                sources=[],
                suggested_pages=[],
            )

        prompt = self._answer_prompt(question, context_parts)
        answer_text = await self._generate(prompt)

        sources: List[Dict[str, Any]] = []
        for p in pages:
            sources.append({"type": "wiki", "id": p.page_id, "title": p.title})
        for c in chunks:
            sources.append({"type": "chunk", "id": c.get("id"), "score": c.get("score")})

        return WikiQueryResult(
            answer=answer_text,
            sources=sources,
            suggested_pages=[p.title for p in pages[:3]],
        )

    def _answer_prompt(self, question: str, context_parts: List[str]) -> str:
        context = "\n\n".join(context_parts)
        return (
            "You are a scientific research assistant. Use the following wiki pages "
            "and source snippets to answer the user's question. If the context does "
            "not contain enough information, say so. Cite sources implicitly by "
            "referring to the wiki page titles or source concepts.\n\n"
            f"Context:\n{context}\n\n"
            f"Question: {question}\n\nAnswer:"
        )

    async def _generate(self, prompt: str) -> str:
        client = self._get_llm_client()
        if client is None:
            return "[LLM unavailable]"
        try:
            response = await client.chat_completion(
                messages=[
                    {"role": "system", "content": "You are a scientific research assistant."},
                    {"role": "user", "content": prompt},
                ]
            )
            return response.choices[0].message.content.strip()
        except Exception as exc:
            logger.warning("Wiki LLM generation failed: %s", exc)
            return f"[Generation failed: {exc}]"

    async def create_manual_page(
        self,
        project_id: str,
        title: str,
        content: str,
        created_by: str = "user",
    ) -> WikiPage:
        """Create a user-authored wiki page."""
        page = WikiPage(
            page_id=str(uuid.uuid4()),
            project_id=project_id,
            title=title,
            content=content,
            created_by=created_by,
            metadata={"auto_generated": False},
        )
        return self.store.create_page(page)
