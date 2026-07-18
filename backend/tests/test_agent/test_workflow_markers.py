"""Tests for domain workflow DAG events on the CodeAct path.

Covers the marker convention injection, stdout marker parsing, the
``workflow_skeleton`` / ``phase`` progress events, trace mirroring, and the
generic-task zero-injection / zero-event guarantee.  LLM and sandbox are
mocked: ``run_code_act`` is patched at the executor module boundary.
"""

import pytest
import yaml
from pathlib import Path

from homomics_lab.agent.agent_registry import AgentRegistry
from homomics_lab.agent.base_agent import BaseAgent
from homomics_lab.agent.orchestrator import Orchestrator
from homomics_lab.agent.task_decomposer import TaskDecomposer
from homomics_lab.agent.workflow_markers import (
    MAX_CONVENTION_CHARS,
    build_marker_convention,
    extract_domain_pipeline,
    parse_marker_line,
    scan_marker_lines,
)
from homomics_lab.agent.plan.models import DataState, Phase, PlanResult
from homomics_lab.agent.intent_analyzer import UserIntent
from homomics_lab.config import settings
from homomics_lab.hpc.state import ExecutionState
from homomics_lab.jobs.runner import BackgroundJobRunner
from homomics_lab.models.common import AgentType
from homomics_lab.skills.models import SkillDefinition, SkillInputSchema
from homomics_lab.skills.registry import SkillRegistry
from homomics_lab.tasks.models import RetryPolicy, TaskNode

DOMAIN = "single-cell-transcriptomics"
PIPELINE = [
    {"phase_type": "qc", "name": "Quality Control"},
    {"phase_type": "normalization", "name": "Normalization"},
    {"phase_type": "clustering", "name": "Clustering"},
]


def _domain_task(**param_overrides) -> TaskNode:
    parameters = {"domain": DOMAIN, "domain_phases": PIPELINE}
    parameters.update(param_overrides)
    return TaskNode(
        id="t1",
        name="qc",
        description="Quality control",
        phase="qc",
        parameters=parameters,
        retry_policy=RetryPolicy(max_attempts=1, backoff_seconds=0.0),
    )


@pytest.fixture
def states():
    return []


@pytest.fixture
def orchestrator(states):
    return Orchestrator(
        registry=AgentRegistry(),
        skill_registry=SkillRegistry(),
        progress_callback=states.append,
    )


@pytest.fixture
def executors(orchestrator):
    return orchestrator._executors


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    return tmp_path


def _workflow_events(states):
    return [s for s in states if s.extra]


# ----------------------------------------------------------------------
# Pure marker parsing
# ----------------------------------------------------------------------


def test_parse_marker_start():
    assert parse_marker_line("__homomics_phase__:qc:start") == ("qc", "start", {})


def test_parse_marker_done_with_params():
    phase, status, params = parse_marker_line(
        '__homomics_phase__:normalization:done:{"target_sum": 10000, "log1p": true}'
    )
    assert (phase, status) == ("normalization", "done")
    assert params == {"target_sum": 10000, "log1p": True}


def test_parse_marker_failed_with_params():
    phase, status, params = parse_marker_line(
        '__homomics_phase__:clustering:failed:{"error": "boom"}'
    )
    assert (phase, status) == ("clustering", "failed")
    assert params == {"error": "boom"}


def test_parse_marker_bad_json_silent():
    phase, status, params = parse_marker_line("__homomics_phase__:qc:done:{not json")
    assert (phase, status) == ("qc", "done")
    assert params == {}


def test_parse_marker_non_dict_json_silent():
    phase, status, params = parse_marker_line("__homomics_phase__:qc:done:[1, 2]")
    assert (phase, status) == ("qc", "done")
    assert params == {}


def test_parse_marker_rejects_non_marker_lines():
    assert parse_marker_line("print('hello')") is None
    assert parse_marker_line("prefix __homomics_phase__:qc:start") is None
    assert parse_marker_line("__homomics_phase__:qc:start trailing") is None
    assert parse_marker_line("__homomics_phase__:qc:unknown") is None
    assert parse_marker_line("") is None


