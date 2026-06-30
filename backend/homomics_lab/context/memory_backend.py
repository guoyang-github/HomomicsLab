"""MemoryBackend: unified semantic memory built on pluggable embeddings, vector store and graph backends.

This implementation replaces the legacy SQLite/PostgreSQL semantic memory classes with a
modular design:

- ``EmbeddingProvider`` computes dense embeddings (sentence-transformers / OpenAI / Ollama).
- ``VectorStoreBackend`` stores the dense vectors and serves nearest-neighbour search.
- A small local SQLite metadata index handles structured queries (list/count/prune/consolidate)
  and keyword fallback when embeddings are unavailable.
- ``GraphBackend`` (optional) stores memory nodes and relationships for graph-traversal recall.
"""

import asyncio
import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from homomics_lab.config import Settings, settings as default_settings
from homomics_lab.context.feedback_store import (
    ExecutionFeedback,
    FeedbackOutcome,
    FeedbackStore,
    SQLiteFeedbackStore,
)
from homomics_lab.context.graph.base import GraphBackend
from homomics_lab.context.graph.factory import get_graph_backend, reset_graph_backend
from homomics_lab.context.vector_store.base import VectorStoreBackend
from homomics_lab.context.vector_store.factory import get_vector_store, reset_vector_store
from homomics_lab.embeddings.base import EmbeddingProvider
from homomics_lab.embeddings.factory import get_embedding_provider, reset_embedding_provider

logger = logging.getLogger(__name__)

_COLLECTION = "memories"
_RRF_K = 60


class MemoryType(str, Enum):
    """Categories of stored memories."""

    CONVERSATION = "conversation"
    TASK = "task"
    EXPERIMENT = "experiment"
    NOTE = "note"
    PREFERENCE = "preference"
    CONCEPT = "concept"


