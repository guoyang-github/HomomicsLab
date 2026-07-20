"""Tests for SkillGenesis — crystallizing validated CodeAct scripts into skills.

Covers:
- Candidate detection (post-fix success / accumulated signature successes).
- crystallize() producing a loadable SKILL.md + parameterized scripts.
- Notification-style registration: direct SkillStore import + notify, with no
  approval state machine.
- Community trust constraints, the intact trust-promotion path, and the undo
  channel (existing skill deletion API).
- De-duplication (a crystallized signature is never re-crystallized).
- The FeedbackRecorder hook wiring (always on, lazily built).
"""

import json
import logging

import pytest

from homomics_lab.agent.turn_feedback_recorder import FeedbackRecorder
from homomics_lab.knowledge.cbkb import CBKB
from homomics_lab.skills.genesis import (
    METRIC_CRYSTALLIZED,
    METRIC_SUCCESS,
    SkillGenesis,
    TaskSignature,
)
from homomics_lab.skills.loader import SkillLoader
from homomics_lab.skills.registry import SkillRegistry
from homomics_lab.skills.skill_store import SkillStore
from homomics_lab.skills.trust import TrustLevel, policy_for, resolve_trust_level
from homomics_lab.tasks.models import TaskNode, TaskStatus
from homomics_lab.tasks.task_tree import TaskTree

SAMPLE_CODE = (
    "import scanpy as sc\n"
    "adata = sc.read_h5ad('/data/workspaces/p1/inputs/sample.h5ad')\n"
    "adata.write('/data/workspaces/p1/outputs/result.h5ad')\n"
    "result = {'cells': int(adata.n_obs)}\n"
)

SAMPLE_PATHS = {
    "working_dir": "/data/workspaces/p1",
    "output_dir": "/data/workspaces/p1/outputs",
    "input_path": "/data/workspaces/p1/inputs/sample.h5ad",
}

DRAFT_JSON = json.dumps(
    {
        "name": "validated_qc_pipeline",
        "description": "QC pipeline drafted by the LLM.",
        "keywords": ["qc", "single-cell", "genesis"],
        "inputs": {
            "input_path": {"type": "string", "description": "Input h5ad file"},
            "output_dir": {"type": "string", "description": "Output directory"},
        },
        "outputs": {"result": {"type": "object", "description": "QC summary"}},
        "usage": "Adapt the reference script to your dataset.",
        "parameters": "- `input_path`: input file\n- `output_dir`: outputs",
        "notes": "- Review before production use",
    }
)


class FakeLLM:
    """Configurable fake LLM client for drafting tests."""

    def __init__(self, response=DRAFT_JSON, configured=True):
        self.response = response
        self.configured = configured
        self.calls = []

    def is_configured(self):
        return self.configured

    async def chat_completion(self, messages, **kwargs):
        self.calls.append(messages)
        return self.response


@pytest.fixture
def cbkb(tmp_path):
    return CBKB(base_dir=tmp_path)


@pytest.fixture
def skill_store(tmp_path):
    return SkillStore(
        registry=SkillRegistry(),
        store_dir=tmp_path / "store",
        skills_dir=tmp_path / "skills",
    )


@pytest.fixture
def notifications():
    return []


@pytest.fixture
def genesis(cbkb, skill_store, tmp_path, notifications):
    return SkillGenesis(
        cbkb=cbkb,
        skill_store=skill_store,
        llm_client=FakeLLM(),
        notify=lambda n: notifications.append(n),
        staging_dir=tmp_path / "staging",
        min_successes=3,
    )


async def _record(genesis, *, fixes=None, action="run qc", domain="single_cell"):
    return await genesis.record_execution(
        domain=domain,
        action=action,
        input_types=[".h5ad"],
        task_name="Run QC on sample",
        code=SAMPLE_CODE,
        success=True,
        fix_history=fixes or [],
        project_id="p1",
        paths=dict(SAMPLE_PATHS),
    )


# ─────────────────────────────────────────
# Candidate detection + notification-style registration
# ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_candidate_via_fix_history_registers_and_notifies(
    genesis, skill_store, notifications
):
    skill = await _record(genesis, fixes=[{"attempt": 1, "stderr": "boom"}])

    assert skill is not None
    assert skill.id.startswith("genesis_run_qc_")
    # Directly registered into the SkillStore — no approval step.
    assert skill_store.registry.get(skill.id) is not None
    assert (genesis.staging_dir / skill.id / "SKILL.md").exists()
    assert len(notifications) == 1
    note = notifications[0]
    assert note["kind"] == "skill_genesis_crystallized"
    assert note["skill_id"] == skill.id
    assert "已学会新技能" in note["message"]
    assert "1 次成功执行" in note["message"]
    assert "删除" in note["message"]  # undo channel is pointed out