def test_scan_marker_lines_mixed_output():
    text = (
        "loading data...\n"
        "__homomics_phase__:qc:start\n"
        "cells: 2700\n"
        '__homomics_phase__:qc:done:{"min_genes": 200}\n'
        "done\n"
    )
    markers = scan_marker_lines(text)
    assert markers == [
        ("qc", "start", {}),
        ("qc", "done", {"min_genes": 200}),
    ]


# ----------------------------------------------------------------------
# Convention text (prompt injection budget)
# ----------------------------------------------------------------------


def test_convention_lists_phases_in_order():
    text = build_marker_convention(PIPELINE)
    assert "__homomics_phase__" in text
    assert "qc, normalization, clustering" in text
    assert "best effort" in text
    assert len(text) <= MAX_CONVENTION_CHARS


def test_convention_stays_within_budget_for_long_pipelines():
    phases = [
        {"phase_type": f"phase_number_{i}", "name": f"Phase {i}"} for i in range(30)
    ]
    text = build_marker_convention(phases)
    assert len(text) <= MAX_CONVENTION_CHARS
    assert "__homomics_phase__" in text


# ----------------------------------------------------------------------
# Domain pipeline extraction (injection gate)
# ----------------------------------------------------------------------


def test_extract_domain_pipeline_from_stamped_phases():
    task = _domain_task()
    domain, phases = extract_domain_pipeline(task)
    assert domain == DOMAIN
    assert [p["phase_type"] for p in phases] == ["qc", "normalization", "clustering"]


def test_extract_returns_none_without_domain():
    task = TaskNode(id="t", name="x", description="x", parameters={})
    assert extract_domain_pipeline(task) is None


@pytest.mark.parametrize("generic", ["generic", "general", "builtin", "Generic"])
def test_extract_returns_none_for_generic_domains(generic):
    task = _domain_task(domain=generic)
    assert extract_domain_pipeline(task) is None


def test_extract_falls_back_to_display_subtasks():
    task = _domain_task(
        domain_phases=None,
        display_subtasks=[
            {"id": "annotate", "description": "Annotate cell types"},
            {"id": "compare", "description": "Compare with existing labels"},
        ],
    )
    # parameters value None is not a valid list; drop the key entirely.
    task.parameters.pop("domain_phases")
    domain, phases = extract_domain_pipeline(task)
    assert domain == DOMAIN
    assert [p["phase_type"] for p in phases] == ["annotate", "compare"]
    assert phases[0]["name"] == "Annotate cell types"


def test_extract_falls_back_to_own_phase():
    task = _domain_task()
    task.parameters.pop("domain_phases")
    domain, phases = extract_domain_pipeline(task)
    assert domain == DOMAIN
    assert phases == [{"phase_type": "qc", "name": "Quality control"}]


def test_extract_returns_none_when_no_phase_info():
    task = _domain_task()
    task.parameters.pop("domain_phases")
    task.phase = "execution"
    assert extract_domain_pipeline(task) is None


# ----------------------------------------------------------------------
# Prompt injection
# ----------------------------------------------------------------------


def test_fallback_prompt_injects_convention_for_domain_task(executors):
    prompt = executors._fallback_task_prompt(_domain_task())
    assert "__homomics_phase__" in prompt
    assert "qc, normalization, clustering" in prompt


def test_fallback_prompt_zero_injection_for_generic_task(executors):
    task = _domain_task(domain="generic")
    prompt = executors._fallback_task_prompt(task)
    assert "__homomics_phase__" not in prompt


def test_skill_reference_prompt_injects_convention(executors, workspace):
    task = _domain_task(use_skill_reference=True)
    prompt = executors._build_skill_reference_prompt(
        task, {"project_id": "p1"}, reference_text=""
    )
    assert "__homomics_phase__" in prompt


