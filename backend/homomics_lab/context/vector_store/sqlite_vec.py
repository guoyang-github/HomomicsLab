"""sqlite-vec vector store backend (test/minimal fallback)."""

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import sqlite_vec

from homomics_lab.context.vector_store.base import VectorSearchResult, VectorStoreBackend

logger = logging.getLogger(__name__)


class SQLiteVecBackend(VectorStoreBackend):
    """Minimal vector store using sqlite-vec."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = db_path or Path(":memory:")
        self._conn: Optional[sqlite3.Connection] = None

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.enable_load_extension(True)
            sqlite_vec.load(self._conn)
            self._conn.enable_load_extension(False)
        return self._conn

    async def create_collection(self, collection: str, dimension: int) -> None:
        conn = self._get_conn()
        conn.execute(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS {collection} USING vec0(embedding FLOAT[{dimension}])"
        )
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {collection}_payload (
                rowid INTEGER PRIMARY KEY,
                external_id TEXT UNIQUE,
                text TEXT,
                metadata TEXT
            )
            """
        )
        conn.commit()

    async def upsert(
        self,
        collection: str,
        ids: List[str],
        texts: List[str],
        embeddings: List[List[float]],
        metadata: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        await self.create_collection(collection, len(embeddings[0]))
        conn = self._get_conn()
        for i, doc_id in enumerate(ids):
            emb_json = json.dumps(embeddings[i])
            meta_json = json.dumps(metadata[i] if metadata and i < len(metadata) else {})
            cursor = conn.execute(
                f"INSERT OR REPLACE INTO {collection}_payload (external_id, text, metadata) VALUES (?, ?, ?)",
                (doc_id, texts[i], meta_json),
            )
            rowid = cursor.lastrowid
            conn.execute(
                f"INSERT OR REPLACE INTO {collection} (rowid, embedding) VALUES (?, ?)",
                (rowid, emb_json),
            )
        conn.commit()

    async def search(
        self,
        collection: str,
        query_embedding: List[float],
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[VectorSearchResult]:
        conn = self._get_conn()
        emb_json = json.dumps(query_embedding)
        rows = conn.execute(
            f"SELECT rowid, distance FROM {collection} WHERE embedding MATCH ? ORDER BY distance LIMIT ?",
            (emb_json, top_k),
        ).fetchall()
        return self._load_payloads(collection, rows)

    async def keyword_search(
        self,
        collection: str,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[VectorSearchResult]:
        conn = self._get_conn()
        query_lower = f"%{query.lower()}%"
        rows = conn.execute(
            f"""
            SELECT p.rowid, 0 AS distance
            FROM {collection}_payload p
            WHERE LOWER(p.text) LIKE ?
            LIMIT ?
            """,
            (query_lower, top_k),
        ).fetchall()
        return self._load_payloads(collection, rows)

    async def delete(self, collection: str, ids: List[str]) -> None:
        conn = self._get_conn()
        placeholders = ",".join("?" for _ in ids)
        rowid_rows = conn.execute(
            f"SELECT rowid FROM {collection}_payload WHERE external_id IN ({placeholders})",
            ids,
        ).fetchall()
        rowids = [r[0] for r in rowid_rows]
        if rowids:
            rowid_placeholders = ",".join("?" for _ in rowids)
            conn.execute(f"DELETE FROM {collection} WHERE rowid IN ({rowid_placeholders})", rowids)
        conn.execute(f"DELETE FROM {collection}_payload WHERE external_id IN ({placeholders})", ids)
        conn.commit()

    async def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _load_payloads(
        self, collection: str, rows: List[Tuple[int, float]]
    ) -> List[VectorSearchResult]:
        if not rows:
            return []
        conn = self._get_conn()
        rowids = [r[0] for r in rows]
        placeholders = ",".join("?" for _ in rowids)
        payload_rows = conn.execute(
            f"SELECT rowid, external_id, text, metadata FROM {collection}_payload WHERE rowid IN ({placeholders})",
            rowids,
        ).fetchall()
        payload_map = {r[0]: (r[1], r[2], json.loads(r[3])) for r in payload_rows}
        results = []
        for rowid, distance in rows:
            external_id, text, metadata = payload_map.get(rowid, (None, None, {}))
            if external_id is None:
                continue
            score = 1.0 - float(distance)
            metadata.pop("text", None)
            results.append(
                VectorSearchResult(id=external_id, score=score, text=text, metadata=metadata)
            )
        return results