@pytest.mark.asyncio
async def test_no_candidate_below_threshold(genesis):
    assert await _record(genesis) is None
    assert await _record(genesis) is None


@pytest.mark.asyncio
async def test_candidate_via_success_threshold(genesis, notifications):
    await _record(genesis)
    await _record(genesis)
    skill = await _record(genesis)
    assert skill is not None
    assert notifications[0]["success_count"] == 3
    assert notifications[0]["had_fixes"] is False
    assert "3 次成功执行" in notifications[0]["message"]


@pytest.mark.asyncio
async def test_failed_or_codeless_runs_are_ignored(genesis, cbkb):
    assert (
        await genesis.record_execution(
            domain="d", action="a", code=SAMPLE_CODE, success=False
        )
        is None
    )
    assert (
        await genesis.record_execution(domain="d", action="a", code="", success=True)
        is None
    )
    assert cbkb.query_parameter_lore_by_prefix("genesis:") == []


@pytest.mark.asyncio
async def test_no_approval_state_machine(genesis):
    # The HITL approval flow is gone: notification replaces approval.
    assert not hasattr(genesis, "approval_store")
    assert not hasattr(genesis, "propose")
    assert not hasattr(genesis, "finalize_resolved")


def test_signature_normalization():
    a = TaskSignature.build("Single Cell", "Run QC!", [".CSV", ".h5ad"])
    b = TaskSignature.build("single_cell", "run qc", [".h5ad", ".csv"])
    assert a.key() == b.key()
    assert a.hash() == b.hash()


# ─────────────────────────────────────────
# crystallize output
# ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_crystallize_produces_loadable_skill(genesis):
    skill = await _record(genesis, fixes=[{"attempt": 1, "stderr": "boom"}])
    package_dir = genesis.staging_dir / skill.id

    loaded = SkillLoader(registry=SkillRegistry()).load_skill(package_dir)

    assert loaded.id == skill.id
    assert loaded.description == "QC pipeline drafted by the LLM."
    assert loaded.metadata["trust_level"] == "community"
    assert loaded.runtime.type == "python"
    assert "input_path" in loaded.input_schema.properties
    assert "result" in loaded.output_schema.properties
    assert loaded.has_scripts

    script = (package_dir / "scripts" / "python" / "core_analysis.py").read_text(
        encoding="utf-8"
    )
    assert "/data/workspaces" not in script
    assert '"<OUTPUT_DIR>' in script or "<OUTPUT_DIR>" in script
    assert '"<INPUT_PATH>' in script or "<INPUT_PATH>" in script


@pytest.mark.asyncio
async def test_crystallize_uses_fallback_draft_without_llm(
    cbkb, skill_store, tmp_path
):
    g = SkillGenesis(
        cbkb=cbkb,
        skill_store=skill_store,
        llm_client=FakeLLM(configured=False),
        staging_dir=tmp_path / "staging",
    )
    skill = await _record(g, fixes=[{"attempt": 1, "stderr": "boom"}])
    package_dir = g.staging_dir / skill.id

    content = (package_dir / "SKILL.md").read_text(encoding="utf-8")
    assert "crystallized from a repeatedly validated CodeAct script" in content
    loaded = SkillLoader(registry=SkillRegistry()).load_skill(package_dir)
    assert loaded.metadata["trust_level"] == "community"


@pytest.mark.asyncio
async def test_invalid_llm_draft_falls_back(cbkb, skill_store, tmp_path):
    g = SkillGenesis(
        cbkb=cbkb,
        skill_store=skill_store,
        llm_client=FakeLLM(response="not json at all"),
        staging_dir=tmp_path / "staging",
    )
    skill = await _record(g, fixes=[{"attempt": 1, "stderr": "boom"}])
    content = (g.staging_dir / skill.id / "SKILL.md").read_text(encoding="utf-8")
    assert "crystallized from a repeatedly validated CodeAct script" in content


# ─────────────────────────────────────────
# Trust model + undo channel
# ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_registers_community_skill(genesis, skill_store, cbkb):
    skill = await _record(genesis, fixes=[{"attempt": 1, "stderr": "boom"}])

    registered = skill_store.registry.get(skill.id)
    assert registered is not None
    level = resolve_trust_level(registered)
    assert level is TrustLevel.COMMUNITY
    # Community trust constraints from the existing trust model apply.
    policy = policy_for(level, interactive=False)
    assert policy.can_execute is True
    assert policy.allow_local_sandbox is False
    assert policy.require_hitl is False
    assert policy.use_code_cache is True

    # CBKB knowledge: task signature -> crystallized skill.
    entries = cbkb.query_parameter_lore_by_prefix("genesis:")
    crystallized = [e for e in entries if e.outcome_metric == METRIC_CRYSTALLIZED]
    assert len(crystallized) == 1
    assert crystallized[0].param_value == skill.id


