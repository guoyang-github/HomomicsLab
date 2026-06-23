"""Tests for the ContextEngine and supporting components."""

import pytest

from homomics_lab.context import (
    ContextEngine,
    ProjectStateManager,
    TokenBudgetManager,
    WorkingMemory,
)
from homomics_lab.context.context_engine.models import ContextSource
from homomics_lab.context.context_engine.ranker import ContextRanker
from homomics_lab.knowledge.cbkb import CBKB
from homomics_lab.models.common import ChatMessage, MessageType
from homomics_lab.secrets import reset_secrets_manager


@pytest.fixture(autouse=True)
def isolate_secrets(tmp_path, monkeypatch):
    # Prevent any persisted runtime LLM config (e.g. from local dev) from
    # leaking into these unit tests.
    reset_secrets_manager()
    monkeypatch.setattr("homomics_lab.config.settings.data_dir", tmp_path)
    monkeypatch.setattr("homomics_lab.config.settings.secrets_master_key", "test-key")
    yield
    reset_secrets_manager()


@pytest.fixture
def tmp_cbkb(tmp_path):
    return CBKB(base_dir=tmp_path)


@pytest.fixture
def context_engine(tmp_cbkb):
    return ContextEngine(cbkb=tmp_cbkb)


@pytest.fixture
def working_memory():
    wm = WorkingMemory(max_messages=5)
    wm.add_message(ChatMessage(id="1", type=MessageType.TEXT, content="Hello", sender="user"))
    wm.add_message(
        ChatMessage(
            id="2",
            type=MessageType.TEXT,
            content="How can I analyze my single-cell data?",
            sender="user",
        )
    )
    return wm


@pytest.mark.asyncio
async def test_context_engine_builds_messages(context_engine, working_memory):
    bundle = await context_engine.build(
        user_message="Run QC",
        working_memory=working_memory,
        project_id="proj_test",
        model="default",
        reserved_output_tokens=1000,
    )
    assert len(bundle.messages) >= 2
    roles = {m["role"] for m in bundle.messages}
    assert "system" in roles
    assert "user" in roles
    assert bundle.metadata["used_tokens"] > 0
    assert bundle.metadata["used_tokens"] <= bundle.metadata["input_budget"]


@pytest.mark.asyncio
async def test_context_engine_includes_project_state(context_engine, tmp_cbkb, working_memory):
    manager = ProjectStateManager(tmp_cbkb)
    state = manager.load("proj_state")
    state.completed_phases = ["qc"]
    state.pending_phases = ["clustering"]
    manager.save(state)

    bundle = await context_engine.build(
        user_message="What is next?",
        working_memory=working_memory,
        project_id="proj_state",
        model="default",
        reserved_output_tokens=1000,
    )
    system_content = bundle.system_content
    assert "qc" in system_content
    assert "clustering" in system_content


@pytest.mark.asyncio
async def test_context_engine_respects_budget(tmp_cbkb, working_memory):
    # Tight budget should still produce a valid bundle for a normal user message.
    engine = ContextEngine(cbkb=tmp_cbkb)
    bundle = await engine.build(
        user_message="Run QC and clustering",
        working_memory=working_memory,
        project_id="proj_budget",
        model="gpt-4o",
        reserved_output_tokens=126_000,
    )
    assert bundle.metadata["used_tokens"] <= bundle.metadata["input_budget"]


def test_token_budget_manager_counts():
    manager = TokenBudgetManager(model="default", output_reserve_tokens=1000)
    text = "This is a short sentence."
    tokens = manager.count(text)
    assert tokens > 0
    assert manager.available_input_tokens() == 7000


def test_context_ranker_prefers_project_state():
    ranker = ContextRanker()
    parts = [
        _make_part("some chat", ContextSource.CHAT),
        _make_part("project state info", ContextSource.PROJECT_STATE),
        _make_part("cbkb info", ContextSource.CBKB),
    ]
    ranked = ranker.rank(parts, query="what is the project status")
    assert ranked[0].source == ContextSource.PROJECT_STATE


def _make_part(content, source):
    from homomics_lab.context.context_engine.models import ContextPart

    return ContextPart(content=content, source=source)
