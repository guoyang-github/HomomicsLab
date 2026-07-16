"""SQLite-backed store for LLM Wiki pages and links."""

import json
import logging
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from homomics_lab.config import settings
from homomics_lab.knowledge.wiki.models import WikiLink, WikiPage

logger = logging.getLogger(__name__)


class WikiStore:
    """Persistent store for wiki pages and links.

    Uses a local SQLite database under ``settings.data_dir / "wiki.db"``.
    The schema is intentionally simple: pages, links, and a full-text search
    index over page content.
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or (settings.data_dir / "wiki.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS wiki_pages (
                    page_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source_document_ids TEXT NOT NULL DEFAULT '[]',
                    source_chunk_ids TEXT NOT NULL DEFAULT '[]',
                    entity_types TEXT NOT NULL DEFAULT '[]',
                    metadata TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    created_by TEXT,
                    version INTEGER NOT NULL DEFAULT 1
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS wiki_links (
                    source_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    relation TEXT NOT NULL DEFAULT 'related',
                    strength REAL NOT NULL DEFAULT 1.0,
                    evidence TEXT NOT NULL DEFAULT '[]',
                    metadata TEXT NOT NULL DEFAULT '{}',
                    PRIMARY KEY (source_id, target_id, relation)
                )
                """
            )
            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS wiki_fts USING fts5(
                    title, content,
                    content='wiki_pages',
                    content_rowid='rowid'
                )
                """
            )
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS wiki_pages_ai AFTER INSERT ON wiki_pages BEGIN
                    INSERT INTO wiki_fts(rowid, title, content)
                    VALUES (NEW.rowid, NEW.title, NEW.content);
                END
                """
            )
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS wiki_pages_ad AFTER DELETE ON wiki_pages BEGIN
                    INSERT INTO wiki_fts(wiki_fts, rowid, title, content)
                    VALUES ('delete', OLD.rowid, OLD.title, OLD.content);
                END
                """
            )
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS wiki_pages_au AFTER UPDATE ON wiki_pages BEGIN
                    INSERT INTO wiki_fts(wiki_fts, rowid, title, content)
                    VALUES ('delete', OLD.rowid, OLD.title, OLD.content);
                    INSERT INTO wiki_fts(rowid, title, content)
                    VALUES (NEW.rowid, NEW.title, NEW.content);
                END
                """
            )
            conn.commit()

    def create_page(self, page: WikiPage) -> WikiPage:
        """Insert a new wiki page."""
        page.page_id = page.page_id or str(uuid.uuid4())
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO wiki_pages (
                    page_id, project_id, title, content, source_document_ids,
                    source_chunk_ids, entity_types, metadata, created_at,
                    updated_at, created_by, version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    page.page_id,
                    page.project_id,
                    page.title,
                    page.content,
                    json.dumps(page.source_document_ids or [], ensure_ascii=False),
                    json.dumps(page.source_chunk_ids or [], ensure_ascii=False),
                    json.dumps(page.entity_types or [], ensure_ascii=False),
                    json.dumps(page.metadata or {}, ensure_ascii=False),
                    page.created_at,
                    page.updated_at,
                    page.created_by,
                    page.version,
                ),
            )
            conn.commit()
        return page

    def get_page(self, page_id: str) -> Optional[WikiPage]:
        """Fetch a single page by id."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM wiki_pages WHERE page_id = ?", (page_id,)
            ).fetchone()
        if row is None:
            return None
        return self._row_to_page(row)

    def update_page(
        self,
        page_id: str,
        title: Optional[str] = None,
        content: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[WikiPage]:
        """Update editable fields of a page and bump its version."""
        page = self.get_page(page_id)
        if page is None:
            return None
        page.title = title if title is not None else page.title
        page.content = content if content is not None else page.content
        if metadata is not None:
            page.metadata.update(metadata)
        page.version += 1
        from datetime import datetime, timezone

        page.updated_at = datetime.now(timezone.utc).isoformat()
        with self._connection() as conn:
            conn.execute(
                """
                UPDATE wiki_pages SET
                    title = ?, content = ?, metadata = ?, version = ?, updated_at = ?
                WHERE page_id = ?
                """,
                (
                    page.title,
                    page.content,
                    json.dumps(page.metadata, ensure_ascii=False),
                    page.version,
                    page.updated_at,
                    page_id,
                ),
            )
            conn.commit()
        return page

    def delete_page(self, page_id: str) -> bool:
        """Delete a page and its outgoing links."""
        with self._connection() as conn:
            cur = conn.execute("DELETE FROM wiki_pages WHERE page_id = ?", (page_id,))
            conn.execute("DELETE FROM wiki_links WHERE source_id = ? OR target_id = ?", (page_id, page_id))
            conn.commit()
        return cur.rowcount > 0

    def list_pages(
        self,
        project_id: str,
        query: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[WikiPage]:
        """List pages for a project, optionally full-text searched."""
        with self._connection() as conn:
            if query:
                safe_query = self._escape_fts_query(query)
                rows = conn.execute(
                    """
                    SELECT p.* FROM wiki_pages p
                    JOIN wiki_fts f ON p.rowid = f.rowid
                    WHERE p.project_id = ? AND wiki_fts MATCH ?
                    ORDER BY rank
                    LIMIT ? OFFSET ?
                    """,
                    (project_id, safe_query, limit, offset),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM wiki_pages
                    WHERE project_id = ?
                    ORDER BY updated_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (project_id, limit, offset),
                ).fetchall()
        return [self._row_to_page(row) for row in rows]

    @staticmethod
    def _escape_fts_query(query: str) -> str:
        """Escape FTS5 query tokens and join with AND."""
        tokens = [t for t in query.replace("'", "").split() if t]
        if not tokens:
            return "*"
        return " AND ".join(f'"{t}"' for t in tokens)

    def create_or_update_link(self, link: WikiLink) -> WikiLink:
        """Upsert a link between two pages."""
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO wiki_links (source_id, target_id, relation, strength, evidence, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id, target_id, relation) DO UPDATE SET
                    strength = excluded.strength,
                    evidence = excluded.evidence,
                    metadata = excluded.metadata
                """,
                (
                    link.source_id,
                    link.target_id,
                    link.relation,
                    link.strength,
                    json.dumps(link.evidence or [], ensure_ascii=False),
                    json.dumps(link.metadata or {}, ensure_ascii=False),
                ),
            )
            conn.commit()
        return link

    def get_links(
        self,
        page_id: str,
        direction: str = "both",
    ) -> List[WikiLink]:
        """Return links from, to, or both directions for a page."""
        links: List[WikiLink] = []
        with self._connection() as conn:
            if direction in ("from", "both"):
                rows = conn.execute(
                    "SELECT * FROM wiki_links WHERE source_id = ?", (page_id,)
                ).fetchall()
                links.extend(self._row_to_link(row) for row in rows)
            if direction in ("to", "both"):
                rows = conn.execute(
                    "SELECT * FROM wiki_links WHERE target_id = ?", (page_id,)
                ).fetchall()
                links.extend(self._row_to_link(row) for row in rows)
        return links

    def _row_to_page(self, row: sqlite3.Row) -> WikiPage:
        from homomics_lab.knowledge.wiki.models import WikiPage

        return WikiPage(
            page_id=row["page_id"],
            project_id=row["project_id"],
            title=row["title"],
            content=row["content"],
            source_document_ids=json.loads(row["source_document_ids"] or "[]"),
            source_chunk_ids=json.loads(row["source_chunk_ids"] or "[]"),
            entity_types=json.loads(row["entity_types"] or "[]"),
            metadata=json.loads(row["metadata"] or "{}"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            created_by=row["created_by"],
            version=row["version"],
        )

    def _row_to_link(self, row: sqlite3.Row) -> WikiLink:
        from homomics_lab.knowledge.wiki.models import WikiLink

        return WikiLink(
            source_id=row["source_id"],
            target_id=row["target_id"],
            relation=row["relation"],
            strength=row["strength"],
            evidence=json.loads(row["evidence"] or "[]"),
            metadata=json.loads(row["metadata"] or "{}"),
        )