@pytest.mark.asyncio
async def test_trust_promotion_path_remains_intact(genesis, skill_store):
    skill = await _record(genesis, fixes=[{"attempt": 1, "stderr": "boom"}])

    # The standard SkillStore.trust_skill promotion path is not bypassed:
    # trusting a genesis skill clears the explicit community level and the
    # skill resolves through the normal source+trusted rules.
    promoted = skill_store.trust_skill(
        skill.id, trusted=True, namespace="community"
    )
    assert resolve_trust_level(promoted) is TrustLevel.VERIFIED
    assert policy_for(resolve_trust_level(promoted)).allow_local_sandbox is True


@pytest.mark.asyncio
async def test_undo_via_existing_skill_deletion(genesis, skill_store):
    skill = await _record(genesis, fixes=[{"attempt": 1, "stderr": "boom"}])
    assert skill_store.registry.get(skill.id) is not None

    # The undo channel is the existing skill deletion API surface
    # (DELETE /api/skills/{skill_id} -> SkillStore.remove_skill).
    skill_store.remove_skill(skill.id, namespace="community")
    assert skill_store.registry.get(skill.id) is None


@pytest.mark.asyncio
async def test_crystallized_signature_is_never_recrystallized(genesis, notifications):
    first = await _record(genesis, fixes=[{"attempt": 1, "stderr": "boom"}])
    assert first is not None
    # Same signature keeps succeeding: never crystallized again.
    for _ in range(5):
        assert await _record(genesis, fixes=[{"attempt": 2, "stderr": "again"}]) is None
    assert len(notifications) == 1


# ─────────────────────────────────────────
# SkillDAG coordination
# ─────────────────────────────────────────


class RecordingDAG:
    def __init__(self):
        self.edges = []

    def propose_edge(
        self, from_skill, to_skill, edge_type, context="", proposed_by="system"
    ):
        self.edges.append((from_skill, to_skill, edge_type.value, proposed_by))


@pytest.mark.asyncio
async def test_crystallized_skill_links_origin_in_dag(cbkb, skill_store, tmp_path):
    dag = RecordingDAG()
    g = SkillGenesis(
        cbkb=cbkb,
        skill_store=skill_store,
        skill_dag=dag,
        llm_client=FakeLLM(),
        staging_dir=tmp_path / "staging",
    )
    skill = await g.record_execution(
        domain="single_cell",
        action="run qc",
        input_types=[".h5ad"],
        task_name="Run QC",
        code=SAMPLE_CODE,
        success=True,
        fix_history=[{"attempt": 1, "stderr": "boom"}],
        origin_skill="broken_builtin_qc",
        paths=dict(SAMPLE_PATHS),
    )

    assert dag.edges == [
        ("broken_builtin_qc", skill.id, "alternative_to", "skill_genesis")
    ]


# ─────────────────────────────────────────
# FeedbackRecorder hook
# ─────────────────────────────────────────


class RecordingGenesis:
    def __init__(self):
        self.calls = []

    async def record_execution(self, **kwargs):
        self.calls.append(kwargs)
        return None


@pytest.mark.asyncio
async def test_feedback_recorder_forwards_codeact_success(tmp_path):
    input_file = tmp_path / "sample.h5ad"
    input_file.write_text("fake")
    genesis = RecordingGenesis()
    recorder = FeedbackRecorder(skill_genesis=genesis)

    task = TaskNode(
        id="t1",
        name="Run QC",
        description="Run QC on sample",
        phase="qc",
        status=TaskStatus.COMPLETED,
        parameters={"input_path": str(input_file)},
        skills_required=["broken_skill"],
    )
    tree = TaskTree(tasks=[task])
    results = {
        "t1": {
            "status": "success",
            "code": SAMPLE_CODE,
            "fix_history": [{"attempt": 1, "stderr": "boom"}],
            "fallback": True,
        }
    }

    await recorder.record_execution_feedback(tree, results, "p1")

    assert len(genesis.calls) == 1
    call = genesis.calls[0]
    assert call["code"] == SAMPLE_CODE
    assert call["domain"] == "qc"
    assert call["fix_history"] == [{"attempt": 1, "stderr": "boom"}]
    assert call["origin_skill"] == "broken_skill"
    assert ".h5ad" in call["input_types"]
    assert call["paths"]["input_path"] == str(input_file)


@pytest.mark.asyncio
async def test_feedback_recorder_ignores_non_codeact_results():
    genesis = RecordingGenesis()
    recorder = FeedbackRecorder(skill_genesis=genesis)
    task = TaskNode(
        id="t1",
        name=" curated ",
        description="curated skill task",
        status=TaskStatus.COMPLETED,
        skills_required=["curated_skill"],
    )
    tree = TaskTree(tasks=[task])
    # Curated skill results carry no generated "code".
    await recorder.record_execution_feedback(
        tree, {"t1": {"status": "success", "result": {}}}, "p1"
    )
    assert genesis.calls == []


