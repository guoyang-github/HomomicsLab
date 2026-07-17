"""Tests for SkillGenesis — crystallizing validated CodeAct scripts into skills.

Covers:
- Candidate detection (post-fix success / accumulated signature successes).
- crystallize() producing a loadable SKILL.md + parameterized scripts.
- HITL approve / reject paths via PersistentApprovalStore.
- Community trust constraints and the intact trust-promotion path.
- De-duplication (pending / rejected signatures are never re-proposed).
- The FeedbackRecorder hook wiring.
"""

import json

import pytest

from homomics_lab.agent.turn_feedback_recorder import FeedbackRecorder
from homomics_lab.knowledge.cbkb import CBKB
from homomics_lab.skills.genesis import (
    METRIC_CRYSTALLIZED,
    METRIC_REJECTED,
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
from homomics_lab.tools.approval_store import PersistentApprovalStore

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
def approval_store(tmp_path):
    return PersistentApprovalStore(db_path=tmp_path / "approvals.db")


@pytest.fixture
def notifications():
    return []


@pytest.fixture
def genesis(cbkb, skill_store, approval_store, tmp_path, notifications):
    return SkillGenesis(
        cbkb=cbkb,
        skill_store=skill_store,
        approval_store=approval_store,
        llm_client=FakeLLM(),
        notify=lambda n: notifications.append(n),
        staging_dir=tmp_path / "staging",
        min_successes=3,
        enabled=True,
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
# Candidate detection
# ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_candidate_via_fix_history(genesis, approval_store, notifications):
    proposal = await _record(genesis, fixes=[{"attempt": 1, "stderr": "boom"}])

    assert proposal is not None
    assert proposal.skill_id.startswith("genesis_run_qc_")
    assert approval_store.get(proposal.call_id) is not None
    assert (proposal.package_dir / "SKILL.md").exists()
    assert len(notifications) == 1
    assert "待确认" in notifications[0]["message"]


@pytest.mark.asyncio
async def test_no_candidate_below_threshold(genesis):
    assert await _record(genesis) is None
    assert await _record(genesis) is None


@pytest.mark.asyncio
async def test_candidate_via_success_threshold(genesis):
    await _record(genesis)
    await _record(genesis)
    proposal = await _record(genesis)
    assert proposal is not None
    assert proposal.candidate.success_count == 3
    assert proposal.candidate.had_fixes is False


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
async def test_disabled_genesis_records_nothing(
    cbkb, skill_store, approval_store, tmp_path
):
    g = SkillGenesis(
        cbkb=cbkb,
        skill_store=skill_store,
        approval_store=approval_store,
        staging_dir=tmp_path / "staging",
        enabled=False,
    )
    proposal = await g.record_execution(
        domain="d",
        action="a",
        code=SAMPLE_CODE,
        success=True,
        fix_history=[{"attempt": 1, "stderr": "x"}],
    )
    assert proposal is None
    assert cbkb.query_parameter_lore_by_prefix("genesis:") == []


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
    proposal = await _record(genesis, fixes=[{"attempt": 1, "stderr": "boom"}])

    skill = SkillLoader(registry=SkillRegistry()).load_skill(proposal.package_dir)

    assert skill.id == proposal.skill_id
    assert skill.description == "QC pipeline drafted by the LLM."
    assert skill.metadata["trust_level"] == "community"
    assert skill.runtime.type == "python"
    assert "input_path" in skill.input_schema.properties
    assert "result" in skill.output_schema.properties
    assert skill.has_scripts

    script = (
        proposal.package_dir / "scripts" / "python" / "core_analysis.py"
    ).read_text(encoding="utf-8")
    assert "/data/workspaces" not in script
    assert '"<OUTPUT_DIR>' in script or "<OUTPUT_DIR>" in script
    assert '"<INPUT_PATH>' in script or "<INPUT_PATH>" in script


@pytest.mark.asyncio
async def test_crystallize_uses_fallback_draft_without_llm(
    cbkb, skill_store, approval_store, tmp_path
):
    g = SkillGenesis(
        cbkb=cbkb,
        skill_store=skill_store,
        approval_store=approval_store,
        llm_client=FakeLLM(configured=False),
        staging_dir=tmp_path / "staging",
        enabled=True,
    )
    proposal = await _record(g, fixes=[{"attempt": 1, "stderr": "boom"}])

    content = (proposal.package_dir / "SKILL.md").read_text(encoding="utf-8")
    assert "crystallized from a repeatedly validated CodeAct script" in content
    skill = SkillLoader(registry=SkillRegistry()).load_skill(proposal.package_dir)
    assert skill.metadata["trust_level"] == "community"


@pytest.mark.asyncio
async def test_invalid_llm_draft_falls_back(
    cbkb, skill_store, approval_store, tmp_path
):
    g = SkillGenesis(
        cbkb=cbkb,
        skill_store=skill_store,
        approval_store=approval_store,
        llm_client=FakeLLM(response="not json at all"),
        staging_dir=tmp_path / "staging",
        enabled=True,
    )
    proposal = await _record(g, fixes=[{"attempt": 1, "stderr": "boom"}])
    content = (proposal.package_dir / "SKILL.md").read_text(encoding="utf-8")
    assert "crystallized from a repeatedly validated CodeAct script" in content


# ─────────────────────────────────────────
# HITL paths
# ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_approve_registers_community_skill(
    genesis, skill_store, approval_store, cbkb
):
    proposal = await _record(genesis, fixes=[{"attempt": 1, "stderr": "boom"}])
    approval_store.approve(proposal.call_id)

    registered = await genesis.finalize_resolved()

    assert [s.id for s in registered] == [proposal.skill_id]
    skill = skill_store.registry.get(proposal.skill_id)
    assert skill is not None
    level = resolve_trust_level(skill)
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
    assert crystallized[0].param_value == proposal.skill_id


@pytest.mark.asyncio
async def test_trust_promotion_path_remains_intact(
    genesis, skill_store, approval_store
):
    proposal = await _record(genesis, fixes=[{"attempt": 1, "stderr": "boom"}])
    approval_store.approve(proposal.call_id)
    await genesis.finalize_resolved()

    # The standard SkillStore.trust_skill promotion path is not bypassed:
    # trusting a genesis skill clears the explicit community level and the
    # skill resolves through the normal source+trusted rules.
    promoted = skill_store.trust_skill(
        proposal.skill_id, trusted=True, namespace="community"
    )
    assert resolve_trust_level(promoted) is TrustLevel.VERIFIED
    assert policy_for(resolve_trust_level(promoted)).allow_local_sandbox is True


@pytest.mark.asyncio
async def test_reject_records_and_never_reproposes(genesis, approval_store, cbkb):
    proposal = await _record(genesis, fixes=[{"attempt": 1, "stderr": "boom"}])
    approval_store.reject(proposal.call_id)

    registered = await genesis.finalize_resolved()

    assert registered == []
    entries = cbkb.query_parameter_lore_by_prefix("genesis:")
    assert any(e.outcome_metric == METRIC_REJECTED for e in entries)
    assert approval_store.list_pending() == []

    # Same signature keeps succeeding: never proposed again.
    for _ in range(5):
        assert await _record(genesis, fixes=[{"attempt": 1, "stderr": "boom"}]) is None
    assert approval_store.list_pending() == []


@pytest.mark.asyncio
async def test_pending_proposal_is_not_duplicated(genesis, approval_store):
    first = await _record(genesis, fixes=[{"attempt": 1, "stderr": "boom"}])
    second = await _record(genesis, fixes=[{"attempt": 2, "stderr": "boom again"}])

    assert first is not None
    assert second is None
    assert len(approval_store.list_pending()) == 1


@pytest.mark.asyncio
async def test_finalize_is_picked_up_on_next_execution(
    genesis, approval_store, skill_store
):
    proposal = await _record(genesis, fixes=[{"attempt": 1, "stderr": "boom"}])
    approval_store.approve(proposal.call_id)

    # A subsequent, unrelated execution finalizes the earlier decision.
    await genesis.record_execution(
        domain="other",
        action="different task",
        code="result = {}",
        success=True,
    )
    assert skill_store.registry.get(proposal.skill_id) is not None


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
async def test_crystallized_skill_links_origin_in_dag(
    cbkb, skill_store, approval_store, tmp_path
):
    dag = RecordingDAG()
    g = SkillGenesis(
        cbkb=cbkb,
        skill_store=skill_store,
        approval_store=approval_store,
        skill_dag=dag,
        llm_client=FakeLLM(),
        staging_dir=tmp_path / "staging",
        enabled=True,
    )
    proposal = await g.record_execution(
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
    approval_store.approve(proposal.call_id)
    await g.finalize_resolved()

    assert dag.edges == [
        ("broken_builtin_qc", proposal.skill_id, "alternative_to", "skill_genesis")
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
async def test_feedback_recorder_genesis_disabled_by_default():
    recorder = FeedbackRecorder()
    assert recorder._get_skill_genesis() is None


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
