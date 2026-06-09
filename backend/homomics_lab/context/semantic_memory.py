"""Semantic memory using sqlite-vec for vector search.

Stores conversation snippets, task results, experiment records, and notes
as dense embeddings. Enables retrieval of relevant past context by semantic
similarity rather than exact keyword matching.

Example:
    memory = SemanticMemory(db_path="/data/memory.db")
    await memory.add(
        text="QC filtering removed 12% of low-quality cells",
        memory_type="task",
        metadata={"task_id": "qc_1", "skill": "scanpy_qc"},
    )
    results = await memory.search("how many cells were filtered", top_k=3)
"""

import json
import sqlite3
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import sqlite_vec


class MemoryType(str, Enum):
    """Categories of stored memories."""

    CONVERSATION = "conversation"
    """Chat message or conversational turn."""

    TASK = "task"
    """Task execution result or summary."""

    EXPERIMENT = "experiment"
    """Experimental record or protocol."""

    NOTE = "note"
    """Free-form note or observation."""


class SemanticMemory:
    """Vector-backed semantic memory with sqlite-vec.

    Each memory is stored as:
      - id (UUID)
      - text (the searchable content)
      - memory_type (conversation/task/experiment/note)
      - metadata (JSON dict)
      - embedding (384-dim float32 vector for all-MiniLM-L6-v2)
      - created_at (ISO timestamp)
    """

    EMBEDDING_DIM = 384  # all-MiniLM-L6-v2 output dimension
    DEFAULT_MODEL = "all-MiniLM-L6-v2"

    def __init__(
        self,
        db_path: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        self.db_path = db_path or ":memory:"
        self._model_name = model_name or self.DEFAULT_MODEL
        self._model = None
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _get_model(self):
        """Lazy-load sentence-transformers model."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self._model_name)
        return self._model

    def _get_conn(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.enable_load_extension(True)
            sqlite_vec.load(self._conn)
            self._conn.enable_load_extension(False)
        return self._conn

    def _init_db(self) -> None:
        """Create tables if they don't exist."""
        conn = self._get_conn()

        # Main memories table with vector column
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                text TEXT NOT NULL,
                memory_type TEXT NOT NULL,
                metadata TEXT NOT NULL DEFAULT '{{}}',
                embedding FLOAT[{self.EMBEDDING_DIM}],
                created_at TEXT NOT NULL
            )
        """)

        # Index on memory_type for fast filtering
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_memories_type
            ON memories(memory_type)
        """)

        # Index on created_at for time-based queries
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_memories_created
            ON memories(created_at)
        """)

        conn.commit()

    def _embed(self, texts: List[str]) -> List[List[float]]:
        """Encode texts into dense embeddings."""
        model = self._get_model()
        embeddings = model.encode(texts, convert_to_tensor=False)
        # Normalize to unit vectors for cosine similarity
        import numpy as np

        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1  # avoid division by zero
        normalized = embeddings / norms
        return normalized.tolist()

    async def add(
        self,
        text: str,
        memory_type: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Add a memory to the semantic store.

        Args:
            text: The searchable content.
            memory_type: One of conversation/task/experiment/note.
            metadata: Arbitrary JSON-serializable dict.

        Returns:
            The generated memory ID.
        """
        import uuid
        from datetime import datetime, timezone

        memory_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        meta_json = json.dumps(metadata or {}, ensure_ascii=False)

        # Generate embedding
        embedding = self._embed([text])[0]

        conn = self._get_conn()
        conn.execute(
            """
            INSERT INTO memories (id, text, memory_type, metadata, embedding, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (memory_id, text, memory_type, meta_json, json.dumps(embedding), created_at),
        )
        conn.commit()

        return memory_id

    async def search(
        self,
        query: str,
        top_k: int = 5,
        memory_type: Optional[str] = None,
        min_score: float = 0.15,
    ) -> List[Dict[str, Any]]:
        """Search memories by semantic similarity.

        Args:
            query: Natural language query.
            top_k: Maximum number of results.
            memory_type: Optional filter by memory type.
            min_score: Minimum cosine similarity threshold.

        Returns:
            List of result dicts with keys: id, text, memory_type,
            metadata, score, created_at.
        """
        query_embedding = self._embed([query])[0]

        conn = self._get_conn()

        if memory_type:
            rows = conn.execute(
                """
                SELECT
                    id,
                    text,
                    memory_type,
                    metadata,
                    created_at,
                    vec_distance_cosine(embedding, ?) AS distance
                FROM memories
                WHERE memory_type = ?
                ORDER BY distance
                LIMIT ?
                """,
                (json.dumps(query_embedding), memory_type, top_k * 2),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT
                    id,
                    text,
                    memory_type,
                    metadata,
                    created_at,
                    vec_distance_cosine(embedding, ?) AS distance
                FROM memories
                ORDER BY distance
                LIMIT ?
                """,
                (json.dumps(query_embedding), top_k * 2),
            ).fetchall()

        results = []
        for row in rows:
            memory_id, text, mtype, meta_json, created_at, distance = row
            # sqlite-vec cosine distance = 1 - cosine_similarity
            score = 1.0 - float(distance)
            if score >= min_score:
                results.append({
                    "id": memory_id,
                    "text": text,
                    "memory_type": mtype,
                    "metadata": json.loads(meta_json),
                    "score": round(score, 4),
                    "created_at": created_at,
                })

        return results[:top_k]

    async def get(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a single memory by ID."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT id, text, memory_type, metadata, created_at FROM memories WHERE id = ?",
            (memory_id,),
        ).fetchone()

        if row is None:
            return None

        return {
            "id": row[0],
            "text": row[1],
            "memory_type": row[2],
            "metadata": json.loads(row[3]),
            "created_at": row[4],
        }

    async def delete(self, memory_id: str) -> bool:
        """Delete a memory by ID.

        Returns:
            True if a row was deleted, False if not found.
        """
        conn = self._get_conn()
        cursor = conn.execute(
            "DELETE FROM memories WHERE id = ?", (memory_id,)
        )
        conn.commit()
        return cursor.rowcount > 0

    async def list_by_type(
        self,
        memory_type: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List memories of a given type, ordered by recency."""
        conn = self._get_conn()
        rows = conn.execute(
            """
            SELECT id, text, memory_type, metadata, created_at
            FROM memories
            WHERE memory_type = ?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (memory_type, limit, offset),
        ).fetchall()

        return [
            {
                "id": row[0],
                "text": row[1],
                "memory_type": row[2],
                "metadata": json.loads(row[3]),
                "created_at": row[4],
            }
            for row in rows
        ]

    async def count(self, memory_type: Optional[str] = None) -> int:
        """Count total memories, optionally filtered by type."""
        conn = self._get_conn()
        if memory_type:
            row = conn.execute(
                "SELECT COUNT(*) FROM memories WHERE memory_type = ?",
                (memory_type,),
            ).fetchone()
        else:
            row = conn.execute("SELECT COUNT(*) FROM memories").fetchone()
        return row[0]

    def close(self) -> None:
        """Close database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