@pytest.mark.asyncio
async def test_feedback_recorder_builds_genesis_by_default(monkeypatch):
    # Genesis is always on: a default recorder lazily builds the service and
    # wires the session-chat notification channel into it.
    from homomics_lab.agent import turn_feedback_recorder as recorder_module

    sentinel = object()
    captured = {}

    def _from_settings(cls, skill_dag=None, notify=None):
        captured["notify"] = notify
        return sentinel

    monkeypatch.setattr(
        "homomics_lab.skills.genesis.SkillGenesis.from_settings",
        classmethod(_from_settings),
    )
    recorder = FeedbackRecorder()
    assert recorder._get_skill_genesis() is sentinel
    assert captured["notify"] is recorder_module._notify_genesis_crystallized


@pytest.mark.asyncio
async def test_feedback_recorder_genesis_build_failure_degrades(
    monkeypatch, caplog
):
    def _boom(cls, skill_dag=None, notify=None):
        raise RuntimeError("no fs")

    monkeypatch.setattr(
        "homomics_lab.skills.genesis.SkillGenesis.from_settings",
        classmethod(_boom),
    )
    recorder = FeedbackRecorder()
    with caplog.at_level(logging.WARNING):
        assert recorder._get_skill_genesis() is None
    assert "Failed to initialize SkillGenesis" in caplog.text


@pytest.mark.asyncio
async def test_lore_success_rows_accumulate(genesis, cbkb):
    # Sanity check on the counting foundation.
    await _record(genesis)
    await _record(genesis)
    entries = [
        e
        for e in cbkb.query_parameter_lore_by_prefix("genesis:")
        if e.outcome_metric == METRIC_SUCCESS
    ]
    assert len(entries) == 2


# ─────────────────────────────────────────
# Notification channel (session chat)
# ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_notification_reaches_session_chat(
    tmp_path, cbkb, skill_store, monkeypatch
):
    """End-to-end: a crystallization notice lands in the project's chat session.

    The recorder-level notify channel appends an agent message to the most
    recently updated session of the project in the shared SessionStore.
    """
    from datetime import datetime, timezone

    from homomics_lab.agent.turn_feedback_recorder import (
        _notify_genesis_crystallized,
    )
    from homomics_lab.config import settings
    from homomics_lab.context.session_store import (
        SessionState,
        create_session_store_from_settings,
    )
    from homomics_lab.context.working_memory import WorkingMemory

    db_path = tmp_path / "sessions.db"
    monkeypatch.setattr(
        settings, "session_store_url", f"sqlite+aiosqlite:///{db_path}"
    )

    # Seed the session a real turn would have created for project p1.
    store = create_session_store_from_settings()
    await store.init()
    await store.save(
        SessionState(
            session_id="s1",
            project_id="p1",
            working_memory=WorkingMemory(),
            task_tree=None,
            updated_at=datetime.now(timezone.utc),
        )
    )

    g = SkillGenesis(
        cbkb=cbkb,
        skill_store=skill_store,
        llm_client=FakeLLM(),
        notify=_notify_genesis_crystallized,
        staging_dir=tmp_path / "staging",
        min_successes=3,
    )
    skill = await _record(g, fixes=[{"attempt": 1, "stderr": "boom"}])
    assert skill is not None

    # Re-open the store with a fresh connection and read the session back.
    stored = await create_session_store_from_settings().get("s1")
    assert stored is not None
    notes = [
        m
        for m in stored.working_memory.messages
        if m.id == f"msg_genesis_{skill.id}"
    ]
    assert len(notes) == 1
    note = notes[0]
    assert note.sender == "agent"
    assert f"已学会新技能 '{skill.id}'" in note.content
    assert "1 次成功执行" in note.content
    assert "经自我修复后验证通过" in note.content
    assert "community 信任级别" in note.content
    assert "删除" in note.content


@pytest.mark.asyncio
async def test_notification_without_session_degrades_to_log(
    tmp_path, monkeypatch, caplog
):
    """No session for the project: the notice is logged, never raised."""
    from homomics_lab.agent.turn_feedback_recorder import (
        _notify_genesis_crystallized,
    )
    from homomics_lab.config import settings

    monkeypatch.setattr(
        settings, "session_store_url", f"sqlite+aiosqlite:///{tmp_path}/sessions.db"
    )
    with caplog.at_level(logging.INFO):
        await _notify_genesis_crystallized(
            {
                "kind": "skill_genesis_crystallized",
                "skill_id": "genesis_x",
                "project_id": "no_such_project",
                "message": "已学会新技能 'genesis_x'",
            }
        )
    assert "已学会新技能 'genesis_x'" in caplog.text