def test_skill_reference_prompt_zero_injection_without_domain(executors, workspace):
    task = _domain_task()
    task.parameters.pop("domain")
    prompt = executors._build_skill_reference_prompt(
        task, {"project_id": "p1"}, reference_text=""
    )
    assert "__homomics_phase__" not in prompt


# ----------------------------------------------------------------------
# End-to-end CodeAct path: skeleton + phase events (mocked run_code_act)
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_codeact_domain_task_emits_skeleton_and_phase_events(
    orchestrator, states, workspace, monkeypatch
):
    captured_prompts = []

    async def fake_run_code_act(**kwargs):
        captured_prompts.append(kwargs.get("task", ""))
        return {
            "success": True,
            "stdout": (
                "loading...\n"
                "__homomics_phase__:qc:start\n"
                '__homomics_phase__:qc:done:{"min_genes": 200}\n'
                "__homomics_phase__:normalization:start\n"
                "summary\n"
            ),
            "stderr": "",
            "result": {"cells": 2700},
            "code": "print(1)",
            "attempts": 1,
            "fix_history": [],
        }

    monkeypatch.setattr(
        "homomics_lab.agent.orchestrator_executors.run_code_act", fake_run_code_act
    )

    task = _domain_task()
    result = await orchestrator._executors._execute_task_codeact(
        task, {"project_id": "p1"}
    )
    assert result["status"] == "success"

    events = _workflow_events(states)
    # Skeleton first, then the three phase markers in output order.
    assert events[0].extra["type"] == "progress"
    assert events[0].extra["event"] == "workflow_skeleton"
    assert events[0].extra["domain"] == DOMAIN
    assert events[0].extra["phases"] == [
        {"phase_type": "qc", "name": "Quality Control", "skipped": False},
        {"phase_type": "normalization", "name": "Normalization", "skipped": False},
        {"phase_type": "clustering", "name": "Clustering", "skipped": False},
    ]

    phase_events = [e.extra for e in events[1:]]
    assert [(e["event"], e["phase"], e["status"]) for e in phase_events] == [
        ("phase", "qc", "start"),
        ("phase", "qc", "done"),
        ("phase", "normalization", "start"),
    ]
    assert phase_events[1]["params"] == {"min_genes": 200}
    assert phase_events[0]["params"] == {}

    # Convention was injected into the generated-script prompt.
    assert any("__homomics_phase__" in p for p in captured_prompts)


@pytest.mark.asyncio
async def test_workflow_events_follow_progress_contract(
    orchestrator, states, workspace, monkeypatch
):
    async def fake_run_code_act(**kwargs):
        return {
            "success": True,
            "stdout": "__homomics_phase__:qc:start\n",
            "stderr": "",
            "result": {},
            "code": "",
            "attempts": 1,
            "fix_history": [],
        }

    monkeypatch.setattr(
        "homomics_lab.agent.orchestrator_executors.run_code_act", fake_run_code_act
    )

    await orchestrator._executors._execute_task_codeact(
        _domain_task(), {"project_id": "p1"}
    )

    for state in _workflow_events(states):
        payload = state.to_dict()
        # Top-level execution: actor/parent_id keys must be omitted entirely.
        assert "actor" not in payload
        assert "parent_id" not in payload
        assert payload["type"] == "progress"
        assert payload["event"] in ("workflow_skeleton", "phase")
        # Round-trip is wire-stable: the phase "status" lives in extra and is
        # merged over the ExecutionState's own status field by to_dict(); a
        # from_dict -> to_dict cycle reproduces the identical payload.
        restored = ExecutionState.from_dict(payload)
        assert restored.to_dict() == payload


@pytest.mark.asyncio
async def test_generic_task_emits_no_workflow_events(
    orchestrator, states, workspace, monkeypatch
):
    async def fake_run_code_act(**kwargs):
        return {
            "success": True,
            "stdout": "__homomics_phase__:qc:start\n",  # markers ignored too
            "stderr": "",
            "result": {},
            "code": "",
            "attempts": 1,
            "fix_history": [],
        }

    monkeypatch.setattr(
        "homomics_lab.agent.orchestrator_executors.run_code_act", fake_run_code_act
    )

    task = _domain_task(domain="generic")
    result = await orchestrator._executors._execute_task_codeact(
        task, {"project_id": "p1"}
    )
    assert result["status"] == "success"
    assert _workflow_events(states) == []


