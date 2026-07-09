"""Execution trace store for plan/job-level observability.

A trace captures the full execution tree of a job or plan:
  job
    └── phase
          └── skill
                └── tool_call
                └── llm_call

Trace nodes are persisted in individual rows so that updating a single node
no longer requires rewriting the entire trace JSON blob.
"""

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from sqlalchemy import delete, desc, select
from sqlalchemy.orm import selectinload

from homomics_lab.database.connection import AsyncSessionLocal
from homomics_lab.database.models import TraceNodeRecord, TraceRecord


class TraceNode(BaseModel):
    """A single node in an execution trace."""

    node_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    parent_id: Optional[str] = None
    node_type: str  # plan | phase | skill | tool | llm | error
    name: str
    status: str = "running"  # running | completed | failed | cancelled
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: Optional[datetime] = None
    inputs: Optional[Dict[str, Any]] = None
    outputs: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    logs: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExecutionTrace(BaseModel):
    """Full trace for a job or plan execution."""

    trace_id: str
    session_id: Optional[str] = None
    project_id: Optional[str] = None
    status: str = "running"
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: Optional[datetime] = None
    error_message: Optional[str] = None
    nodes: List[TraceNode] = Field(default_factory=list)

    def model_dump(self, **kwargs):
        # Pydantic v2 compatibility: ensure datetimes serialize to ISO strings.
        data = super().model_dump(**kwargs)
        return data


