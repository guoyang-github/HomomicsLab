"""Data models for the LLM Wiki layer."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class WikiPage:
    """A single concept/topic page in the LLM Wiki.

    Pages are either auto-generated from ingested document chunks/entities or
    created manually by users.  They are project-scoped and can be edited,
    linked, and versioned.
    """

    page_id: str
    project_id: str
    title: str
    content: str
    source_document_ids: List[str] = field(default_factory=list)
    source_chunk_ids: List[str] = field(default_factory=list)
    entity_types: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    created_by: Optional[str] = None  # "system" | "llm" | user_id
    version: int = 1


@dataclass
class WikiLink:
    """A typed link between two wiki pages."""

    source_id: str
    target_id: str
    relation: str = "related"  # e.g. "related", "prerequisite", "subconcept", "references"
    strength: float = 1.0
    evidence: List[str] = field(default_factory=list)  # chunk ids or sentence snippets
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WikiQueryResult:
    """Result of a wiki / document RAG query."""

    answer: str
    sources: List[Dict[str, Any]] = field(default_factory=list)
    suggested_pages: List[str] = field(default_factory=list)