@pytest.mark.asyncio
async def test_no_markers_degrades_to_pending_skeleton(
    orchestrator, states, workspace, monkeypatch
):
    async def fake_run_code_act(**kwargs):
        return {
            "success": True,
            "stdout": "no markers here\n",
            "stderr": "",
            "result": {},
            "code": "",
            "attempts": 1,
            "fix_history": [],
        }

    monkeypatch.setattr(
        "homomics_lab.agent.orchestrator_executors.run_code_act", fake_run_code_act
    )

    result = await orchestrator._executors._execute_task_codeact(
        _domain_task(), {"project_id": "p1"}
    )
    assert result["status"] == "success"
    events = _workflow_events(states)
    # Skeleton is still emitted; phases stay pending (no phase events).
    assert len(events) == 1
    assert events[0].extra["event"] == "workflow_skeleton"


@pytest.mark.asyncio
async def test_failed_run_scans_merged_stderr_for_failed_markers(
    orchestrator, states, workspace, monkeypatch
):
    async def fake_run_code_act(**kwargs):
        return {
            "success": False,
            "stdout": "",
            # execute_code surfaces the merged stream as stderr on failure.
            "stderr": (
                "__homomics_phase__:qc:start\n"
                "Traceback ...\n"
                '__homomics_phase__:qc:failed:{"error": "ValueError: bad shape"}\n'
            ),
            "error": "ValueError: bad shape",
            "result": {},
            "code": "",
            "attempts": 1,
            "fix_history": [],
        }

    monkeypatch.setattr(
        "homomics_lab.agent.orchestrator_executors.run_code_act", fake_run_code_act
    )

    result = await orchestrator._executors._execute_task_codeact(
        _domain_task(), {"project_id": "p1"}
    )
    assert result["status"] == "error"
    phase_events = [
        e.extra for e in _workflow_events(states) if e.extra["event"] == "phase"
    ]
    assert [(e["phase"], e["status"]) for e in phase_events] == [
        ("qc", "start"),
        ("qc", "failed"),
    ]
    assert phase_events[-1]["params"] == {"error": "ValueError: bad shape"}


# ----------------------------------------------------------------------
# Trace mirroring
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_workflow_events_mirrored_to_trace(
    orchestrator, states, workspace, monkeypatch
):
    trace_calls = []

    class FakeTraceStore:
        async def add_node(self, **kwargs):
            trace_calls.append(kwargs)
            return None

    monkeypatch.setattr(
        "homomics_lab.agent.orchestrator_executors.TraceStore", FakeTraceStore
    )

    async def fake_run_code_act(**kwargs):
        return {
            "success": True,
            "stdout": "__homomics_phase__:qc:start\n",
            "stderr": "",
            "result": {},
            "code": "",
            "attempts": 1,
            "fix_history": [],
        }

    monkeypatch.setattr(
        "homomics_lab.agent.orchestrator_executors.run_code_act", fake_run_code_act
    )

    await orchestrator._executors._execute_task_codeact(
        _domain_task(), {"project_id": "p1", "trace_id": "trace-1"}
    )

    assert trace_calls[0]["trace_id"] == "trace-1"
    assert trace_calls[0]["node_type"] == "plan"
    assert trace_calls[0]["metadata"]["event"] == "workflow_skeleton"
    assert trace_calls[0]["metadata"]["domain"] == DOMAIN
    assert trace_calls[1]["node_type"] == "phase"
    assert trace_calls[1]["metadata"] == {
        "event": "phase",
        "phase": "qc",
        "status": "start",
        "params": {},
        "task_id": "t1",
    }


