"""Cognify-style pipeline: parse -> chunk -> summarize -> extract -> load."""

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from homomics_lab.context.graph.base import GraphBackend
from homomics_lab.context.memory_backend import MemoryBackend
from homomics_lab.context.vector_store.base import VectorStoreBackend
from homomics_lab.embeddings.base import EmbeddingProvider
from homomics_lab.knowledge.ingestion.builder import BuilderOptions, KnowledgeGraphBuilder
from homomics_lab.knowledge.ingestion.chunker import ChunkerOptions, TextChunker
from homomics_lab.knowledge.ingestion.extractor import (
    ExtractorOptions,
    LLMEntityRelationExtractor,
    LLMSummarizer,
)
from homomics_lab.knowledge.ingestion.models import (
    DocumentSource,
    IngestionResult,
    KnowledgeGraphFragment,
    ParsedDocument,
)
from homomics_lab.knowledge.ingestion.parser_registry import ParserRegistry
from homomics_lab.llm_client import LLMClient
from homomics_lab.skills.capability_index import CapabilityIndex

logger = logging.getLogger(__name__)


@dataclass
class CognifyOptions:
    """Pipeline-level options."""

    chunker: ChunkerOptions = field(default_factory=ChunkerOptions)
    extractor: ExtractorOptions = field(default_factory=ExtractorOptions)
    builder: BuilderOptions = field(default_factory=BuilderOptions)
    project_id: Optional[str] = None
    skip_existing: bool = True
    max_concurrent_extractions: int = 4


class CognifyPipeline:
    """Transform a document into a searchable knowledge graph."""

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        graph_backend: Optional[GraphBackend] = None,
        vector_store: Optional[VectorStoreBackend] = None,
        memory_backend: Optional[MemoryBackend] = None,
        capability_index: Optional[CapabilityIndex] = None,
        embedding_provider: Optional[EmbeddingProvider] = None,
        parser_registry: Optional[ParserRegistry] = None,
        data_dir: Optional[Path] = None,
        options: Optional[CognifyOptions] = None,
    ) -> None:
        self.llm_client = llm_client
        self.graph_backend = graph_backend
        self.vector_store = vector_store
        self.memory_backend = memory_backend
        self.capability_index = capability_index
        self.embedding_provider = embedding_provider
        self.parser_registry = parser_registry or ParserRegistry()
        self.data_dir = data_dir
        self.options = options or CognifyOptions()

        self.chunker = TextChunker(self.options.chunker)
        self.extractor = LLMEntityRelationExtractor(llm_client, self.options.extractor)
        self.summarizer = LLMSummarizer(llm_client, self.options.extractor)
        self.builder = KnowledgeGraphBuilder(
            graph_backend=graph_backend,
            vector_store=vector_store,
            memory_backend=memory_backend,
            capability_index=capability_index,
            embedding_provider=embedding_provider,
            options=self.options.builder,
        )

    async def cognify(self, source: DocumentSource) -> IngestionResult:
        """Run the full ECL pipeline on a document source."""
        parsed = await self._parse(source)
        content_hash = hashlib.sha256(parsed.text.encode("utf-8")).hexdigest()
        document_id = f"doc-{content_hash[:16]}"

        if self.options.skip_existing and await self._is_processed(content_hash):
            return IngestionResult(
                document_id=document_id,
                source=parsed.source,
                already_processed=True,
            )

        chunks = self.chunker.chunk(parsed, document_id)
        doc_summary, fragment = await asyncio.gather(
            self.summarizer.summarize(parsed.text),
            self._extract_from_chunks(chunks),
        )

        result = await self.builder.build(
            document_id=document_id,
            parsed=parsed,
            chunks=chunks,
            fragment=fragment,
            summary=doc_summary,
            project_id=self.options.project_id,
        )

        await self._mark_processed(content_hash, document_id)
        return result

    async def ingest_file(self, path: Path, project_id: Optional[str] = None) -> IngestionResult:
        if project_id is not None:
            self.options.project_id = project_id
        source = DocumentSource.from_file(Path(path))
        return await self.cognify(source)

    async def ingest_text(self, text: str, filename: str = "inline.txt", project_id: Optional[str] = None) -> IngestionResult:
        if project_id is not None:
            self.options.project_id = project_id
        source = DocumentSource.from_text(text, filename)
        return await self.cognify(source)

    async def ingest_url(self, url: str, project_id: Optional[str] = None) -> IngestionResult:
        if project_id is not None:
            self.options.project_id = project_id
        source = DocumentSource.from_url(url)
        return await self.cognify(source)

    async def _parse(self, source: DocumentSource) -> ParsedDocument:
        parser = self.parser_registry.select(source)
        return await parser.parse(source)

    async def _extract_from_chunks(self, chunks: List) -> KnowledgeGraphFragment:
        if not self.options.extractor.enable_extraction or not chunks:
            return KnowledgeGraphFragment()

        semaphore = asyncio.Semaphore(self.options.max_concurrent_extractions)

        async def _one(chunk):
            async with semaphore:
                return await self.extractor.extract(chunk.text)

        fragments = await asyncio.gather(*(_one(c) for c in chunks), return_exceptions=True)
        merged = KnowledgeGraphFragment()
        seen_entities = set()
        seen_relations = set()
        for item in fragments:
            if isinstance(item, Exception):
                logger.warning("Extraction failed for a chunk: %s", item)
                continue
            for e in item.entities:
                key = (e.name.lower(), e.entity_type.lower())
                if key not in seen_entities:
                    seen_entities.add(key)
                    merged.entities.append(e)
            for r in item.relations:
                key = (r.source.lower(), r.target.lower(), r.relation_type.lower())
                if key not in seen_relations:
                    seen_relations.add(key)
                    merged.relations.append(r)
        return merged

    def _processed_file(self) -> Optional[Path]:
        if self.data_dir is None:
            return None
        path = Path(self.data_dir) / "knowledge_ingestion"
        path.mkdir(parents=True, exist_ok=True)
        return path / "processed_hashes.json"

    async def _is_processed(self, content_hash: str) -> bool:
        path = self._processed_file()
        if path is None:
            return False

        def _read() -> Dict[str, Any]:
            if not path.exists():
                return {}
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                return {}

        data = await asyncio.to_thread(_read)
        return content_hash in data

    async def _mark_processed(self, content_hash: str, document_id: str) -> None:
        path = self._processed_file()
        if path is None:
            return

        def _write() -> None:
            data: Dict[str, Any] = {}
            if path.exists():
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except Exception:
                    pass
            data[content_hash] = {
                "document_id": document_id,
                "processed_at": datetime.now(timezone.utc).isoformat(),
            }
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        await asyncio.to_thread(_write)
