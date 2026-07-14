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
async def test_artifact_messages_are_appended_on_success(tmp_path: Path) -> None:
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

    # In-memory messages should contain artifact cards.
    artifact_msgs = [m for m in working_memory.messages if m.type == MessageType.ARTIFACT]
    kinds = {m.content.get("kind") for m in artifact_msgs}
    assert "html" in kinds
    assert "table" in kinds
    assert "json" in kinds
    assert "anndata" in kinds
    assert "image" not in kinds, "images are streamed as PLOT messages"
    assert "plotly" not in kinds, "plotly figures are streamed as PLOT_DATA messages"

    # Report-specific metadata preserved.
    report_msg = next(m for m in artifact_msgs if m.content.get("kind") == "html")
    assert report_msg.content.get("report_id") == "report_123"
    assert report_msg.content.get("summary") == "executive summary"
    assert report_msg.content.get("url") == "/api/reports/report_123"

    # Persisted working memory should be saved and also contain artifact messages.
    assert len(store.saved) == 1
    persisted = store.saved[0].working_memory
    persisted_artifact_msgs = [m for m in persisted.messages if m.type == MessageType.ARTIFACT]
    assert len(persisted_artifact_msgs) == len(artifact_msgs)


@pytest.mark.asyncio
async def test_no_artifact_messages_without_artifacts(tmp_path: Path) -> None:
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

    artifact_msgs = [m for m in working_memory.messages if m.type == MessageType.ARTIFACT]
    assert artifact_msgs == []
    assert len(store.saved) == 1