@pytest.mark.asyncio
async def test_no_trace_without_trace_id(orchestrator, states, workspace, monkeypatch):
    class ExplodingTraceStore:
        def __init__(self, *args, **kwargs):
            raise AssertionError("TraceStore must not be constructed")

    monkeypatch.setattr(
        "homomics_lab.agent.orchestrator_executors.TraceStore", ExplodingTraceStore
    )

    async def fake_run_code_act(**kwargs):
        return {
            "success": True,
            "stdout": "__homomics_phase__:qc:start\n",
            "stderr": "",
            "result": {},
            "code": "",
            "attempts": 1,
            "fix_history": [],
        }

    monkeypatch.setattr(
        "homomics_lab.agent.orchestrator_executors.run_code_act", fake_run_code_act
    )

    result = await orchestrator._executors._execute_task_codeact(
        _domain_task(), {"project_id": "p1"}
    )
    assert result["status"] == "success"
    assert len(_workflow_events(states)) == 2  # skeleton + phase, trace skipped


# ----------------------------------------------------------------------
# Skill-as-reference path
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_skill_reference_path_emits_events_and_injects(
    orchestrator, states, workspace, monkeypatch
):
    skill = SkillDefinition(
        id="celltypist",
        name="celltypist",
        version="1.0",
        category="single-cell",
        description="Cell type annotation",
        input_schema=SkillInputSchema(),
    )
    orchestrator.skill_registry.register(skill)

    captured_prompts = []

    async def fake_run_code_act(**kwargs):
        captured_prompts.append(kwargs.get("task", ""))
        return {
            "success": True,
            "stdout": '__homomics_phase__:annotation:done:{"model": "Immune_All_Low.pkl"}\n',
            "stderr": "",
            "result": {},
            "code": "",
            "attempts": 1,
            "fix_history": [],
        }

    monkeypatch.setattr(
        "homomics_lab.agent.orchestrator_executors.run_code_act", fake_run_code_act
    )

    task = _domain_task(
        use_skill_reference=True,
        domain_phases=[{"phase_type": "annotation", "name": "Annotation"}],
    )
    task.skills_required = ["celltypist"]
    result = await orchestrator._executors._execute_task_with_skill_reference(
        task, {"project_id": "p1"}
    )
    assert result["status"] == "success"

    events = _workflow_events(states)
    assert events[0].extra["event"] == "workflow_skeleton"
    assert events[0].extra["phases"] == [
        {"phase_type": "annotation", "name": "Annotation", "skipped": False}
    ]
    assert events[1].extra["event"] == "phase"
    assert events[1].extra["params"] == {"model": "Immune_All_Low.pkl"}
    assert any("__homomics_phase__" in p for p in captured_prompts)


# ----------------------------------------------------------------------
# Runner callback: session_id stamping
# ----------------------------------------------------------------------


def test_runner_callback_stamps_job_and_session_id():
    published = []

    class FakePubSub:
        def publish(self, job_id, state):
            published.append((job_id, state))

    runner = BackgroundJobRunner.__new__(BackgroundJobRunner)
    runner._pubsub = FakePubSub()
    callback = runner._make_progress_callback("job-1", session_id="sess-1")

    workflow_state = ExecutionState(
        job_id="",
        status="RUNNING",
        scheduler_type="agent",
        extra={
            "type": "progress",
            "event": "phase",
            "phase": "qc",
            "status": "start",
            "params": {},
        },
    )
    callback(workflow_state)
    job_id, state = published[0]
    assert job_id == "job-1"
    assert state.job_id == "job-1"
    assert state.extra["session_id"] == "sess-1"

    plain_state = ExecutionState(job_id="", status="RUNNING", scheduler_type="agent")
    callback(plain_state)
    assert plain_state.extra is None  # untouched: no session_id key added


# ----------------------------------------------------------------------
# Plan-time stamping (decomposer)
# ----------------------------------------------------------------------