class TraceStore:
    """Persist and retrieve execution traces from SQLite."""

    def __init__(self, session_factory=AsyncSessionLocal):
        self._session_factory = session_factory

    async def start_trace(
        self,
        trace_id: str,
        session_id: Optional[str] = None,
        project_id: Optional[str] = None,
        root_name: str = "job",
    ) -> ExecutionTrace:
        """Create a new trace and return it.

        If a trace with ``trace_id`` already exists (e.g. the chat endpoint
        already started one and a downstream executor tries to start another),
        return the existing trace instead of raising a uniqueness error.
        """
        async with self._session_factory() as session:
            existing = await session.get(TraceRecord, trace_id)
            if existing is not None:
                return self._record_to_trace(existing)

        trace = ExecutionTrace(
            trace_id=trace_id,
            session_id=session_id,
            project_id=project_id,
            status="running",
            nodes=[
                TraceNode(
                    node_id="root",
                    node_type="plan",
                    name=root_name,
                )
            ],
        )
        async with self._session_factory() as session:
            session.add(self._trace_to_record(trace))
            session.add(self._node_to_record(trace_id, trace.nodes[0]))
            await session.commit()
        return trace

    async def add_node(
        self,
        trace_id: str,
        node_type: str,
        name: str,
        parent_id: Optional[str] = None,
        inputs: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[TraceNode]:
        """Append a node to an existing trace."""
        async with self._session_factory() as session:
            trace_record = await session.get(TraceRecord, trace_id)
            if trace_record is None:
                return None

            node = TraceNode(
                parent_id=parent_id,
                node_type=node_type,
                name=name,
                inputs=inputs,
                metadata=metadata or {},
            )
            session.add(self._node_to_record(trace_id, node))
            await session.commit()
            return node

    async def update_node(
        self,
        trace_id: str,
        node_id: str,
        status: Optional[str] = None,
        outputs: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        logs: Optional[List[str]] = None,
    ) -> Optional[ExecutionTrace]:
        """Update a node's status/outputs/error/logs."""
        async with self._session_factory() as session:
            node_record = await session.scalar(
                select(TraceNodeRecord).where(
                    TraceNodeRecord.trace_id == trace_id,
                    TraceNodeRecord.node_id == node_id,
                )
            )
            if node_record is None:
                return None

            if status is not None:
                node_record.status = status
            if outputs is not None:
                node_record.outputs_json = json.dumps(outputs, default=str)
            if error is not None:
                node_record.error = error
            if logs is not None:
                node_record.logs_json = json.dumps(logs, default=str)
            if status in {"completed", "failed", "cancelled"}:
                node_record.ended_at = datetime.now(timezone.utc)

            await session.commit()

        return await self.get_trace(trace_id)

    async def finish_trace(
        self,
        trace_id: str,
        status: str,
        error_message: Optional[str] = None,
    ) -> Optional[ExecutionTrace]:
        """Mark a trace as finished and persist it."""
        async with self._session_factory() as session:
            trace_record = await session.get(TraceRecord, trace_id)
            if trace_record is None:
                return None

            trace_record.status = status
            trace_record.error_message = error_message
            trace_record.ended_at = datetime.now(timezone.utc)

            root_node = await session.scalar(
                select(TraceNodeRecord).where(
                    TraceNodeRecord.trace_id == trace_id,
                    TraceNodeRecord.node_id == "root",
                )
            )
            if root_node is not None:
                root_node.status = status
                root_node.ended_at = trace_record.ended_at
                if error_message:
                    root_node.error = error_message

            await session.commit()

        return await self.get_trace(trace_id)

    async def get_trace(self, trace_id: str) -> Optional[ExecutionTrace]:
        async with self._session_factory() as session:
            stmt = (
                select(TraceRecord)
                .options(selectinload(TraceRecord.nodes))
                .where(TraceRecord.trace_id == trace_id)
            )
            record = await session.scalar(stmt)
            return self._record_to_trace(record) if record else None

    async def list_recent(self, limit: int = 100) -> List[ExecutionTrace]:
        async with self._session_factory() as session:
            stmt = (
                select(TraceRecord)
                .options(selectinload(TraceRecord.nodes))
                .order_by(desc(TraceRecord.started_at))
                .limit(limit)
            )
            result = await session.execute(stmt)
            return [self._record_to_trace(r) for r in result.scalars().all()]

    async def _save(self, trace: ExecutionTrace) -> ExecutionTrace:
        """Persist trace-level changes (does not rewrite individual nodes)."""
        async with self._session_factory() as session:
            record = await session.get(TraceRecord, trace.trace_id)
            if record is None:
                record = self._trace_to_record(trace)
                session.add(record)
            else:
                record.session_id = trace.session_id
                record.project_id = trace.project_id
                record.status = trace.status
                record.started_at = trace.started_at
                record.ended_at = trace.ended_at
                record.error_message = trace.error_message
            await session.commit()
        return trace

    # ───────────────────────────────────────────────────────────────────────
    # Retention API
    # ───────────────────────────────────────────────────────────────────────

    async def delete_before(self, before: datetime) -> int:
        """Delete all traces started before ``before``."""
        async with self._session_factory() as session:
            await session.execute(
                delete(TraceNodeRecord).where(
                    TraceNodeRecord.trace_id.in_(
                        select(TraceRecord.trace_id).where(
                            TraceRecord.started_at < before
                        )
                    )
                )
            )
            result = await session.execute(
                delete(TraceRecord).where(TraceRecord.started_at < before)
            )
            await session.commit()
            return result.rowcount or 0

    async def delete_by_status(self, status: str) -> int:
        """Delete all traces with the given status."""
        async with self._session_factory() as session:
            await session.execute(
                delete(TraceNodeRecord).where(
                    TraceNodeRecord.trace_id.in_(
                        select(TraceRecord.trace_id).where(TraceRecord.status == status)
                    )
                )
            )
            result = await session.execute(
                delete(TraceRecord).where(TraceRecord.status == status)
            )
            await session.commit()
            return result.rowcount or 0

    async def delete_older_than(self, days: int) -> int:
        """Delete traces older than ``days`` days."""
        before = datetime.now(timezone.utc) - timedelta(days=days)
        return await self.delete_before(before)

    # ───────────────────────────────────────────────────────────────────────
    # Serialization helpers
    # ───────────────────────────────────────────────────────────────────────

    @staticmethod
    def _trace_to_record(trace: ExecutionTrace) -> TraceRecord:
        return TraceRecord(
            trace_id=trace.trace_id,
            session_id=trace.session_id,
            project_id=trace.project_id,
            status=trace.status,
            started_at=trace.started_at,
            ended_at=trace.ended_at,
            error_message=trace.error_message,
            nodes_json="[]",
        )

    @staticmethod
    def _node_to_record(trace_id: str, node: TraceNode) -> TraceNodeRecord:
        return TraceNodeRecord(
            trace_id=trace_id,
            node_id=node.node_id,
            parent_id=node.parent_id,
            node_type=node.node_type,
            name=node.name,
            status=node.status,
            started_at=node.started_at,
            ended_at=node.ended_at,
            inputs_json=json.dumps(node.inputs, default=str) if node.inputs is not None else "null",
            outputs_json=json.dumps(node.outputs, default=str) if node.outputs is not None else "null",
            error=node.error,
            logs_json=json.dumps(node.logs, default=str),
            metadata_json=json.dumps(node.metadata, default=str),
        )

    @staticmethod
    def _record_to_node(record: TraceNodeRecord) -> TraceNode:
        return TraceNode(
            node_id=record.node_id,
            parent_id=record.parent_id,
            node_type=record.node_type,
            name=record.name,
            status=record.status,
            started_at=record.started_at,
            ended_at=record.ended_at,
            inputs=json.loads(record.inputs_json) if record.inputs_json != "null" else None,
            outputs=json.loads(record.outputs_json) if record.outputs_json != "null" else None,
            error=record.error,
            logs=json.loads(record.logs_json) if record.logs_json else [],
            metadata=json.loads(record.metadata_json) if record.metadata_json else {},
        )

    @staticmethod
    def _record_to_trace(record: TraceRecord) -> ExecutionTrace:
        return ExecutionTrace(
            trace_id=record.trace_id,
            session_id=record.session_id,
            project_id=record.project_id,
            status=record.status,
            started_at=record.started_at,
            ended_at=record.ended_at,
            error_message=record.error_message,
            nodes=[TraceStore._record_to_node(n) for n in record.nodes],
        )
