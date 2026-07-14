"""Tests for the skill-level HITL true gate (G1).

Covers:
- EXPERIMENTAL skills pause before dispatch until approved.
- Approval persistence via PersistentApprovalStore.
- Cache hits are gated by approval as well.
- Non-interactive mode still raises UntrustedSkillError.
"""

import pytest

from homomics_lab.config import settings
from homomics_lab.skills.loader import SkillLoader
from homomics_lab.skills.registry import SkillRegistry
from homomics_lab.skills.runtime import SkillRuntimeExecutor, UntrustedSkillError
from homomics_lab.tools.approval_store import PersistentApprovalStore


@pytest.fixture
def experimental_skill_dir(tmp_path):
    skill_dir = tmp_path / "experimental-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        """\
---
name: experimental-skill
description: An experimental skill for HITL gate testing.
tool_type: python
---

# Instructions
Return the doubled value.
""",
        encoding="utf-8",
    )
    scripts = skill_dir / "scripts" / "python"
    scripts.mkdir(parents=True)
    (scripts / "run.py").write_text("result = {'doubled': value * 2}\n")
    return skill_dir


class RecordingScheduler:
    """Fake scheduler that records whether it was called."""

    def __init__(self, response=None):
        self.calls = []
        self.response = response or {"ok": True}

    async def execute(
        self,
        skill,
        code,
        inputs,
        timeout_seconds=None,
        parent_job_id=None,
        allow_local_sandbox=False,
    ):
        self.calls.append({
            "skill_id": skill.id,
            "inputs": inputs,
            "allow_local_sandbox": allow_local_sandbox,
        })
        return dict(self.response)


def build_executor(
    skill_dir,
    tmp_path,
    monkeypatch,
    interactive=True,
    cache_enabled=False,
):
    monkeypatch.setattr(settings, "interactive_mode", interactive)
    if cache_enabled:
        monkeypatch.setattr(settings, "skill_cache_enabled", True)
        monkeypatch.setattr(settings, "skill_cache_dir", tmp_path / "skill_cache")
    else:
        monkeypatch.setattr(settings, "skill_cache_enabled", False)

    registry = SkillRegistry()
    loader = SkillLoader(registry=registry)
    skill = loader.load_discovery(skill_dir)
    skill.metadata["source"] = "external"
    skill.metadata["trusted"] = False
    registry.register(skill)

    approval_store = PersistentApprovalStore(db_path=tmp_path / "approvals.db")
    executor = SkillRuntimeExecutor(
        registry=registry,
        working_dir=tmp_path,
        approval_store=approval_store,
    )
    executor.cache = None if not cache_enabled else executor.cache
    scheduler = RecordingScheduler(response={"doubled": "executed"})
    executor._scheduler = scheduler
    return executor, scheduler, approval_store


@pytest.mark.asyncio
async def test_experimental_skill_returns_hitl_checkpoint(
    experimental_skill_dir, tmp_path, monkeypatch
):
    executor, scheduler, _ = build_executor(
        experimental_skill_dir, tmp_path, monkeypatch, interactive=True
    )

    result = await executor.execute(
        "experimental-skill", {"value": 5, "_approval_call_id": "call-1"}
    )

    assert result["status"] == "awaiting_human"
    assert result["success"] is False
    assert result["mode"] == "awaiting_skill_approval"
    assert result["skill_id"] == "experimental-skill"
    assert result["hitl"]["task_id"] == "call-1"
    checkpoint = result["hitl"]["checkpoint"]
    assert checkpoint["trigger_reason"] == "policy"
    option_ids = {opt["id"] for opt in checkpoint["options"]}
    assert option_ids == {"approve", "decline"}
    assert checkpoint["context_summary"]
    assert "experimental" in checkpoint["context_summary"]
    assert scheduler.calls == []


@pytest.mark.asyncio
async def test_experimental_skill_runs_after_approval(
    experimental_skill_dir, tmp_path, monkeypatch
):
    executor, scheduler, approval_store = build_executor(
        experimental_skill_dir, tmp_path, monkeypatch, interactive=True
    )

    pending = await executor.execute(
        "experimental-skill", {"value": 5, "_approval_call_id": "call-2"}
    )
    assert pending["hitl"]["task_id"] == "call-2"
    approval_store.approve("call-2")

    result = await executor.execute(
        "experimental-skill", {"value": 5, "_approval_call_id": "call-2"}
    )

    assert result["doubled"] == "executed"
    assert result["trust_level"] == "experimental"
    assert result["hitl_required"] is True
    assert result["hitl_approved"] is True
    assert len(scheduler.calls) == 1


@pytest.mark.asyncio
async def test_experimental_skill_stays_pending_without_approval(
    experimental_skill_dir, tmp_path, monkeypatch
):
    executor, scheduler, _ = build_executor(
        experimental_skill_dir, tmp_path, monkeypatch, interactive=True
    )

    for _ in range(3):
        result = await executor.execute(
            "experimental-skill", {"value": 5, "_approval_call_id": "call-3"}
        )
        assert result["status"] == "awaiting_human"
        assert result["success"] is False
        assert result["hitl"]["task_id"] == "call-3"

    assert scheduler.calls == []


@pytest.mark.asyncio
async def test_experimental_skill_rejected_non_interactive(
    experimental_skill_dir, tmp_path, monkeypatch
):
    executor, _, _ = build_executor(
        experimental_skill_dir, tmp_path, monkeypatch, interactive=False
    )

    with pytest.raises(UntrustedSkillError, match="experimental"):
        await executor.execute("experimental-skill", {"value": 5})


@pytest.mark.asyncio
async def test_experimental_skill_cache_gated_by_approval(
    experimental_skill_dir, tmp_path, monkeypatch
):
    executor, scheduler, approval_store = build_executor(
        experimental_skill_dir, tmp_path, monkeypatch, interactive=True, cache_enabled=True
    )

    # First call is not approved -> no execution, no cache write.
    pending = await executor.execute(
        "experimental-skill", {"value": 7, "_approval_call_id": "call-4"}
    )
    assert pending["status"] == "awaiting_human"
    assert scheduler.calls == []

    approval_store.approve("call-4")

    # Second call executes and caches.
    result = await executor.execute(
        "experimental-skill", {"value": 7, "_approval_call_id": "call-4"}
    )
    assert result["doubled"] == "executed"
    assert result["hitl_approved"] is True
    assert len(scheduler.calls) == 1

    # Third call is still approved -> cache hit, no extra scheduler call.
    cached = await executor.execute(
        "experimental-skill", {"value": 7, "_approval_call_id": "call-4"}
    )
    assert cached["doubled"] == "executed"
    assert cached["hitl_approved"] is True
    assert len(scheduler.calls) == 1