def test_stamp_domain_pipeline_marks_all_tasks():
    plan = PlanResult(
        phases=[
            Phase(phase_type="qc", description="Quality Control"),
            Phase(phase_type="clustering", description="Clustering"),
            Phase(phase_type="optional_step", required=False),
        ],
        strategy_name="single-cell",
        data_state=DataState(),
    )
    decomposer = TaskDecomposer()
    tree = decomposer._plan_result_to_task_tree(plan)

    decomposer._stamp_domain_pipeline(plan, tree, DOMAIN)
    for task in tree.tasks:
        assert task.parameters["domain"] == DOMAIN
        # Optional (non-required) phases are excluded from the skeleton.
        assert [p["phase_type"] for p in task.parameters["domain_phases"]] == [
            "qc",
            "clustering",
        ]


def test_stamp_domain_pipeline_noop_without_domain():
    plan = PlanResult(
        phases=[Phase(phase_type="qc")],
        strategy_name="single-cell",
        data_state=DataState(),
    )
    decomposer = TaskDecomposer()
    tree = decomposer._plan_result_to_task_tree(plan)
    decomposer._stamp_domain_pipeline(plan, tree, None)
    assert all("domain" not in t.parameters for t in tree.tasks)


def _domain_skill_registry() -> SkillRegistry:
    """Registry containing every skill referenced by the single_cell domain."""
    registry = SkillRegistry()
    domain_file = (
        Path(__file__).parent.parent.parent
        / "homomics_lab"
        / "domains"
        / "single-cell-transcriptomics"
        / "domain.yaml"
    )
    with open(domain_file, "r", encoding="utf-8") as f:
        domain = yaml.safe_load(f)
    skill_ids = {
        skill_id
        for phase in domain.get("phases", [])
        for skill_id in phase.get("skills", [])
    }
    for skill_id in skill_ids:
        registry.register(
            SkillDefinition(
                id=skill_id,
                name=skill_id,
                version="1.0",
                category="single-cell-transcriptomics",
                description=f"Domain skill {skill_id}",
                input_schema=SkillInputSchema(),
            )
        )
    return registry


@pytest.mark.asyncio
async def test_decompose_stamps_domain_and_trimmed_pipeline(monkeypatch):
    monkeypatch.setattr(settings, "auto_load_domain_strategies", True)
    decomposer = TaskDecomposer(skill_registry=_domain_skill_registry())
    intent = UserIntent(
        analysis_type="single_cell_analysis",
        complexity="complex",
    )

    tree = await decomposer.decompose(
        intent, context={"preflight": {"skip_phases": ["qc"]}}
    )

    assert tree.tasks, "expected a non-empty domain task tree"
    for task in tree.tasks:
        assert task.parameters["domain"] == "single-cell-transcriptomics"
        skeleton = task.parameters["domain_phases"]
        assert "qc" not in [p["phase_type"] for p in skeleton]
        assert "clustering" in [p["phase_type"] for p in skeleton]


# ----------------------------------------------------------------------
# Real-time streaming phase events (line callback + task-level dedupe)
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_codeact_streams_phase_events_with_dedupe(
    orchestrator, states, workspace, monkeypatch
):
    """Markers reported live via the line callback are emitted exactly once.

    The fake execution reports markers through ``on_output_line`` (as the
    sandbox streaming path would) and also returns them in the captured
    output; the batch fallback scan must not re-emit them.
    """
    seen = {}

    async def fake_run_code_act(**kwargs):
        cb = kwargs.get("on_output_line")
        seen["cb"] = cb
        assert cb is not None, "domain task must get a streaming line callback"
        for line, stream in [
            ("__homomics_phase__:qc:start", "stdout"),
            ("loading...", "stdout"),  # not a marker: ignored
            ('__homomics_phase__:qc:done:{"min_genes": 200}', "stdout"),
            ("__homomics_phase__:normalization:start", "stderr"),
        ]:
            cb(line, stream)
        return {
            "success": True,
            # The same markers also appear in the captured output, so the
            # batch fallback would re-report them without dedupe.
            "stdout": (
                "__homomics_phase__:qc:start\n"
                '__homomics_phase__:qc:done:{"min_genes": 200}\n'
            ),
            "stderr": "__homomics_phase__:normalization:start\n",
            "result": {"cells": 2700},
            "code": "print(1)",
            "attempts": 1,
            "fix_history": [],
        }

    monkeypatch.setattr(
        "homomics_lab.agent.orchestrator_executors.run_code_act", fake_run_code_act
    )

    result = await orchestrator._executors._execute_task_codeact(
        _domain_task(), {"project_id": "p1"}
    )
    assert result["status"] == "success"
    assert seen["cb"] is not None

    events = _workflow_events(states)
    assert events[0].extra["event"] == "workflow_skeleton"
    phase_events = [e.extra for e in events[1:]]
    # In arrival order, each (phase, status) exactly once.
    assert [(e["phase"], e["status"]) for e in phase_events] == [
        ("qc", "start"),
        ("qc", "done"),
        ("normalization", "start"),
    ]
    assert phase_events[1]["params"] == {"min_genes": 200}


