"""Semantic memory with pluggable SQLite (sqlite-vec + FTS5) or PostgreSQL/pgvector backends.

Stores conversation snippets, task results, experiment records, and notes as dense
embeddings. Enables retrieval of relevant past context by semantic similarity rather
than exact keyword matching.

Example:
    from homomics_lab.context.semantic_memory import create_semantic_memory
    from homomics_lab.config import settings

    memory = create_semantic_memory(settings)
    if memory:
        await memory.add(
            text="QC filtering removed 12% of low-quality cells",
            memory_type="task",
            metadata={"task_id": "qc_1", "skill": "example_skill"},
        )
        results = await memory.search("how many cells were filtered", top_k=3)
"""

import json
import sqlite3
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

import sqlite_vec

from homomics_lab.config import Settings
from homomics_lab.context.embedding_cache import get_shared_embedding_model


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

    PREFERENCE = "preference"
    """Explicit user preference."""

    CONCEPT = "concept"
    """Consolidated concept or episode summary."""


class BaseSemanticMemory(ABC):
    """Abstract interface for vector-backed semantic memory.

    Each memory is stored as:
      - id (UUID)
      - text (the searchable content)
      - memory_type (conversation/task/experiment/note/preference/concept)
      - metadata (JSON dict)
      - embedding (384-dim float32 vector for all-MiniLM-L6-v2)
      - importance (0-1 retention score)
      - ttl_days (optional expiration window)
      - project_id (structured scope column)
      - session_id (structured scope column)
      - created_at (ISO timestamp)
      - last_accessed (ISO timestamp)
    """

    EMBEDDING_DIM = 384  # all-MiniLM-L6-v2 output dimension
    DEFAULT_MODEL = "all-MiniLM-L6-v2"
    RRF_K = 60

    def __init__(self, model_name: Optional[str] = None):
        self._model_name = model_name or self.DEFAULT_MODEL

    def _embed(self, texts: List[str]) -> List[List[float]]:
        """Encode texts into dense embeddings using the shared model."""
        model = get_shared_embedding_model(self._model_name)
        return model.encode(texts)

    @abstractmethod
    async def add(
        self,
        text: str,
        memory_type: str,
        metadata: Optional[Dict[str, Any]] = None,
        importance: float = 0.5,
        ttl_days: Optional[int] = None,
        project_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> str:
        """Add a memory to the semantic store."""

    @abstractmethod
    async def search(
        self,
        query: str,
        top_k: int = 5,
        memory_type: Optional[str] = None,
        min_score: float = 0.15,
        project_id: Optional[str] = None,
        session_id: Optional[str] = None,
        hybrid: bool = True,
    ) -> List[Dict[str, Any]]:
        """Search memories by semantic similarity with optional hybrid fusion."""

    @abstractmethod
    async def get(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a single memory by ID."""

    @abstractmethod
    async def delete(self, memory_id: str) -> bool:
        """Delete a memory by ID."""

    @abstractmethod
    async def list_by_type(
        self,
        memory_type: str,
        limit: int = 100,
        offset: int = 0,
        project_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List memories of a given type, ordered by recency."""

    @abstractmethod
    async def count(
        self,
        memory_type: Optional[str] = None,
        project_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> int:
        """Count total memories, optionally filtered by type/scope."""

    @abstractmethod
    async def prune_stale_memories(
        self,
        retention_days: int = 30,
        low_importance_threshold: float = 0.3,
    ) -> int:
        """Remove expired or low-importance stale memories."""

    @abstractmethod
    async def consolidate_conversation_chunks(
        self,
        session_id: Optional[str] = None,
        chunk_size: int = 5,
        project_id: Optional[str] = None,
    ) -> int:
        """Merge adjacent conversation memories into summary chunks."""

    @abstractmethod
    async def close(self) -> None:
        """Close database connection(s)."""


class SQLiteSemanticMemory(BaseSemanticMemory):
    """Vector-backed semantic memory with sqlite-vec and FTS5 hybrid search."""

    def __init__(
        self,
        db_path: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        super().__init__(model_name=model_name)
        self.db_path = db_path or ":memory:"
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
                importance REAL NOT NULL DEFAULT 0.5,
                ttl_days INTEGER,
                project_id TEXT,
                session_id TEXT,
                created_at TEXT NOT NULL,
                last_accessed TEXT
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

        # Structured scope indexes
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_memories_project
            ON memories(project_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_memories_session
            ON memories(session_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_memories_project_session_created
            ON memories(project_id, session_id, created_at)
        """)

        # Lightweight migration for legacy tables.
        try:
            cols = {row[1] for row in conn.execute("PRAGMA table_info(memories)")}
            if "importance" not in cols:
                conn.execute("ALTER TABLE memories ADD COLUMN importance REAL NOT NULL DEFAULT 0.5")
            if "ttl_days" not in cols:
                conn.execute("ALTER TABLE memories ADD COLUMN ttl_days INTEGER")
            if "last_accessed" not in cols:
                conn.execute("ALTER TABLE memories ADD COLUMN last_accessed TEXT")
            if "project_id" not in cols:
                conn.execute("ALTER TABLE memories ADD COLUMN project_id TEXT")
            if "session_id" not in cols:
                conn.execute("ALTER TABLE memories ADD COLUMN session_id TEXT")

            # Backfill structured scope columns from JSON metadata.
            conn.execute("""
                UPDATE memories
                SET project_id = json_extract(metadata, '$.project_id')
                WHERE project_id IS NULL AND json_extract(metadata, '$.project_id') IS NOT NULL
            """)
            conn.execute("""
                UPDATE memories
                SET session_id = json_extract(metadata, '$.session_id')
                WHERE session_id IS NULL AND json_extract(metadata, '$.session_id') IS NOT NULL
            """)
        except Exception:
            pass

        # FTS5 external content table for hybrid search.
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                text,
                content='memories',
                content_rowid='rowid'
            )
        """)

        # Backfill FTS index for existing rows.
        try:
            existing = conn.execute("SELECT COUNT(*) FROM memories_fts").fetchone()[0]
            total = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
            if existing == 0 and total > 0:
                conn.execute("""
                    INSERT INTO memories_fts(rowid, text)
                    SELECT rowid, text FROM memories
                """)
        except Exception:
            pass

        conn.commit()

    def _fts_insert(self, rowid: int, text: str) -> None:
        """Insert a row into the FTS5 index."""
        conn = self._get_conn()
        conn.execute("INSERT INTO memories_fts(rowid, text) VALUES (?, ?)", (rowid, text))

    def _fts_delete_by_memory_ids(self, memory_ids: List[str]) -> None:
        """Remove rows from the FTS5 index by memory IDs."""
        if not memory_ids:
            return
        conn = self._get_conn()
        placeholders = ",".join("?" for _ in memory_ids)
        conn.execute(
            f"DELETE FROM memories_fts WHERE rowid IN (SELECT rowid FROM memories WHERE id IN ({placeholders}))",
            memory_ids,
        )

    async def add(
        self,
        text: str,
        memory_type: str,
        metadata: Optional[Dict[str, Any]] = None,
        importance: float = 0.5,
        ttl_days: Optional[int] = None,
        project_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> str:
        """Add a memory to the semantic store."""
        memory_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        meta = metadata or {}
        if project_id is not None:
            meta["project_id"] = project_id
        if session_id is not None:
            meta["session_id"] = session_id
        # Derive scope from metadata if not passed explicitly.
        project_id = project_id or meta.get("project_id")
        session_id = session_id or meta.get("session_id")
        meta_json = json.dumps(meta, ensure_ascii=False)

        # Generate embedding
        embedding = self._embed([text])[0]

        conn = self._get_conn()
        cursor = conn.execute(
            """
            INSERT INTO memories (
                id, text, memory_type, metadata, embedding, importance, ttl_days,
                project_id, session_id, created_at, last_accessed
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                memory_id,
                text,
                memory_type,
                meta_json,
                json.dumps(embedding),
                importance,
                ttl_days,
                project_id,
                session_id,
                created_at,
                created_at,
            ),
        )
        self._fts_insert(cursor.lastrowid, text)
        conn.commit()

        return memory_id

    async def search(
        self,
        query: str,
        top_k: int = 5,
        memory_type: Optional[str] = None,
        min_score: float = 0.15,
        project_id: Optional[str] = None,
        session_id: Optional[str] = None,
        hybrid: bool = True,
    ) -> List[Dict[str, Any]]:
        """Search memories by semantic similarity with optional FTS hybrid fusion."""
        if not query.strip():
            return []

        conn = self._get_conn()
        limit = max(top_k * 2, 10)

        def _apply_filters(sql_list: List[str], sql_params: List[Any]) -> None:
            if memory_type is not None:
                sql_list.append("memory_type = ?")
                sql_params.append(memory_type)
            if project_id is not None:
                sql_list.append("project_id = ?")
                sql_params.append(project_id)
            if session_id is not None:
                sql_list.append("session_id = ?")
                sql_params.append(session_id)

        # Dense vector search
        query_embedding = self._embed([query])[0]
        dense_where = []
        dense_params: List[Any] = [json.dumps(query_embedding)]
        _apply_filters(dense_where, dense_params)
        where_clause = "WHERE " + " AND ".join(dense_where) if dense_where else ""
        dense_rows = conn.execute(
            f"""
            SELECT
                id,
                text,
                memory_type,
                metadata,
                created_at,
                vec_distance_cosine(embedding, ?) AS distance
            FROM memories
            {where_clause}
            ORDER BY distance
            LIMIT ?
            """,
            (*dense_params, limit),
        ).fetchall()

        dense_results: Dict[str, Dict[str, Any]] = {}
        for rank, row in enumerate(dense_rows):
            memory_id, text, mtype, meta_json, created_at, distance = row
            score = 1.0 - float(distance)
            if score >= min_score:
                dense_results[memory_id] = {
                    "id": memory_id,
                    "text": text,
                    "memory_type": mtype,
                    "metadata": json.loads(meta_json),
                    "score": score,
                    "created_at": created_at,
                    "_dense_rank": rank + 1,
                }

        # FTS search
        fts_results: Dict[str, Dict[str, Any]] = {}
        if hybrid:
            fts_where = ["memories_fts MATCH ?"]
            fts_params: List[Any] = [query]
            _apply_filters(fts_where, fts_params)
            # Filters apply to the content table joined via rowid.
            fts_where_sql = "WHERE " + " AND ".join(fts_where) if fts_where else ""
            fts_rows = conn.execute(
                f"""
                SELECT
                    memories.id,
                    memories.text,
                    memories.memory_type,
                    memories.metadata,
                    memories.created_at,
                    rank
                FROM memories_fts
                JOIN memories ON memories.rowid = memories_fts.rowid
                {fts_where_sql}
                ORDER BY rank
                LIMIT ?
                """,
                (*fts_params, limit),
            ).fetchall()
            for rank, row in enumerate(fts_rows):
                memory_id, text, mtype, meta_json, created_at, _rank = row
                fts_results[memory_id] = {
                    "id": memory_id,
                    "text": text,
                    "memory_type": mtype,
                    "metadata": json.loads(meta_json),
                    "score": 0.0,
                    "created_at": created_at,
                    "_fts_rank": rank + 1,
                }

        # RRF fusion
        all_ids = set(dense_results) | set(fts_results)
        fused: List[Dict[str, Any]] = []
        for memory_id in all_ids:
            rrf_score = 0.0
            if memory_id in dense_results:
                rrf_score += 1.0 / (self.RRF_K + dense_results[memory_id]["_dense_rank"])
            if memory_id in fts_results:
                rrf_score += 1.0 / (self.RRF_K + fts_results[memory_id]["_fts_rank"])
            # Prefer dense result payload but enrich with FTS if missing.
            payload = dense_results.get(memory_id) or fts_results.get(memory_id)
            payload = {**payload, "score": round(rrf_score, 6)}
            payload.pop("_dense_rank", None)
            payload.pop("_fts_rank", None)
            fused.append(payload)

        fused.sort(key=lambda r: r["score"], reverse=True)
        results = fused[:top_k]

        if results:
            self._touch([r["id"] for r in results])
        return results

    async def get(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a single memory by ID."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT id, text, memory_type, metadata, created_at FROM memories WHERE id = ?",
            (memory_id,),
        ).fetchone()

        if row is None:
            return None

        self._touch([memory_id])
        return {
            "id": row[0],
            "text": row[1],
            "memory_type": row[2],
            "metadata": json.loads(row[3]),
            "created_at": row[4],
        }

    async def delete(self, memory_id: str) -> bool:
        """Delete a memory by ID."""
        conn = self._get_conn()
        self._fts_delete_by_memory_ids([memory_id])
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
        project_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List memories of a given type, ordered by recency."""
        conn = self._get_conn()
        filters = ["memory_type = ?"]
        params: List[Any] = [memory_type]
        if project_id is not None:
            filters.append("project_id = ?")
            params.append(project_id)
        if session_id is not None:
            filters.append("session_id = ?")
            params.append(session_id)
        where = "WHERE " + " AND ".join(filters)
        rows = conn.execute(
            f"""
            SELECT id, text, memory_type, metadata, created_at
            FROM memories
            {where}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (*params, limit, offset),
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

    async def count(
        self,
        memory_type: Optional[str] = None,
        project_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> int:
        """Count total memories, optionally filtered by type/scope."""
        conn = self._get_conn()
        filters: List[str] = []
        params: List[Any] = []
        if memory_type is not None:
            filters.append("memory_type = ?")
            params.append(memory_type)
        if project_id is not None:
            filters.append("project_id = ?")
            params.append(project_id)
        if session_id is not None:
            filters.append("session_id = ?")
            params.append(session_id)
        where = "WHERE " + " AND ".join(filters) if filters else ""
        row = conn.execute(
            f"SELECT COUNT(*) FROM memories {where}",
            params,
        ).fetchone()
        return row[0]

    def _touch(self, memory_ids: List[str]) -> None:
        """Update last_accessed for the given memory IDs."""
        if not memory_ids:
            return
        now = datetime.now(timezone.utc).isoformat()
        conn = self._get_conn()
        placeholders = ",".join("?" for _ in memory_ids)
        conn.execute(
            f"UPDATE memories SET last_accessed = ? WHERE id IN ({placeholders})",
            (now, *memory_ids),
        )
        conn.commit()

    async def prune_stale_memories(
        self,
        retention_days: int = 30,
        low_importance_threshold: float = 0.3,
    ) -> int:
        """Remove expired or low-importance stale memories."""
        conn = self._get_conn()
        try:
            # Find candidate IDs first so we can clean the FTS index.
            ids = [
                row[0]
                for row in conn.execute(
                    """
                    SELECT id FROM memories
                    WHERE
                        (ttl_days IS NOT NULL AND date(created_at) <= date('now', '-' || ttl_days || ' days'))
                        OR (
                            importance < ?
                            AND (
                                last_accessed IS NULL
                                OR date(last_accessed) <= date('now', '-' || ? || ' days')
                            )
                            AND date(created_at) <= date('now', '-' || ? || ' days')
                        )
                    """,
                    (low_importance_threshold, retention_days, retention_days),
                ).fetchall()
            ]
            if not ids:
                return 0
            self._fts_delete_by_memory_ids(ids)
            placeholders = ",".join("?" for _ in ids)
            cursor = conn.execute(
                f"DELETE FROM memories WHERE id IN ({placeholders})",
                ids,
            )
            conn.commit()
            return cursor.rowcount
        except Exception:
            conn.rollback()
            raise

    async def consolidate_conversation_chunks(
        self,
        session_id: Optional[str] = None,
        chunk_size: int = 5,
        project_id: Optional[str] = None,
    ) -> int:
        """Merge adjacent conversation memories into summary chunks."""
        if chunk_size < 2:
            return 0

        conn = self._get_conn()
        filters = ["memory_type = ?"]
        params: List[Any] = ["conversation"]
        if session_id is not None:
            filters.append("session_id = ?")
            params.append(session_id)
        if project_id is not None:
            filters.append("project_id = ?")
            params.append(project_id)
        where_sql = "WHERE " + " AND ".join(filters)

        rows = conn.execute(
            f"""
            SELECT id, text, metadata, importance, ttl_days, created_at, project_id, session_id
            FROM memories
            {where_sql}
            ORDER BY created_at ASC
            """,
            params,
        ).fetchall()

        def _session_key(row) -> Optional[str]:
            return row[7]

        groups: List[List[tuple]] = []
        current_group: List[tuple] = []
        current_key: Optional[str] = None
        for row in rows:
            key = _session_key(row)
            if key != current_key or len(current_group) >= chunk_size:
                if len(current_group) >= chunk_size:
                    groups.append(current_group)
                current_group = [row]
                current_key = key
            else:
                current_group.append(row)
        if len(current_group) >= chunk_size:
            groups.append(current_group)

        if not groups:
            return 0

        now = datetime.now(timezone.utc).isoformat()
        try:
            for group in groups:
                ids = [r[0] for r in group]
                merged_text = "\n\n".join(f"[{r[5]}] {r[1]}" for r in group)
                importances = [r[3] for r in group if r[3] is not None]
                merged_importance = sum(importances) / len(importances) if importances else 0.5
                ttl_days = group[0][4]
                meta = json.loads(group[0][2])
                merged_meta = {
                    **meta,
                    "consolidated": True,
                    "source_ids": ids,
                    "original_count": len(group),
                }
                merged_embedding = self._embed([merged_text])[0]
                cursor = conn.execute(
                    """
                    INSERT INTO memories (
                        id, text, memory_type, metadata, embedding, importance, ttl_days,
                        project_id, session_id, created_at, last_accessed
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        merged_text,
                        "conversation",
                        json.dumps(merged_meta),
                        json.dumps(merged_embedding),
                        merged_importance,
                        ttl_days,
                        group[0][6],
                        group[0][7],
                        group[0][5],
                        now,
                    ),
                )
                self._fts_insert(cursor.lastrowid, merged_text)
                self._fts_delete_by_memory_ids(ids)
                placeholders = ",".join("?" for _ in ids)
                conn.execute(
                    f"DELETE FROM memories WHERE id IN ({placeholders})",
                    ids,
                )
            conn.commit()
            return len(groups)
        except Exception:
            conn.rollback()
            raise

    async def close(self) -> None:
        """Close database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None


class PostgresSemanticMemory(BaseSemanticMemory):
    """PostgreSQL/pgvector backed semantic memory with dense + full-text hybrid search."""

    def __init__(
        self,
        postgres_url: str,
        model_name: Optional[str] = None,
    ):
        super().__init__(model_name=model_name)
        self._postgres_url = self._normalize_postgres_url(postgres_url)
        self._pool: Optional[Any] = None
        self._pgvector_available: bool = False
        self._embedding_type: str = "vector"

    @staticmethod
    def _normalize_postgres_url(url: str) -> str:
        """Convert SQLAlchemy-style asyncpg URLs to plain asyncpg DSN."""
        url = url.strip()
        if url.startswith("postgresql+asyncpg://"):
            return "postgresql://" + url.split("://", 1)[1]
        if url.startswith("postgres://"):
            return "postgresql://" + url.split("://", 1)[1]
        return url

    @staticmethod
    def _fmt_ts(value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        return value.isoformat()

    async def _get_pool(self) -> Any:
        """Get or create the asyncpg connection pool."""
        if self._pool is None:
            import asyncpg

            self._pool = await asyncpg.create_pool(self._postgres_url, min_size=1, max_size=5)
            await self._init_db()
        return self._pool

    async def _init_db(self) -> None:
        """Create tables and indexes; set pgvector availability flag."""
        import asyncpg

        pool = self._pool
        if pool is None:
            raise RuntimeError("Pool not initialized")

        async with pool.acquire() as conn:
            # Try to enable pgvector extension.
            try:
                await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
                self._pgvector_available = True
            except (asyncpg.InsufficientPrivilegeError, asyncpg.UndefinedObjectError):
                # Permission denied or extension not available. Check if vector type exists.
                row = await conn.fetchrow(
                    "SELECT 1 FROM pg_type WHERE typname = 'vector'"
                )
                self._pgvector_available = row is not None
            except Exception:
                row = await conn.fetchrow(
                    "SELECT 1 FROM pg_type WHERE typname = 'vector'"
                )
                self._pgvector_available = row is not None

            if not self._pgvector_available:
                raise RuntimeError(
                    "PostgreSQL semantic memory backend requires the pgvector extension. "
                    "Install it and ensure the 'vector' type is available."
                )

            # Register pgvector type support.
            from pgvector.asyncpg import register_vector

            await register_vector(conn)

            embedding_col = f"embedding vector({self.EMBEDDING_DIM})"

            await conn.execute(f"""
                CREATE TABLE IF NOT EXISTS memories (
                    id UUID PRIMARY KEY,
                    text TEXT NOT NULL,
                    memory_type TEXT NOT NULL,
                    metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                    {embedding_col},
                    importance REAL NOT NULL DEFAULT 0.5,
                    ttl_days INTEGER,
                    project_id TEXT,
                    session_id TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    last_accessed TIMESTAMPTZ
                )
            """)

            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_memories_type
                ON memories(memory_type)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_memories_created
                ON memories(created_at)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_memories_project
                ON memories(project_id)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_memories_session
                ON memories(session_id)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_memories_project_session_created
                ON memories(project_id, session_id, created_at)
            """)

            # Full-text search index.
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_memories_fts
                ON memories USING GIN (to_tsvector('simple', text))
            """)

            # Vector search index (HNSW preferred, fall back to IVFFlat).
            if self._pgvector_available:
                try:
                    await conn.execute("""
                        CREATE INDEX IF NOT EXISTS idx_memories_embedding_hnsw
                        ON memories USING hnsw (embedding vector_cosine_ops)
                        WITH (m = 16, ef_construction = 64)
                    """)
                except Exception:
                    try:
                        await conn.execute(f"""
                            CREATE INDEX IF NOT EXISTS idx_memories_embedding_ivfflat
                            ON memories USING ivfflat (embedding vector_cosine_ops)
                            WITH (lists = 100)
                        """)
                    except Exception:
                        pass

    @staticmethod
    def _apply_filters(
        conditions: List[str],
        params: List[Any],
        memory_type: Optional[str] = None,
        project_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> None:
        if memory_type is not None:
            conditions.append("memory_type = $" + str(len(params) + 1))
            params.append(memory_type)
        if project_id is not None:
            conditions.append("project_id = $" + str(len(params) + 1))
            params.append(project_id)
        if session_id is not None:
            conditions.append("session_id = $" + str(len(params) + 1))
            params.append(session_id)

    async def add(
        self,
        text: str,
        memory_type: str,
        metadata: Optional[Dict[str, Any]] = None,
        importance: float = 0.5,
        ttl_days: Optional[int] = None,
        project_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> str:
        """Add a memory to the semantic store."""
        memory_id = uuid.uuid4()
        created_at = datetime.now(timezone.utc)
        meta = metadata or {}
        if project_id is not None:
            meta["project_id"] = project_id
        if session_id is not None:
            meta["session_id"] = session_id
        project_id = project_id or meta.get("project_id")
        session_id = session_id or meta.get("session_id")

        embedding = self._embed([text])[0]

        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO memories (
                    id, text, memory_type, metadata, embedding, importance, ttl_days,
                    project_id, session_id, created_at, last_accessed
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                """,
                memory_id,
                text,
                memory_type,
                json.dumps(meta, ensure_ascii=False),
                embedding,
                importance,
                ttl_days,
                project_id,
                session_id,
                created_at,
                created_at,
            )
        return str(memory_id)

    async def search(
        self,
        query: str,
        top_k: int = 5,
        memory_type: Optional[str] = None,
        min_score: float = 0.15,
        project_id: Optional[str] = None,
        session_id: Optional[str] = None,
        hybrid: bool = True,
    ) -> List[Dict[str, Any]]:
        """Search memories by semantic similarity with optional full-text hybrid fusion."""
        if not query.strip():
            return []

        query_embedding = self._embed([query])[0]
        limit = max(top_k * 2, 10)

        pool = await self._get_pool()
        async with pool.acquire() as conn:
            # Dense vector search
            dense_conditions: List[str] = []
            dense_params: List[Any] = [query_embedding]
            self._apply_filters(
                dense_conditions, dense_params, memory_type, project_id, session_id
            )
            dense_where = (
                "WHERE " + " AND ".join(dense_conditions)
                if dense_conditions
                else ""
            )
            dense_rows = await conn.fetch(
                f"""
                SELECT
                    id,
                    text,
                    memory_type,
                    metadata,
                    created_at,
                    1 - (embedding <=> $1) AS score
                FROM memories
                {dense_where}
                ORDER BY embedding <=> $1
                LIMIT ${len(dense_params) + 1}
                """,
                *dense_params,
                limit,
            )

            dense_results: Dict[str, Dict[str, Any]] = {}
            for rank, row in enumerate(dense_rows):
                score = float(row["score"])
                if score >= min_score:
                    dense_results[str(row["id"])] = {
                        "id": str(row["id"]),
                        "text": row["text"],
                        "memory_type": row["memory_type"],
                        "metadata": json.loads(row["metadata"]),
                        "score": score,
                        "created_at": self._fmt_ts(row["created_at"]),
                        "_dense_rank": rank + 1,
                    }

            # Full-text search
            fts_results: Dict[str, Dict[str, Any]] = {}
            if hybrid:
                fts_conditions: List[str] = [
                    "to_tsvector('simple', text) @@ plainto_tsquery('simple', $1)"
                ]
                fts_params: List[Any] = [query]
                self._apply_filters(
                    fts_conditions, fts_params, memory_type, project_id, session_id
                )
                fts_where = "WHERE " + " AND ".join(fts_conditions)
                fts_rows = await conn.fetch(
                    f"""
                    SELECT
                        id,
                        text,
                        memory_type,
                        metadata,
                        created_at,
                        ts_rank_cd(to_tsvector('simple', text), plainto_tsquery('simple', $1)) AS rank
                    FROM memories
                    {fts_where}
                    ORDER BY rank DESC
                    LIMIT ${len(fts_params) + 1}
                    """,
                    *fts_params,
                    limit,
                )
                for rank, row in enumerate(fts_rows):
                    fts_results[str(row["id"])] = {
                        "id": str(row["id"]),
                        "text": row["text"],
                        "memory_type": row["memory_type"],
                        "metadata": json.loads(row["metadata"]),
                        "score": 0.0,
                        "created_at": self._fmt_ts(row["created_at"]),
                        "_fts_rank": rank + 1,
                    }

        # RRF fusion
        all_ids = set(dense_results) | set(fts_results)
        fused: List[Dict[str, Any]] = []
        for memory_id in all_ids:
            rrf_score = 0.0
            if memory_id in dense_results:
                rrf_score += 1.0 / (self.RRF_K + dense_results[memory_id]["_dense_rank"])
            if memory_id in fts_results:
                rrf_score += 1.0 / (self.RRF_K + fts_results[memory_id]["_fts_rank"])
            payload = dense_results.get(memory_id) or fts_results.get(memory_id)
            payload = {**payload, "score": round(rrf_score, 6)}
            payload.pop("_dense_rank", None)
            payload.pop("_fts_rank", None)
            fused.append(payload)

        fused.sort(key=lambda r: r["score"], reverse=True)
        results = fused[:top_k]

        if results:
            await self._touch([r["id"] for r in results])
        return results

    async def get(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a single memory by ID."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, text, memory_type, metadata, created_at FROM memories WHERE id = $1",
                uuid.UUID(memory_id),
            )

        if row is None:
            return None

        await self._touch([memory_id])
        return {
            "id": str(row["id"]),
            "text": row["text"],
            "memory_type": row["memory_type"],
            "metadata": json.loads(row["metadata"]),
            "created_at": self._fmt_ts(row["created_at"]),
        }

    async def delete(self, memory_id: str) -> bool:
        """Delete a memory by ID."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM memories WHERE id = $1",
                uuid.UUID(memory_id),
            )
        # asyncpg DELETE returns 'DELETE <n>'
        return result.startswith("DELETE") and int(result.split()[1]) > 0

    async def list_by_type(
        self,
        memory_type: str,
        limit: int = 100,
        offset: int = 0,
        project_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List memories of a given type, ordered by recency."""
        conditions = ["memory_type = $1"]
        params: List[Any] = [memory_type]
        self._apply_filters(conditions, params, None, project_id, session_id)
        where = "WHERE " + " AND ".join(conditions)

        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT id, text, memory_type, metadata, created_at
                FROM memories
                {where}
                ORDER BY created_at DESC
                LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}
                """,
                *params,
                limit,
                offset,
            )

        return [
            {
                "id": str(row["id"]),
                "text": row["text"],
                "memory_type": row["memory_type"],
                "metadata": json.loads(row["metadata"]),
                "created_at": self._fmt_ts(row["created_at"]),
            }
            for row in rows
        ]

    async def count(
        self,
        memory_type: Optional[str] = None,
        project_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> int:
        """Count total memories, optionally filtered by type/scope."""
        conditions: List[str] = []
        params: List[Any] = []
        self._apply_filters(conditions, params, memory_type, project_id, session_id)
        where = "WHERE " + " AND ".join(conditions) if conditions else ""

        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT COUNT(*) FROM memories {where}",
                *params,
            )
        return row[0] if row else 0

    async def _touch(self, memory_ids: List[str]) -> None:
        """Update last_accessed for the given memory IDs."""
        if not memory_ids:
            return
        now = datetime.now(timezone.utc)
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE memories SET last_accessed = $1 WHERE id = ANY($2::uuid[])
                """,
                now,
                [uuid.UUID(mid) for mid in memory_ids],
            )

    async def prune_stale_memories(
        self,
        retention_days: int = 30,
        low_importance_threshold: float = 0.3,
    ) -> int:
        """Remove expired or low-importance stale memories."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                """
                DELETE FROM memories
                WHERE
                    (ttl_days IS NOT NULL AND created_at <= NOW() - INTERVAL '1 day' * ttl_days)
                    OR (
                        importance < $1
                        AND (
                            last_accessed IS NULL
                            OR last_accessed <= NOW() - INTERVAL '1 day' * $2
                        )
                        AND created_at <= NOW() - INTERVAL '1 day' * $2
                    )
                """,
                low_importance_threshold,
                retention_days,
            )
        return int(result.split()[1]) if result.startswith("DELETE") else 0

    async def consolidate_conversation_chunks(
        self,
        session_id: Optional[str] = None,
        chunk_size: int = 5,
        project_id: Optional[str] = None,
    ) -> int:
        """Merge adjacent conversation memories into summary chunks."""
        if chunk_size < 2:
            return 0

        pool = await self._get_pool()
        async with pool.acquire() as conn:
            conditions = ["memory_type = $1"]
            params: List[Any] = ["conversation"]
            self._apply_filters(conditions, params, None, project_id, session_id)
            where = "WHERE " + " AND ".join(conditions)
            rows = await conn.fetch(
                f"""
                SELECT id, text, metadata, importance, ttl_days, created_at, project_id, session_id
                FROM memories
                {where}
                ORDER BY created_at ASC
                """,
                *params,
            )

        def _session_key(row) -> Optional[str]:
            return row["session_id"]

        groups: List[List[Any]] = []
        current_group: List[Any] = []
        current_key: Optional[str] = None
        for row in rows:
            key = _session_key(row)
            if key != current_key or len(current_group) >= chunk_size:
                if len(current_group) >= chunk_size:
                    groups.append(current_group)
                current_group = [row]
                current_key = key
            else:
                current_group.append(row)
        if len(current_group) >= chunk_size:
            groups.append(current_group)

        if not groups:
            return 0

        now = datetime.now(timezone.utc)
        async with pool.acquire() as conn:
            async with conn.transaction():
                for group in groups:
                    ids = [r["id"] for r in group]
                    merged_text = "\n\n".join(
                        f"[{r['created_at']}] {r['text']}" for r in group
                    )
                    importances = [r["importance"] for r in group if r["importance"] is not None]
                    merged_importance = sum(importances) / len(importances) if importances else 0.5
                    ttl_days = group[0]["ttl_days"]
                    meta = json.loads(group[0]["metadata"])
                    merged_meta = {
                        **meta,
                        "consolidated": True,
                        "source_ids": [str(i) for i in ids],
                        "original_count": len(group),
                    }
                    merged_embedding = self._embed([merged_text])[0]
                    await conn.execute(
                        """
                        INSERT INTO memories (
                            id, text, memory_type, metadata, embedding, importance, ttl_days,
                            project_id, session_id, created_at, last_accessed
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                        """,
                        uuid.uuid4(),
                        merged_text,
                        "conversation",
                        json.dumps(merged_meta, ensure_ascii=False),
                        merged_embedding,
                        merged_importance,
                        ttl_days,
                        group[0]["project_id"],
                        group[0]["session_id"],
                        group[0]["created_at"],
                        now,
                    )
                    await conn.execute(
                        "DELETE FROM memories WHERE id = ANY($1::uuid[])",
                        ids,
                    )
        return len(groups)

    async def close(self) -> None:
        """Close the asyncpg connection pool."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None


# Backward-compatible alias: code that imports SemanticMemory gets the SQLite backend.
SemanticMemory = SQLiteSemanticMemory


def create_semantic_memory(settings: Settings) -> Optional[BaseSemanticMemory]:
    """Factory that creates the configured semantic memory backend.

    Returns None when semantic memory is disabled or no embedding model is set.
    """
    if not settings.enable_semantic_memory or not settings.semantic_search_model:
        return None

    if settings.semantic_memory_backend == "postgres":
        postgres_url = settings.semantic_memory_postgres_url
        if not postgres_url:
            db_url = settings.database_url
            if db_url.startswith(("postgresql+asyncpg://", "postgresql://", "postgres://")):
                postgres_url = db_url
        if not postgres_url:
            raise ValueError(
                "semantic_memory_postgres_url must be set when semantic_memory_backend=postgres"
            )
        return PostgresSemanticMemory(
            postgres_url=postgres_url,
            model_name=settings.semantic_search_model,
        )

    # SQLite (dev default): persist to disk inside the configured data_dir.
    db_path = str(settings.data_dir / "semantic_memory.db")
    return SQLiteSemanticMemory(
        db_path=db_path,
        model_name=settings.semantic_search_model,
    )
