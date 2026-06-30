"""Data models for the knowledge ingestion pipeline."""

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class SourceType(str, Enum):
    FILE = "file"
    URL = "url"
    TEXT = "text"


@dataclass
class DocumentSource:
    """Original source of a document."""

    source_type: SourceType
    source: str
    filename: Optional[str] = None
    mime_type: Optional[str] = None
    content_hash: Optional[str] = None

    @classmethod
    def from_file(cls, path: Path) -> "DocumentSource":
        import mimetypes

        path = Path(path)
        mime, _ = mimetypes.guess_type(path.name)
        content = path.read_bytes()
        return cls(
            source_type=SourceType.FILE,
            source=str(path.resolve()),
            filename=path.name,
            mime_type=mime or "application/octet-stream",
            content_hash=hashlib.sha256(content).hexdigest(),
        )

    @classmethod
    def from_text(cls, text: str, filename: str = "inline.txt") -> "DocumentSource":
        return cls(
            source_type=SourceType.TEXT,
            source=text,
            filename=filename,
            mime_type="text/plain",
            content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        )

    @classmethod
    def from_url(cls, url: str, filename: Optional[str] = None) -> "DocumentSource":
        return cls(
            source_type=SourceType.URL,
            source=url,
            filename=filename or url.split("/")[-1].split("?")[0] or "download",
            mime_type=None,
            content_hash=None,
        )


@dataclass
class ParsedDocument:
    """Result of parsing a raw document into clean text."""

    source: DocumentSource
    title: Optional[str] = None
    text: str = ""
    pages: List[str] = field(default_factory=list)
    paragraphs: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TextChunk:
    """A single semantic chunk."""

    chunk_id: str
    document_id: str
    text: str
    index: int = 0
    estimated_tokens: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractedEntity:
    """Entity extracted from text."""

    name: str
    entity_type: str = "concept"
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractedRelation:
    """Relationship between two entities."""

    source: str
    target: str
    relation_type: str
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class KnowledgeGraphFragment:
    """A batch of extracted entities and relations."""

    entities: List[ExtractedEntity] = field(default_factory=list)
    relations: List[ExtractedRelation] = field(default_factory=list)


@dataclass
class IngestionResult:
    """Summary of a completed ingestion."""

    document_id: str
    source: DocumentSource
    chunk_ids: List[str] = field(default_factory=list)
    entity_names: List[str] = field(default_factory=list)
    relation_count: int = 0
    memory_id: Optional[str] = None
    data_source_id: Optional[str] = None
    already_processed: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