@pytest.mark.asyncio
async def test_generic_task_receives_no_line_callback(
    orchestrator, states, workspace, monkeypatch
):
    """Generic tasks get no callback and no events — batch path unchanged."""
    seen = {}

    async def fake_run_code_act(**kwargs):
        seen["cb"] = kwargs.get("on_output_line")
        return {
            "success": True,
            "stdout": "__homomics_phase__:qc:start\n",
            "stderr": "",
            "result": {},
            "code": "",
            "attempts": 1,
            "fix_history": [],
        }

    monkeypatch.setattr(
        "homomics_lab.agent.orchestrator_executors.run_code_act", fake_run_code_act
    )

    result = await orchestrator._executors._execute_task_codeact(
        _domain_task(domain="generic"), {"project_id": "p1"}
    )
    assert result["status"] == "success"
    assert seen["cb"] is None
    assert _workflow_events(states) == []


@pytest.mark.asyncio
async def test_batch_fallback_when_callback_never_fires(
    orchestrator, states, workspace, monkeypatch
):
    """A backend that never invokes the callback degrades to the batch scan."""

    async def fake_run_code_act(**kwargs):
        return {
            "success": True,
            "stdout": "__homomics_phase__:qc:start\n",
            "stderr": "",
            "result": {},
            "code": "",
            "attempts": 1,
            "fix_history": [],
        }

    monkeypatch.setattr(
        "homomics_lab.agent.orchestrator_executors.run_code_act", fake_run_code_act
    )

    await orchestrator._executors._execute_task_codeact(
        _domain_task(), {"project_id": "p1"}
    )
    phase_events = [
        e.extra for e in _workflow_events(states) if e.extra["event"] == "phase"
    ]
    assert [(e["phase"], e["status"]) for e in phase_events] == [("qc", "start")]


@pytest.mark.asyncio
async def test_streamed_phase_events_mirrored_to_trace(
    orchestrator, states, workspace, monkeypatch
):
    """Streamed (fire-and-forget) trace mirrors are flushed before return."""
    trace_calls = []

    class FakeTraceStore:
        async def add_node(self, **kwargs):
            trace_calls.append(kwargs)
            return None

    monkeypatch.setattr(
        "homomics_lab.agent.orchestrator_executors.TraceStore", FakeTraceStore
    )

    async def fake_run_code_act(**kwargs):
        cb = kwargs["on_output_line"]
        cb("__homomics_phase__:qc:start", "stdout")
        return {
            "success": True,
            "stdout": "__homomics_phase__:qc:start\n",
            "stderr": "",
            "result": {},
            "code": "",
            "attempts": 1,
            "fix_history": [],
        }

    monkeypatch.setattr(
        "homomics_lab.agent.orchestrator_executors.run_code_act", fake_run_code_act
    )

    await orchestrator._executors._execute_task_codeact(
        _domain_task(), {"project_id": "p1", "trace_id": "trace-rt"}
    )

    phase_traces = [c for c in trace_calls if c["node_type"] == "phase"]
    assert len(phase_traces) == 1
    assert phase_traces[0]["trace_id"] == "trace-rt"
    assert phase_traces[0]["metadata"]["phase"] == "qc"
    assert phase_traces[0]["metadata"]["status"] == "start"


