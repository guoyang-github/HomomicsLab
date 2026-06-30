"""High-level KnowledgeIndex facade for document ingestion and search."""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from homomics_lab.config import Settings, settings as default_settings
from homomics_lab.context.graph.base import GraphBackend
from homomics_lab.context.graph.factory import get_graph_backend, reset_graph_backend
from homomics_lab.context.memory_backend import MemoryBackend
from homomics_lab.context.vector_store.base import VectorStoreBackend
from homomics_lab.context.vector_store.factory import get_vector_store, reset_vector_store
from homomics_lab.embeddings.base import EmbeddingProvider
from homomics_lab.embeddings.factory import get_embedding_provider, reset_embedding_provider
from homomics_lab.knowledge.ingestion.models import DocumentSource, IngestionResult
from homomics_lab.knowledge.ingestion.pipeline import CognifyOptions, CognifyPipeline
from homomics_lab.llm_client import LLMClient
from homomics_lab.skills.capability_index import CapabilityIndex

logger = logging.getLogger(__name__)

_COLLECTION = "knowledge_chunks"


class KnowledgeIndex:
    """Facade for the knowledge ingestion subsystem.

    Provides document ingestion from files, URLs or inline text, plus search
    over the resulting chunks and graph entities.
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        llm_client: Optional[LLMClient] = None,
        graph_backend: Optional[GraphBackend] = None,
        vector_store: Optional[VectorStoreBackend] = None,
        memory_backend: Optional[MemoryBackend] = None,
        capability_index: Optional[CapabilityIndex] = None,
        embedding_provider: Optional[EmbeddingProvider] = None,
        options: Optional[CognifyOptions] = None,
    ) -> None:
        self.settings = settings or default_settings
        self._llm_client = llm_client
        self._graph_backend = graph_backend
        self._vector_store = vector_store
        self._memory_backend = memory_backend
        self._capability_index = capability_index
        self._embedding_provider = embedding_provider
        self.options = options

        self._owns_graph = graph_backend is None
        self._owns_vector = vector_store is None
        self._owns_embedding = embedding_provider is None

    # ------------------------------------------------------------------
    # Lazy accessors
    # ------------------------------------------------------------------
    def _get_llm_client(self) -> Optional[LLMClient]:
        return self._llm_client

    def _get_graph_backend(self) -> Optional[GraphBackend]:
        if self._graph_backend is None:
            try:
                self._graph_backend = get_graph_backend(self.settings)
            except Exception as exc:
                logger.warning("KnowledgeIndex could not load graph backend: %s", exc)
        return self._graph_backend

    def _get_vector_store(self) -> Optional[VectorStoreBackend]:
        if self._vector_store is None:
            try:
                self._vector_store = get_vector_store(self.settings)
            except Exception as exc:
                logger.warning("KnowledgeIndex could not load vector store: %s", exc)
        return self._vector_store

    def _get_embedding_provider(self) -> Optional[EmbeddingProvider]:
        if self._embedding_provider is None:
            try:
                self._embedding_provider = get_embedding_provider(self.settings)
            except Exception as exc:
                logger.warning("KnowledgeIndex could not load embedding provider: %s", exc)
        return self._embedding_provider

    def _pipeline(self, project_id: Optional[str] = None) -> CognifyPipeline:
        options = self.options or CognifyOptions()
        if project_id is not None:
            options.project_id = project_id
        return CognifyPipeline(
            llm_client=self._get_llm_client(),
            graph_backend=self._get_graph_backend(),
            vector_store=self._get_vector_store(),
            memory_backend=self._memory_backend,
            capability_index=self._capability_index,
            embedding_provider=self._get_embedding_provider(),
            data_dir=self.settings.data_dir,
            options=options,
        )

    # ------------------------------------------------------------------
    # Public ingestion API
    # ------------------------------------------------------------------
    async def ingest_file(
        self,
        path: Path,
        project_id: Optional[str] = None,
        options: Optional[CognifyOptions] = None,
    ) -> IngestionResult:
        pipeline = self._with_options(options, project_id)
        return await pipeline.ingest_file(Path(path), project_id=project_id)

    async def ingest_text(
        self,
        text: str,
        filename: str = "inline.txt",
        project_id: Optional[str] = None,
        options: Optional[CognifyOptions] = None,
    ) -> IngestionResult:
        pipeline = self._with_options(options, project_id)
        return await pipeline.ingest_text(text, filename=filename, project_id=project_id)

    async def ingest_url(
        self,
        url: str,
        project_id: Optional[str] = None,
        options: Optional[CognifyOptions] = None,
    ) -> IngestionResult:
        pipeline = self._with_options(options, project_id)
        return await pipeline.ingest_url(url, project_id=project_id)

    async def ingest_source(
        self,
        source: DocumentSource,
        project_id: Optional[str] = None,
        options: Optional[CognifyOptions] = None,
    ) -> IngestionResult:
        pipeline = self._with_options(options, project_id)
        return await pipeline.cognify(source)

    def _with_options(
        self, options: Optional[CognifyOptions], project_id: Optional[str]
    ) -> CognifyPipeline:
        base = options or self.options or CognifyOptions()
        if project_id is not None:
            base.project_id = project_id
        return CognifyPipeline(
            llm_client=self._get_llm_client(),
            graph_backend=self._get_graph_backend(),
            vector_store=self._get_vector_store(),
            memory_backend=self._memory_backend,
            capability_index=self._capability_index,
            embedding_provider=self._get_embedding_provider(),
            data_dir=self.settings.data_dir,
            options=base,
        )

    # ------------------------------------------------------------------
    # Search / retrieval
    # ------------------------------------------------------------------
    async def search_chunks(
        self,
        query: str,
        project_id: Optional[str] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Semantic search over ingested knowledge chunks."""
        provider = self._get_embedding_provider()
        vector_store = self._get_vector_store()
        if provider is None or vector_store is None:
            return []

        try:
            embeddings = await asyncio.to_thread(provider.encode, [query])
        except Exception as exc:
            logger.warning("Chunk search embedding failed: %s", exc)
            return []

        filters = {"project_id": project_id} if project_id else None
        try:
            results = await vector_store.search(
                collection=_COLLECTION,
                query_embedding=embeddings[0],
                top_k=top_k,
                filters=filters,
            )
        except Exception as exc:
            logger.warning("Chunk vector search failed: %s", exc)
            return []

        return [
            {
                "id": r.id,
                "text": r.text,
                "score": r.score,
                "metadata": r.metadata or {},
            }
            for r in results
        ]

    async def get_document_graph(self, document_id: str) -> Dict[str, Any]:
        """Return the document node and its linked chunks/entities."""
        graph = self._get_graph_backend()
        if graph is None:
            return {}

        doc_node_id = f"document:{document_id}"
        try:
            chunks = await graph.get_neighbors(doc_node_id, edge_types=["PART_OF"], direction="incoming")
            entities = await graph.get_neighbors(doc_node_id, edge_types=["MENTIONED_IN"], direction="incoming")
            edges = await graph.get_edges(doc_node_id)
            return {
                "document_id": document_id,
                "chunks": [
                    {"id": n.id, "text": n.properties.get("text", ""), "index": n.properties.get("index")}
                    for n in chunks
                ],
                "entities": [
                    {"id": n.id, "name": n.properties.get("name"), "type": n.properties.get("entity_type")}
                    for n in entities
                ],
                "edges": [
                    {"from": e.from_id, "to": e.to_id, "type": e.type, "properties": e.properties}
                    for e in edges
                ],
            }
        except Exception as exc:
            logger.warning("Failed to retrieve document graph: %s", exc)
            return {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def close(self) -> None:
        if self._owns_graph and self._graph_backend is not None:
            try:
                await self._graph_backend.close()
                reset_graph_backend()
            except Exception as exc:
                logger.warning("Graph backend close failed: %s", exc)
        if self._owns_vector and self._vector_store is not None:
            try:
                await self._vector_store.close()
                reset_vector_store()
            except Exception as exc:
                logger.warning("Vector store close failed: %s", exc)
        if self._owns_embedding and self._embedding_provider is not None:
            try:
                reset_embedding_provider()
            except Exception as exc:
                logger.warning("Embedding provider reset failed: %s", exc)


# Ensure asyncio import for search.
import asyncio  # noqa: E402