class MemoryBackend:
    """Pluggable semantic memory backend.

    The backend is intentionally split into three concerns:

    1. **Embeddings** – dense representation of memory text.
    2. **Vector store** – approximate nearest-neighbour search over embeddings.
    3. **Metadata store** – structured SQLite index for type/scope/time queries.
    4. **Graph store** (optional) – memory nodes and session/project relationships.

    All public methods are async.  Synchronous embedding models and SQLite are executed
    via ``asyncio.to_thread`` so they do not block the event loop.
    """

    DEFAULT_MODEL = "all-MiniLM-L6-v2"

    def __init__(
        self,
        db_path: Optional[Path] = None,
        model_name: Optional[str] = None,
        settings: Optional[Settings] = None,
        embedding_provider: Optional[EmbeddingProvider] = None,
        vector_store: Optional[VectorStoreBackend] = None,
        graph_backend: Optional[GraphBackend] = None,
        feedback_store: Optional[FeedbackStore] = None,
    ) -> None:
        self.settings = settings or default_settings
        self._model_name = model_name or self.settings.embedding_model or self.DEFAULT_MODEL

        # Allow injection for tests; otherwise use the configured factories.
        self._embedding_provider = embedding_provider
        self._vector_store = vector_store
        self._graph_backend = graph_backend
        self._feedback_store = feedback_store

        self._owns_embedding = embedding_provider is None
        self._owns_vector_store = vector_store is None
        self._owns_graph_backend = graph_backend is None
        self._owns_feedback_store = feedback_store is None

        self.db_path = Path(db_path) if db_path else self.settings.data_dir / "memory_meta.db"
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    # ------------------------------------------------------------------
    # Lazy accessors
    # ------------------------------------------------------------------
    def _get_embedding_provider(self) -> Optional[EmbeddingProvider]:
        if self._embedding_provider is None:
            # If the caller injected a model name directly, build a dedicated provider
            # instead of mutating the global singleton.
            if self._model_name and self._model_name != (self.settings.embedding_model or ""):
                from homomics_lab.embeddings.sentence_transformers import (
                    SentenceTransformersProvider,
                )

                self._embedding_provider = SentenceTransformersProvider(model_name=self._model_name)
                self._owns_embedding = True
            else:
                self._embedding_provider = get_embedding_provider(self.settings)
        return self._embedding_provider

    def _get_vector_store(self) -> VectorStoreBackend:
        if self._vector_store is None:
            self._vector_store = get_vector_store(self.settings)
        return self._vector_store

    def _get_graph_backend(self) -> Optional[GraphBackend]:
        if self._graph_backend is None:
            self._graph_backend = get_graph_backend(self.settings)
        return self._graph_backend

    def _get_feedback_store(self) -> FeedbackStore:
        if self._feedback_store is None:
            self._feedback_store = SQLiteFeedbackStore(
                db_path=self.settings.data_dir / "feedback.db"
            )
        return self._feedback_store

    # ------------------------------------------------------------------
    # Embedding helpers
    # ------------------------------------------------------------------
    async def _embed(self, texts: List[str]) -> Optional[List[List[float]]]:
        """Encode texts, returning None if the provider is unavailable."""
        if not texts:
            return []
        provider = self._get_embedding_provider()
        if provider is None or not provider.is_available():
            return None
        try:
            return await asyncio.to_thread(provider.encode, texts)
        except Exception as exc:
            logger.warning("Embedding failed: %s", exc)
            return None

    async def _dimension(self) -> int:
        provider = self._get_embedding_provider()
        if provider is None:
            return 0
        # ``dimension`` may load the model; offload if it is expensive.
        try:
            return await asyncio.to_thread(lambda: provider.dimension)
        except Exception as exc:
            logger.warning("Failed to determine embedding dimension: %s", exc)
            return 0

    # ------------------------------------------------------------------
    # Metadata store
    # ------------------------------------------------------------------
    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _init_db(self) -> None:
        conn = self._get_conn()
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                text TEXT NOT NULL,
                memory_type TEXT NOT NULL,
                metadata TEXT NOT NULL DEFAULT '{}',
                importance REAL NOT NULL DEFAULT 0.5,
                ttl_days INTEGER,
                project_id TEXT,
                session_id TEXT,
                created_at TEXT NOT NULL,
                last_accessed TEXT
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(memory_type)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_memories_project ON memories(project_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_memories_session ON memories(session_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_memories_created ON memories(created_at)"
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_memories_project_session_created
            ON memories(project_id, session_id, created_at)
            """
        )
        # Lightweight FTS5 index for keyword fallback.
        conn.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                text,
                content='memories',
                content_rowid='rowid'
            )
            """
        )
        conn.commit()

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        meta = json.loads(row["metadata"])
        return {
            "id": row["id"],
            "text": row["text"],
            "memory_type": row["memory_type"],
            "metadata": meta,
            "importance": row["importance"],
            "ttl_days": row["ttl_days"],
            "project_id": row["project_id"],
            "session_id": row["session_id"],
            "created_at": row["created_at"],
            "last_accessed": row["last_accessed"],
        }

    def _fts_insert(self, rowid: int, text: str) -> None:
        self._get_conn().execute(
            "INSERT OR REPLACE INTO memories_fts(rowid, text) VALUES (?, ?)", (rowid, text)
        )

    def _fts_delete_by_rowids(self, rowids: List[int]) -> None:
        if not rowids:
            return
        placeholders = ",".join("?" for _ in rowids)
        self._get_conn().execute(
            f"DELETE FROM memories_fts WHERE rowid IN ({placeholders})", rowids
        )

    def _build_where(
        self,
        memory_type: Optional[str] = None,
        project_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> tuple:
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
        return where, params

    # ------------------------------------------------------------------
    # Graph helpers
    # ------------------------------------------------------------------
    async def _add_graph_node(self, memory_id: str, row: Dict[str, Any]) -> None:
        graph = self._get_graph_backend()
        if graph is None:
            return
        try:
            await graph.add_node(
                node_id=memory_id,
                labels=["Memory", row["memory_type"].capitalize()],
                properties={
                    "text": row["text"][:500],
                    "memory_type": row["memory_type"],
                    "project_id": row["project_id"],
                    "session_id": row["session_id"],
                    "created_at": row["created_at"],
                },
            )
            if row.get("project_id"):
                await graph.add_edge(
                    from_id=row["project_id"],
                    to_id=memory_id,
                    edge_type="HAS_MEMORY",
                )
            if row.get("session_id"):
                await graph.add_edge(
                    from_id=row["session_id"],
                    to_id=memory_id,
                    edge_type="HAS_MEMORY",
                )
        except Exception as exc:
            logger.warning("Graph memory indexing failed: %s", exc)

    async def _add_graph_edges_between(self, from_id: str, to_id: str, edge_type: str) -> None:
        graph = self._get_graph_backend()
        if graph is None:
            return
        try:
            await graph.add_edge(from_id=from_id, to_id=to_id, edge_type=edge_type)
        except Exception as exc:
            logger.warning("Graph edge creation failed: %s", exc)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
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
        """Add a memory and index it in the vector/graph stores."""
        memory_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        meta = dict(metadata or {})
        if project_id is not None:
            meta["project_id"] = project_id
        if session_id is not None:
            meta["session_id"] = session_id
        project_id = project_id or meta.get("project_id")
        session_id = session_id or meta.get("session_id")
        meta_json = json.dumps(meta, ensure_ascii=False)

        # Compute embedding if possible.
        embeddings = await self._embed([text])

        def _write() -> None:
            conn = self._get_conn()
            cursor = conn.execute(
                """
                INSERT INTO memories (
                    id, text, memory_type, metadata, importance, ttl_days,
                    project_id, session_id, created_at, last_accessed
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    memory_id,
                    text,
                    memory_type,
                    meta_json,
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
            return cursor.lastrowid

        await asyncio.to_thread(_write)

        # Vector store indexing.
        if embeddings:
            try:
                await self._get_vector_store().upsert(
                    collection=_COLLECTION,
                    ids=[memory_id],
                    texts=[text],
                    embeddings=embeddings,
                    metadata=[
                        {
                            "memory_type": memory_type,
                            "project_id": project_id,
                            "session_id": session_id,
                            "created_at": created_at,
                        }
                    ],
                )
            except Exception as exc:
                logger.warning("Vector store upsert failed: %s", exc)

        # Graph indexing.
        await self._add_graph_node(
            memory_id,
            {
                "text": text,
                "memory_type": memory_type,
                "project_id": project_id,
                "session_id": session_id,
                "created_at": created_at,
            },
        )

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
        """Search memories by semantic similarity with optional keyword hybrid fusion."""
        if not query.strip():
            return []

        limit = max(top_k * 2, 10)
        vector_filters = {
            k: v
            for k, v in {
                "memory_type": memory_type,
                "project_id": project_id,
                "session_id": session_id,
            }.items()
            if v is not None
        }

        dense_results: Dict[str, Dict[str, Any]] = {}
        query_embedding = await self._embed([query])
        if query_embedding:
            try:
                vec_hits = await self._get_vector_store().search(
                    collection=_COLLECTION,
                    query_embedding=query_embedding[0],
                    top_k=limit,
                    filters=vector_filters or None,
                )
                for rank, hit in enumerate(vec_hits):
                    if hit.score >= min_score:
                        dense_results[hit.id] = {
                            "id": hit.id,
                            "score": hit.score,
                            "_dense_rank": rank + 1,
                        }
            except Exception as exc:
                logger.warning("Vector search failed: %s", exc)

        fts_results: Dict[str, Dict[str, Any]] = {}
        if hybrid:
            try:
                kw_hits = await self._get_vector_store().keyword_search(
                    collection=_COLLECTION,
                    query=query,
                    top_k=limit,
                    filters=vector_filters or None,
                )
                for rank, hit in enumerate(kw_hits):
                    fts_results[hit.id] = {
                        "id": hit.id,
                        "score": 1.0,
                        "_fts_rank": rank + 1,
                    }
            except Exception as exc:
                logger.warning("Keyword search failed: %s", exc)

        # If no vector index is available, fall back to local FTS5/keyword search.
        if not dense_results and not fts_results:
            fallback = await self._local_keyword_search(
                query,
                limit=limit,
                memory_type=memory_type,
                project_id=project_id,
                session_id=session_id,
            )
            for rank, row in enumerate(fallback):
                fts_results[row["id"]] = {
                    "id": row["id"],
                    "score": 1.0,
                    "_fts_rank": rank + 1,
                }

        # Enrich hits from the metadata store and apply RRF fusion.
        all_ids = set(dense_results) | set(fts_results)
        fused: List[Dict[str, Any]] = []
        for memory_id in all_ids:
            row = await self.get(memory_id)
            if row is None:
                continue
            # Post-filter: not all vector backends support metadata filters natively.
            if memory_type is not None and row.get("memory_type") != memory_type:
                continue
            if project_id is not None and row.get("project_id") != project_id:
                continue
            if session_id is not None and row.get("session_id") != session_id:
                continue

            rrf_score = 0.0
            if memory_id in dense_results:
                rrf_score += 1.0 / (_RRF_K + dense_results[memory_id]["_dense_rank"])
            if memory_id in fts_results:
                rrf_score += 1.0 / (_RRF_K + fts_results[memory_id]["_fts_rank"])

            row["score"] = round(rrf_score, 6)
            fused.append(row)

        fused.sort(key=lambda r: r["score"], reverse=True)
        results = fused[:top_k]
        if results:
            await self._touch([r["id"] for r in results])
        return results

    async def _local_keyword_search(
        self,
        query: str,
        limit: int,
        memory_type: Optional[str] = None,
        project_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """SQLite FTS5 fallback when the vector store cannot be queried."""
        where, params = self._build_where(memory_type, project_id, session_id)
        # The MATCH parameter must come after the structured filters.
        if where:
            sql = f"""
                SELECT memories.id
                FROM memories_fts
                JOIN memories ON memories.rowid = memories_fts.rowid
                {where}
                AND memories_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """
            params.append(query)
        else:
            sql = """
                SELECT memories.id
                FROM memories_fts
                JOIN memories ON memories.rowid = memories_fts.rowid
                WHERE memories_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """
            params = [query]
        params.append(limit)

        def _query() -> List[sqlite3.Row]:
            return self._get_conn().execute(sql, params).fetchall()

        rows = await asyncio.to_thread(_query)
        return [await self.get(r["id"]) for r in rows if r["id"]]

    async def get(self, memory_id: str) -> Optional[Dict[str, Any]]:
        def _query() -> Optional[sqlite3.Row]:
            return self._get_conn().execute(
                "SELECT * FROM memories WHERE id = ?", (memory_id,)
            ).fetchone()

        row = await asyncio.to_thread(_query)
        if row is None:
            return None
        return self._row_to_dict(row)

    async def delete(self, memory_id: str) -> bool:
        def _delete() -> int:
            conn = self._get_conn()
            row = conn.execute(
                "SELECT rowid FROM memories WHERE id = ?", (memory_id,)
            ).fetchone()
            if row is None:
                return 0
            self._fts_delete_by_rowids([row["rowid"]])
            cursor = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            conn.commit()
            return cursor.rowcount

        deleted = await asyncio.to_thread(_delete)
        if deleted:
            try:
                await self._get_vector_store().delete(_COLLECTION, [memory_id])
            except Exception as exc:
                logger.warning("Vector store delete failed: %s", exc)
        return deleted > 0

    async def list_by_type(
        self,
        memory_type: str,
        limit: int = 100,
        offset: int = 0,
        project_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        where, params = self._build_where(memory_type, project_id, session_id)
        sql = f"""
            SELECT * FROM memories {where}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        def _query() -> List[sqlite3.Row]:
            return self._get_conn().execute(sql, params).fetchall()

        rows = await asyncio.to_thread(_query)
        return [self._row_to_dict(r) for r in rows]

    async def count(
        self,
        memory_type: Optional[str] = None,
        project_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> int:
        where, params = self._build_where(memory_type, project_id, session_id)
        sql = f"SELECT COUNT(*) FROM memories {where}"

        def _query() -> int:
            row = self._get_conn().execute(sql, params).fetchone()
            return row[0] if row else 0

        return await asyncio.to_thread(_query)

    async def prune_stale_memories(
        self,
        retention_days: int = 30,
        low_importance_threshold: float = 0.3,
    ) -> int:
        def _prune() -> List[str]:
            conn = self._get_conn()
            rows = conn.execute(
                """
                SELECT id, rowid FROM memories
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
            if not rows:
                return []
            ids = [r["id"] for r in rows]
            self._fts_delete_by_rowids([r["rowid"] for r in rows])
            placeholders = ",".join("?" for _ in ids)
            conn.execute(f"DELETE FROM memories WHERE id IN ({placeholders})", ids)
            conn.commit()
            return ids

        ids = await asyncio.to_thread(_prune)
        if ids:
            try:
                await self._get_vector_store().delete(_COLLECTION, ids)
            except Exception as exc:
                logger.warning("Vector store prune delete failed: %s", exc)
        return len(ids)

    async def consolidate_conversation_chunks(
        self,
        session_id: Optional[str] = None,
        chunk_size: int = 5,
        project_id: Optional[str] = None,
    ) -> int:
        if chunk_size < 2:
            return 0

        where, params = self._build_where(MemoryType.CONVERSATION, project_id, session_id)
        sql = f"""
            SELECT * FROM memories {where}
            ORDER BY created_at ASC
        """

        def _query() -> List[sqlite3.Row]:
            return self._get_conn().execute(sql, params).fetchall()

        rows = await asyncio.to_thread(_query)

        groups: List[List[Dict[str, Any]]] = []
        current_group: List[Dict[str, Any]] = []
        current_key: Optional[str] = None
        for row in rows:
            item = self._row_to_dict(row)
            key = item.get("session_id")
            if key != current_key or len(current_group) >= chunk_size:
                if len(current_group) >= chunk_size:
                    groups.append(current_group)
                current_group = [item]
                current_key = key
            else:
                current_group.append(item)
        if len(current_group) >= chunk_size:
            groups.append(current_group)

        if not groups:
            return 0

        for group in groups:
            ids = [m["id"] for m in group]
            merged_text = "\n\n".join(f"[{m['created_at']}] {m['text']}" for m in group)
            importances = [m["importance"] for m in group if m["importance"] is not None]
            merged_importance = sum(importances) / len(importances) if importances else 0.5
            ttl_days = group[0].get("ttl_days")
            merged_meta = {
                **group[0]["metadata"],
                "consolidated": True,
                "source_ids": ids,
                "original_count": len(group),
            }
            new_id = await self.add(
                text=merged_text,
                memory_type=MemoryType.CONVERSATION,
                metadata=merged_meta,
                importance=merged_importance,
                ttl_days=ttl_days,
                project_id=group[0].get("project_id"),
                session_id=group[0].get("session_id"),
            )
            # Link consolidated summary back to the original memories in the graph.
            for old_id in ids:
                await self._add_graph_edges_between(new_id, old_id, "CONSOLIDATES")
            await self._delete_many(ids)

        return len(groups)

    async def _delete_many(self, ids: List[str]) -> None:
        def _delete() -> None:
            conn = self._get_conn()
            placeholders = ",".join("?" for _ in ids)
            rows = conn.execute(
                f"SELECT rowid FROM memories WHERE id IN ({placeholders})", ids
            ).fetchall()
            self._fts_delete_by_rowids([r["rowid"] for r in rows])
            conn.execute(f"DELETE FROM memories WHERE id IN ({placeholders})", ids)
            conn.commit()

        await asyncio.to_thread(_delete)
        try:
            await self._get_vector_store().delete(_COLLECTION, ids)
        except Exception as exc:
            logger.warning("Vector store batch delete failed: %s", exc)

    async def _touch(self, memory_ids: List[str]) -> None:
        if not memory_ids:
            return
        now = datetime.now(timezone.utc).isoformat()
        placeholders = ",".join("?" for _ in memory_ids)

        def _update() -> None:
            self._get_conn().execute(
                f"UPDATE memories SET last_accessed = ? WHERE id IN ({placeholders})",
                (now, *memory_ids),
            )
            self._get_conn().commit()

        await asyncio.to_thread(_update)

    async def add_feedback(
        self,
        memory_id: str,
        outcome: FeedbackOutcome,
        project_id: Optional[str] = None,
        rating: Optional[int] = None,
        comment: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record execution feedback for a memory and adjust its importance."""
        feedback = ExecutionFeedback(
            target_type="memory",
            target_id=memory_id,
            outcome=outcome,
            project_id=project_id,
            rating=rating,
            comment=comment,
            context=context or {},
        )

        def _record_and_adjust() -> None:
            self._get_feedback_store().record(feedback)
            delta = 0.1 if outcome == FeedbackOutcome.SUCCESS else -0.1 if outcome == FeedbackOutcome.FAILURE else 0.0
            if delta:
                self._get_conn().execute(
                    "UPDATE memories SET importance = MAX(0.0, MIN(1.0, importance + ?)) WHERE id = ?",
                    (delta, memory_id),
                )
                self._get_conn().commit()

        await asyncio.to_thread(_record_and_adjust)

    async def close(self) -> None:
        def _close() -> None:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

        await asyncio.to_thread(_close)

        # Only close backends we own via the factory singletons.
        if self._owns_vector_store:
            try:
                await self._get_vector_store().close()
                reset_vector_store()
            except Exception as exc:
                logger.warning("Vector store close failed: %s", exc)
        if self._owns_graph_backend:
            try:
                await self._get_graph_backend().close()
                reset_graph_backend()
            except Exception as exc:
                logger.warning("Graph backend close failed: %s", exc)
        if self._owns_feedback_store:
            try:
                self._get_feedback_store().close()
            except Exception as exc:
                logger.warning("Feedback store close failed: %s", exc)
        if self._owns_embedding:
            reset_embedding_provider()


def create_semantic_memory(settings: Optional[Settings] = None) -> Optional[MemoryBackend]:
    """Factory that mirrors the legacy ``create_semantic_memory`` signature."""
    settings = settings or default_settings
    if not getattr(settings, "enable_semantic_memory", True):
        return None
    model_name = settings.embedding_model or settings.semantic_search_model
    if not model_name:
        return None
    return MemoryBackend(settings=settings)
