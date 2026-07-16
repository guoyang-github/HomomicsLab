"""Background jobs should emit ``type: artifact`` chat messages for non-plot artifacts."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import pytest

from homomics_lab.artifacts import build_artifact
from homomics_lab.context.memory_manager import MemoryManager
from homomics_lab.context.session_store import SessionState, SessionStore
from homomics_lab.context.working_memory import WorkingMemory
from homomics_lab.jobs.constants import JobMode, JobStatus
from homomics_lab.jobs.models import Job
from homomics_lab.jobs.runner import BackgroundJobRunner
from homomics_lab.models.common import ChatMessage, MessageType


class _FakeSessionStore(SessionStore):
    def __init__(self, state: Optional[SessionState] = None):
        self._state = state
        self.saved: List[SessionState] = []

    async def get(self, session_id: str) -> Optional[SessionState]:
        return self._state

    async def save(self, state: SessionState) -> None:
        self.saved.append(state)

    async def delete(self, session_id: str) -> None:
        pass

    async def list(self, project_id: Optional[str] = None) -> List[SessionState]:
        return [self._state] if self._state else []

    async def cleanup_expired(self, ttl_days: int) -> int:
        return 0


def _make_job(working_memory: WorkingMemory, job_id: str = "job_artifact_001") -> Job:
    return Job(
        job_id=job_id,
        session_id="session_artifact_001",
        project_id="project_artifact_001",
        status=JobStatus.COMPLETED,
        mode=JobMode.SINGLE_STEP,
        working_memory=working_memory,
        result={"task_result": {"result": {}}},
    )


def _make_result(task_result: Dict[str, Any], tmp_path: Path):
    """Build a result-like namespace and task tree from a skill result."""
    task = SimpleNamespace(
        status="completed",
        result=task_result,
        parameters={"user_request": "run analysis"},
        skills_required=["demo-skill"],
    )
    tree = SimpleNamespace(tasks=[task])
    result = SimpleNamespace(
        task_tree=tree,
        mode="single_step",
        response_text="done",
        progress=100,
        hitl_task_id=None,
        error=None,
    )
    return result, tree


def _create_artifact_files(tmp_path: Path) -> Dict[str, Path]:
    files = {
        "report": tmp_path / "report.html",
        "table": tmp_path / "table.csv",
        "json": tmp_path / "data.json",
        "anndata": tmp_path / "data.h5ad",
        "image": tmp_path / "plot.png",
        "plotly": tmp_path / "plotly.json",
    }
    files["report"].write_text("<html><body>report</body></html>", encoding="utf-8")
    files["table"].write_text("a,b\n1,2\n", encoding="utf-8")
    files["json"].write_text('{"foo": "bar"}', encoding="utf-8")
    files["anndata"].write_bytes(b"\x89HDF\r\n\x1a\n")
    files["image"].write_bytes(b"\x89PNG\r\n\x1a\n")
    files["plotly"].write_text('{"data": [], "layout": {}}', encoding="utf-8")
    return files


@pytest.mark.asyncio
async def test_artifact_envelopes_are_embedded_in_todo_on_success(tmp_path: Path) -> None:
    files = _create_artifact_files(tmp_path)

    # Build artifact list with explicit metadata (report_id, summary, url).
    artifacts: List[Dict[str, Any]] = []
    for key in ("report", "table", "json", "anndata", "image", "plotly"):
        env = build_artifact(files[key])
        assert env is not None
        if key == "report":
            env["report_id"] = "report_123"
            env["summary"] = "executive summary"
            env["url"] = "/api/reports/report_123"
        elif key == "table":
            env["summary"] = "counts table"
        artifacts.append(env)

    task_result: Dict[str, Any] = {"success": True, "artifacts": artifacts}
    result, tree = _make_result(task_result, tmp_path)

    working_memory = WorkingMemory()
    working_memory.add_message(
        ChatMessage(
            id="msg_0",
            type=MessageType.TODO_LIST,
            content={"job_id": "job_artifact_001", "text": "queued", "status": "pending"},
            sender="agent",
        )
    )
    job = _make_job(working_memory)
    job.result = {"task_result": {"result": task_result}}

    store = _FakeSessionStore(
        SessionState(
            session_id=job.session_id,
            project_id=job.project_id,
            working_memory=working_memory,
            task_tree=None,
            updated_at=datetime.now(timezone.utc),
        )
    )
    memory_manager = MemoryManager(session_store=store)
    runner = BackgroundJobRunner(
        queue=SimpleNamespace(),
        repository=SimpleNamespace(),
        pubsub=SimpleNamespace(publish=lambda *a, **k: None),
        memory_manager=memory_manager,
    )

    await runner._update_queued_todo_message(job, result)

    # Artifacts are now surfaced inside the TODO_LIST card so the chat stream
    # stays compact; standalone ARTIFACT messages are no longer emitted.
    todo_msgs = [m for m in working_memory.messages if m.type == MessageType.TODO_LIST]
    assert len(todo_msgs) == 1
    todo_content = todo_msgs[0].content
    assert isinstance(todo_content, dict)
    embedded = todo_content.get("artifacts", [])
    kinds = {env.get("kind") for env in embedded}
    assert "html" in kinds
    assert "table" in kinds
    assert "json" in kinds
    assert "anndata" in kinds
    assert "image" not in kinds, "images are streamed as PLOT messages"
    assert "plotly" not in kinds, "plotly figures are streamed as PLOT_DATA messages"

    # Report-specific metadata preserved.
    report_env = next(env for env in embedded if env.get("kind") == "html")
    assert report_env.get("report_id") == "report_123"
    assert report_env.get("summary") == "executive summary"
    assert report_env.get("url") == "/api/reports/report_123"

    # A rich summary message is also appended to the conversation and persisted.
    assert len(store.saved) == 2
    persisted = store.saved[-1].working_memory
    persisted_todo = [m for m in persisted.messages if m.type == MessageType.TODO_LIST]
    assert len(persisted_todo) == 1
    assert len(persisted_todo[0].content.get("artifacts", [])) == len(embedded)


@pytest.mark.asyncio
async def test_no_artifact_envelopes_without_artifacts(tmp_path: Path) -> None:
    task_result: Dict[str, Any] = {"success": True}
    result, tree = _make_result(task_result, tmp_path)

    working_memory = WorkingMemory()
    working_memory.add_message(
        ChatMessage(
            id="msg_0",
            type=MessageType.TODO_LIST,
            content={"job_id": "job_no_artifact_001", "text": "queued", "status": "pending"},
            sender="agent",
        )
    )
    job = _make_job(working_memory, job_id="job_no_artifact_001")
    job.result = {"task_result": {"result": task_result}}

    store = _FakeSessionStore(
        SessionState(
            session_id=job.session_id,
            project_id=job.project_id,
            working_memory=working_memory,
            task_tree=None,
            updated_at=datetime.now(timezone.utc),
        )
    )
    memory_manager = MemoryManager(session_store=store)
    runner = BackgroundJobRunner(
        queue=SimpleNamespace(),
        repository=SimpleNamespace(),
        pubsub=SimpleNamespace(publish=lambda *a, **k: None),
        memory_manager=memory_manager,
    )

    await runner._update_queued_todo_message(job, result)

    todo_msgs = [m for m in working_memory.messages if m.type == MessageType.TODO_LIST]
    assert len(todo_msgs) == 1
    assert todo_msgs[0].content.get("artifacts", []) == []

    # A concise completion summary is appended even when no artifacts exist.
    summary_msgs = [m for m in working_memory.messages if m.type == MessageType.TEXT]
    assert len(summary_msgs) == 1
    assert "分析已完成" in summary_msgs[0].content
    assert len(store.saved) == 2
