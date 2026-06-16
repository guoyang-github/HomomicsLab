"""Execution trace store for plan/job-level observability.

A trace captures the full execution tree of a job or plan:
  job
    └── phase
          └── skill
                └── tool_call
                └── llm_call
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from sqlalchemy import desc, select

from homomics_lab.database.connection import AsyncSessionLocal
from homomics_lab.database.models import TraceRecord


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
        """Create a new trace and return it."""
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
            record = self._to_record(trace)
            session.add(record)
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
        trace = await self.get_trace(trace_id)
        if trace is None:
            return None
        node = TraceNode(
            parent_id=parent_id,
            node_type=node_type,
            name=name,
            inputs=inputs,
            metadata=metadata or {},
        )
        trace.nodes.append(node)
        await self._save(trace)
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
        trace = await self.get_trace(trace_id)
        if trace is None:
            return None
        for node in trace.nodes:
            if node.node_id == node_id:
                if status is not None:
                    node.status = status
                if outputs is not None:
                    node.outputs = outputs
                if error is not None:
                    node.error = error
                if logs is not None:
                    node.logs = logs
                if status in {"completed", "failed", "cancelled"}:
                    node.ended_at = datetime.now(timezone.utc)
                break
        return await self._save(trace)

    async def finish_trace(
        self,
        trace_id: str,
        status: str,
        error_message: Optional[str] = None,
    ) -> Optional[ExecutionTrace]:
        """Mark a trace as finished and persist it."""
        trace = await self.get_trace(trace_id)
        if trace is None:
            return None
        trace.status = status
        trace.error_message = error_message
        trace.ended_at = datetime.now(timezone.utc)
        # Also mark the root node.
        for node in trace.nodes:
            if node.node_id == "root":
                node.status = status
                node.ended_at = trace.ended_at
                if error_message:
                    node.error = error_message
        return await self._save(trace)

    async def get_trace(self, trace_id: str) -> Optional[ExecutionTrace]:
        async with self._session_factory() as session:
            record = await session.get(TraceRecord, trace_id)
            return self._to_model(record) if record else None

    async def list_recent(self, limit: int = 100) -> List[ExecutionTrace]:
        async with self._session_factory() as session:
            stmt = select(TraceRecord).order_by(desc(TraceRecord.started_at)).limit(limit)
            result = await session.execute(stmt)
            return [self._to_model(r) for r in result.scalars().all()]

    async def _save(self, trace: ExecutionTrace) -> ExecutionTrace:
        async with self._session_factory() as session:
            record = await session.get(TraceRecord, trace.trace_id)
            if record is None:
                record = self._to_record(trace)
                session.add(record)
            else:
                self._update_record(record, trace)
            await session.commit()
        return trace

    @staticmethod
    def _to_record(trace: ExecutionTrace) -> TraceRecord:
        return TraceRecord(
            trace_id=trace.trace_id,
            session_id=trace.session_id,
            project_id=trace.project_id,
            status=trace.status,
            started_at=trace.started_at,
            ended_at=trace.ended_at,
            error_message=trace.error_message,
            nodes_json=json.dumps(
                [n.model_dump(mode="json") for n in trace.nodes], default=str
            ),
        )

    @staticmethod
    def _update_record(record: TraceRecord, trace: ExecutionTrace) -> None:
        record.status = trace.status
        record.ended_at = trace.ended_at
        record.error_message = trace.error_message
        record.nodes_json = json.dumps(
            [n.model_dump(mode="json") for n in trace.nodes], default=str
        )

    @staticmethod
    def _to_model(record: TraceRecord) -> ExecutionTrace:
        nodes = []
        if record.nodes_json:
            nodes = [TraceNode.model_validate(n) for n in json.loads(record.nodes_json)]
        return ExecutionTrace(
            trace_id=record.trace_id,
            session_id=record.session_id,
            project_id=record.project_id,
            status=record.status,
            started_at=record.started_at,
            ended_at=record.ended_at,
            error_message=record.error_message,
            nodes=nodes,
        )
