"""Build a knowledge graph, vector index and memory entry from extracted fragments."""

import asyncio
import logging
from dataclasses import dataclass
from typing import List, Optional

from homomics_lab.context.graph.base import GraphBackend
from homomics_lab.context.memory_backend import MemoryBackend
from homomics_lab.context.vector_store.base import VectorStoreBackend
from homomics_lab.knowledge.ingestion.models import (
    ExtractedRelation,
    IngestionResult,
    ParsedDocument,
    TextChunk,
)
from homomics_lab.skills.capability_index import CapabilityIndex

logger = logging.getLogger(__name__)

_COLLECTION = "knowledge_chunks"


@dataclass
class BuilderOptions:
    """Options for knowledge graph construction."""

    enable_vector_index: bool = True
    enable_memory_note: bool = True
    enable_capability_index: bool = True


class KnowledgeGraphBuilder:
    """Persist chunks, entities and relations to the configured backends."""

    def __init__(
        self,
        graph_backend: Optional[GraphBackend] = None,
        vector_store: Optional[VectorStoreBackend] = None,
        memory_backend: Optional[MemoryBackend] = None,
        capability_index: Optional[CapabilityIndex] = None,
        embedding_provider=None,
        options: Optional[BuilderOptions] = None,
    ) -> None:
        self.graph_backend = graph_backend
        self.vector_store = vector_store
        self.memory_backend = memory_backend
        self.capability_index = capability_index
        self.embedding_provider = embedding_provider
        self.options = options or BuilderOptions()

    async def build(
        self,
        document_id: str,
        parsed: ParsedDocument,
        chunks: List[TextChunk],
        fragment,
        summary: str,
        project_id: Optional[str] = None,
    ) -> IngestionResult:
        result = IngestionResult(document_id=document_id, source=parsed.source)

        await self._add_document_node(document_id, parsed, summary, project_id)

        chunk_texts = [c.text for c in chunks]
        embeddings = await self._embed(chunk_texts) if self.options.enable_vector_index else None

        if embeddings and self.vector_store is not None:
            try:
                await self.vector_store.upsert(
                    collection=_COLLECTION,
                    ids=[c.chunk_id for c in chunks],
                    texts=chunk_texts,
                    embeddings=embeddings,
                    metadata=[
                        {
                            "document_id": document_id,
                            "project_id": project_id,
                            "chunk_index": c.index,
                        }
                        for c in chunks
                    ],
                )
            except Exception as exc:
                logger.warning("Failed to index knowledge chunks: %s", exc)

        for chunk in chunks:
            await self._add_chunk_node(document_id, chunk, project_id)
        result.chunk_ids = [c.chunk_id for c in chunks]

        entity_names = {e.name for e in fragment.entities}
        for entity in fragment.entities:
            await self._add_entity_node(entity, chunks, project_id)
        for relation in fragment.relations:
            await self._add_relation_edge(relation, project_id)
            # Ensure both endpoints exist even if not in the extracted entity list.
            if relation.source not in entity_names:
                await self._ensure_entity_node(relation.source, project_id)
            if relation.target not in entity_names:
                await self._ensure_entity_node(relation.target, project_id)
        result.entity_names = sorted(entity_names)
        result.relation_count = len(fragment.relations)

        if self.options.enable_memory_note and self.memory_backend is not None:
            try:
                note_text = summary or parsed.text[:1000]
                memory_id = await self.memory_backend.add(
                    text=note_text,
                    memory_type="note",
                    metadata={
                        "document_id": document_id,
                        "source_type": parsed.source.source_type.value,
                        "source": parsed.source.source,
                        "filename": parsed.source.filename,
                        "title": parsed.title,
                        "chunk_count": len(chunks),
                        "entity_count": len(fragment.entities),
                        "relation_count": len(fragment.relations),
                    },
                    importance=0.6,
                    project_id=project_id,
                )
                result.memory_id = memory_id
            except Exception as exc:
                logger.warning("Failed to add document memory note: %s", exc)

        if self.options.enable_capability_index and self.capability_index is not None:
            try:
                data_source_id = f"knowledge:{document_id}"
                await self.capability_index.index_data_source(
                    source_id=data_source_id,
                    name=parsed.title or parsed.source.filename or document_id,
                    description=summary or parsed.text[:500],
                    category="knowledge",
                    metadata={
                        "document_id": document_id,
                        "project_id": project_id,
                        "source_type": parsed.source.source_type.value,
                        "source": parsed.source.source,
                    },
                )
                result.data_source_id = data_source_id
            except Exception as exc:
                logger.warning("Failed to index document as data source: %s", exc)

        return result

    async def _embed(self, texts: List[str]) -> Optional[List[List[float]]]:
        if self.embedding_provider is None:
            return None
        try:
            return await asyncio.to_thread(self.embedding_provider.encode, texts)
        except Exception as exc:
            logger.warning("Embedding failed for knowledge chunks: %s", exc)
            return None

    async def _add_document_node(
        self,
        document_id: str,
        parsed: ParsedDocument,
        summary: str,
        project_id: Optional[str],
    ) -> None:
        if self.graph_backend is None:
            return
        try:
            await self.graph_backend.add_node(
                node_id=f"document:{document_id}",
                labels=["Document"],
                properties={
                    "title": parsed.title or parsed.source.filename or document_id,
                    "source_type": parsed.source.source_type.value,
                    "source": parsed.source.source,
                    "filename": parsed.source.filename,
                    "mime_type": parsed.source.mime_type,
                    "content_hash": parsed.source.content_hash,
                    "summary": summary,
                    "project_id": project_id,
                },
            )
            if project_id:
                await self.graph_backend.add_edge(
                    from_id=f"project:{project_id}",
                    to_id=f"document:{document_id}",
                    edge_type="HAS_DOCUMENT",
                )
        except Exception as exc:
            logger.warning("Failed to add document graph node: %s", exc)

    async def _add_chunk_node(
        self,
        document_id: str,
        chunk: TextChunk,
        project_id: Optional[str],
    ) -> None:
        if self.graph_backend is None:
            return
        try:
            await self.graph_backend.add_node(
                node_id=chunk.chunk_id,
                labels=["DocumentChunk"],
                properties={
                    "text": chunk.text[:500],
                    "index": chunk.index,
                    "estimated_tokens": chunk.estimated_tokens,
                    "document_id": document_id,
                    "project_id": project_id,
                },
            )
            await self.graph_backend.add_edge(
                from_id=chunk.chunk_id,
                to_id=f"document:{document_id}",
                edge_type="PART_OF",
            )
        except Exception as exc:
            logger.warning("Failed to add chunk graph node %s: %s", chunk.chunk_id, exc)

    async def _add_entity_node(self, entity, chunks: List[TextChunk], project_id: Optional[str]) -> None:
        if self.graph_backend is None:
            return
        node_id = f"entity:{entity.name}"
        try:
            await self.graph_backend.add_node(
                node_id=node_id,
                labels=["Entity"],
                properties={
                    "name": entity.name,
                    "entity_type": entity.entity_type,
                    "description": entity.description,
                    "project_id": project_id,
                },
            )
            # Link entity to the first chunk where it appears (best-effort).
            for chunk in chunks:
                if entity.name.lower() in chunk.text.lower():
                    await self.graph_backend.add_edge(
                        from_id=node_id,
                        to_id=chunk.chunk_id,
                        edge_type="MENTIONED_IN",
                    )
                    break
        except Exception as exc:
            logger.warning("Failed to add entity node %s: %s", node_id, exc)

    async def _ensure_entity_node(self, name: str, project_id: Optional[str]) -> None:
        if self.graph_backend is None:
            return
        node_id = f"entity:{name}"
        try:
            await self.graph_backend.add_node(
                node_id=node_id,
                labels=["Entity"],
                properties={"name": name, "entity_type": "unknown", "project_id": project_id},
            )
        except Exception as exc:
            logger.warning("Failed to ensure entity node %s: %s", node_id, exc)

    async def _add_relation_edge(self, relation: ExtractedRelation, project_id: Optional[str]) -> None:
        if self.graph_backend is None:
            return
        try:
            await self.graph_backend.add_edge(
                from_id=f"entity:{relation.source}",
                to_id=f"entity:{relation.target}",
                edge_type=relation.relation_type,
                properties={"project_id": project_id},
            )
        except Exception as exc:
            logger.warning("Failed to add relation edge %s: %s", relation, exc)
