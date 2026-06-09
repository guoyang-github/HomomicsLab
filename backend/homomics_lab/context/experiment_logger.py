"""Experiment logger with timestamped notes and MEMORY.md generation.

Tracks experimental observations, analysis results, and decisions with
automatic Markdown export. Supports hybrid retrieval (time + semantic).

Example:
    logger = ExperimentLogger(project_id="proj_1")
    await logger.record(
        text="QC filtering removed 12% of cells (n=1,200 out of 10,000)",
        tags=["QC", "scanpy", "preprocessing"],
        step="quality_control",
    )
    # Auto-generates /data/projects/proj_1/MEMORY.md
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from homomics_lab.config import settings


class ExperimentLogger:
    """Timestamped experiment note logger with MEMORY.md export.

    Stores notes in SQLite for fast time-based queries, with optional
    semantic indexing via SemanticMemory for content-based retrieval.
    """

    def __init__(
        self,
        project_id: str,
        db_path: Optional[str] = None,
        semantic_memory=None,
    ):
        self.project_id = project_id
        self.semantic_memory = semantic_memory

        if db_path:
            self.db_path = db_path
        else:
            project_dir = settings.data_dir / "projects" / project_id
            project_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = str(project_dir / "experiment.db")

        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _init_db(self) -> None:
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS experiment_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                step TEXT,
                text TEXT NOT NULL,
                tags TEXT NOT NULL DEFAULT '[]',
                metadata TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_notes_project
            ON experiment_notes(project_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_notes_created
            ON experiment_notes(created_at)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_notes_step
            ON experiment_notes(step)
        """)
        conn.commit()

    async def record(
        self,
        text: str,
        step: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Record a timestamped experiment note.

        Args:
            text: The note content (observation, result, decision).
            step: Pipeline step name (e.g., "quality_control").
            tags: List of tags for categorization.
            metadata: Arbitrary JSON data.

        Returns:
            The note ID.
        """
        created_at = datetime.now(timezone.utc).isoformat()
        tags_json = json.dumps(tags or [], ensure_ascii=False)
        meta_json = json.dumps(metadata or {}, ensure_ascii=False)

        conn = self._get_conn()
        cursor = conn.execute(
            """
            INSERT INTO experiment_notes (project_id, step, text, tags, metadata, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (self.project_id, step, text, tags_json, meta_json, created_at),
        )
        conn.commit()
        note_id = cursor.lastrowid

        # Also index in semantic memory if available
        if self.semantic_memory is not None:
            await self.semantic_memory.add(
                text=text,
                memory_type="experiment",
                metadata={
                    "project_id": self.project_id,
                    "note_id": note_id,
                    "step": step,
                    "tags": tags or [],
                },
            )

        return note_id

    async def get(self, note_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve a single note by ID."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM experiment_notes WHERE id = ? AND project_id = ?",
            (note_id, self.project_id),
        ).fetchone()

        if row is None:
            return None

        return self._row_to_dict(row)

    async def list_by_time_range(
        self,
        start: Optional[str] = None,
        end: Optional[str] = None,
        step: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """List notes within a time range, optionally filtered by step.

        Args:
            start: ISO datetime string (inclusive).
            end: ISO datetime string (inclusive).
            step: Filter by pipeline step.
            limit: Maximum results.
        """
        conn = self._get_conn()
        query = "SELECT * FROM experiment_notes WHERE project_id = ?"
        params = [self.project_id]

        if start:
            query += " AND created_at >= ?"
            params.append(start)
        if end:
            query += " AND created_at <= ?"
            params.append(end)
        if step:
            query += " AND step = ?"
            params.append(step)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        return [self._row_to_dict(row) for row in rows]

    async def search_by_tag(self, tag: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Search notes by tag (exact match)."""
        conn = self._get_conn()
        # SQLite JSON1 extension for array containment
        rows = conn.execute(
            """
            SELECT * FROM experiment_notes
            WHERE project_id = ? AND json_extract(tags, '$') LIKE ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (self.project_id, f'%"{tag}"%', limit),
        ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    async def hybrid_search(
        self,
        query: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """Hybrid retrieval: semantic search + time range filtering.

        Requires semantic_memory to be set.
        """
        if self.semantic_memory is None:
            # Fallback to tag search with LIKE
            conn = self._get_conn()
            rows = conn.execute(
                "SELECT * FROM experiment_notes WHERE project_id = ? AND text LIKE ? ORDER BY created_at DESC LIMIT ?",
                (self.project_id, f"%{query}%", top_k),
            ).fetchall()
            return [self._row_to_dict(row) for row in rows]

        # Semantic search
        results = await self.semantic_memory.search(
            query, top_k=top_k * 2, memory_type="experiment"
        )

        # Filter by time range and project
        filtered = []
        for r in results:
            meta = r["metadata"]
            if meta.get("project_id") != self.project_id:
                continue
            created = meta.get("created_at", "")
            if start and created < start:
                continue
            if end and created > end:
                continue
            # Enrich with full note data
            note_id = meta.get("note_id")
            if note_id:
                note = await self.get(note_id)
                if note:
                    note["semantic_score"] = r["score"]
                    filtered.append(note)

        return filtered[:top_k]

    def generate_memory_md(self, output_path: Optional[Path] = None) -> str:
        """Generate MEMORY.md — a human-readable experiment log.

        Args:
            output_path: Where to write the file. Defaults to
                <data_dir>/projects/<project_id>/MEMORY.md

        Returns:
            The generated Markdown content.
        """
        conn = self._get_conn()
        rows = conn.execute(
            """
            SELECT * FROM experiment_notes
            WHERE project_id = ?
            ORDER BY created_at ASC
            """,
            (self.project_id,),
        ).fetchall()

        lines = [
            f"# Experiment Log: {self.project_id}",
            "",
            f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            f"Total entries: {len(rows)}",
            "",
            "---",
            "",
        ]

        current_date = None
        for row in rows:
            note = self._row_to_dict(row)
            dt = datetime.fromisoformat(note["created_at"])
            date_str = dt.strftime("%Y-%m-%d")
            time_str = dt.strftime("%H:%M")

            if date_str != current_date:
                lines.append(f"## {date_str}")
                lines.append("")
                current_date = date_str

            step_tag = f" [{note['step']}]" if note["step"] else ""
            tags_str = ", ".join(f"`{t}`" for t in note["tags"]) if note["tags"] else ""

            lines.append(f"### {time_str}{step_tag}")
            if tags_str:
                lines.append(f"Tags: {tags_str}")
            lines.append("")
            lines.append(note["text"])
            lines.append("")

            # Add metadata if present
            if note["metadata"]:
                meta_items = []
                for k, v in note["metadata"].items():
                    meta_items.append(f"- **{k}**: {v}")
                if meta_items:
                    lines.append("**Metadata:**")
                    lines.extend(meta_items)
                    lines.append("")

            lines.append("---")
            lines.append("")

        content = "\n".join(lines)

        if output_path is None:
            output_path = (
                settings.data_dir / "projects" / self.project_id / "MEMORY.md"
            )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")

        return content

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "id": row["id"],
            "project_id": row["project_id"],
            "step": row["step"],
            "text": row["text"],
            "tags": json.loads(row["tags"]),
            "metadata": json.loads(row["metadata"]),
            "created_at": row["created_at"],
        }

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