# ----------------------------------------------------------------------
# Fixed-pipeline (curated skill runtime) workflow events
# ----------------------------------------------------------------------


class _FakeCuratedAgent(BaseAgent):
    agent_type = AgentType.BIOINFO
    capabilities = ["scanpy_qc"]

    async def run(self, task, context):
        return {"status": "success", "output": {"cells": 100}}


class _FakeFailingAgent(BaseAgent):
    agent_type = AgentType.BIOINFO
    capabilities = ["scanpy_qc"]

    async def run(self, task, context):
        raise RuntimeError("curated skill exploded")


def _fixed_orchestrator(states, agent) -> Orchestrator:
    registry = AgentRegistry()
    registry.register(agent)
    return Orchestrator(
        registry=registry,
        skill_registry=SkillRegistry(),
        progress_callback=states.append,
    )


def _fixed_pipeline_task(**param_overrides) -> TaskNode:
    task = _domain_task(**param_overrides)
    task.skills_required = ["scanpy_qc"]
    return task


@pytest.mark.asyncio
async def test_fixed_pipeline_emits_skeleton_and_phase_events(states, workspace):
    orch = _fixed_orchestrator(states, _FakeCuratedAgent())
    result = await orch._execute_task(
        _fixed_pipeline_task(),
        {"execution_mode": "fixed_pipeline", "project_id": "p1"},
        {},
    )
    assert result["status"] == "success"

    events = _workflow_events(states)
    assert events[0].extra["event"] == "workflow_skeleton"
    assert events[0].extra["domain"] == DOMAIN
    assert events[0].extra["phases"] == [
        {"phase_type": "qc", "name": "Quality Control", "skipped": False},
        {"phase_type": "normalization", "name": "Normalization", "skipped": False},
        {"phase_type": "clustering", "name": "Clustering", "skipped": False},
    ]
    phase_events = [e.extra for e in events[1:] if e.extra["event"] == "phase"]
    assert [(e["phase"], e["status"]) for e in phase_events] == [
        ("qc", "start"),
        ("qc", "done"),
    ]
    assert phase_events[0]["params"] == {"skill": "scanpy_qc"}
    assert phase_events[1]["params"] == {"skill": "scanpy_qc"}


@pytest.mark.asyncio
async def test_fixed_pipeline_failed_task_emits_phase_failed(states, workspace):
    orch = _fixed_orchestrator(states, _FakeFailingAgent())
    with pytest.raises(RuntimeError, match="curated skill exploded"):
        await orch._execute_task(
            _fixed_pipeline_task(),
            {"execution_mode": "fixed_pipeline", "project_id": "p1"},
            {},
        )
    phase_events = [
        e.extra for e in _workflow_events(states) if e.extra["event"] == "phase"
    ]
    assert [(e["phase"], e["status"]) for e in phase_events] == [
        ("qc", "start"),
        ("qc", "failed"),
    ]
    assert "curated skill exploded" in phase_events[-1]["params"]["error"]


@pytest.mark.asyncio
async def test_fixed_pipeline_generic_task_emits_nothing(states, workspace):
    orch = _fixed_orchestrator(states, _FakeCuratedAgent())
    result = await orch._execute_task(
        _fixed_pipeline_task(domain="generic"),
        {"execution_mode": "fixed_pipeline", "project_id": "p1"},
        {},
    )
    assert result["status"] == "success"
    assert _workflow_events(states) == []


@pytest.mark.asyncio
async def test_auto_mode_curated_path_stays_silent(states, workspace):
    """The workflow events are a fixed_pipeline contract; auto mode is unchanged."""
    orch = _fixed_orchestrator(states, _FakeCuratedAgent())
    result = await orch._execute_task(
        _fixed_pipeline_task(),
        {"execution_mode": "auto", "project_id": "p1"},
        {},
    )
    assert result["status"] == "success"
    assert _workflow_events(states) == []
