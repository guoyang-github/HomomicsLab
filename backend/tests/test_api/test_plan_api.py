"""Tests for the plan approval API."""

import time
import uuid

import pytest
from fastapi.testclient import TestClient

from homomics_lab.agent.plan.models import DataState, Phase, PlanResult, StrategyTrace
from homomics_lab.context.working_memory import WorkingMemory
from homomics_lab.main import app
from homomics_lab.plan import Plan, PlanStatus, PlanStore
from homomics_lab.tasks.models import TaskNode
from homomics_lab.tasks.task_tree import TaskTree


def _poll_job(client, job_id: str, timeout: float = 30.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        response = client.get(f"/api/execution/{job_id}/status")
        data = response.json()
        if data["status"] not in ("queued", "pending", "running"):
            return data
        time.sleep(0.1)
    return response.json()


def _make_pending_plan(store: PlanStore) -> Plan:
    tree = TaskTree(
        [
            TaskNode(
                id="t1",
                name="fallback_suggestion",
                description="No executable workflow could be planned.",
                phase="suggestion",
                skills_required=[],
            )
        ]
    )
    plan_result = PlanResult(
        phases=[],
        strategy_name="llm_fallback",
        data_state=DataState(),
        is_fallback=True,
        suggestion_text="No executable workflow could be planned.",
    )
    return Plan(
        plan_id=f"plan_{uuid.uuid4().hex[:12]}",
        session_id="sess_plan",
        project_id="proj_1",
        status=PlanStatus.PENDING_APPROVAL,
        is_fallback=True,
        intent_analysis_type="general",
        intent_complexity="direct_response",
        plan_result=plan_result,
        task_tree=tree,
        working_memory=WorkingMemory(),
    )


def _make_pending_plan_with_phase(
    store: PlanStore, session_id: str = "sess_plan"
) -> Plan:
    tree = TaskTree(
        [
            TaskNode(
                id="qc1",
                name="qc",
                description="quality control",
                phase="qc",
                skills_required=["scanpy_qc"],
                parameters={"min_genes": 200},
            )
        ]
    )
    plan_result = PlanResult(
        phases=[
            Phase(
                phase_type="qc",
                description="quality control",
                parameters={"min_genes": 200},
            )
        ],
        strategy_name="single-cell-transcriptomics",
        data_state=DataState(),
    )
    return Plan(
        plan_id=f"plan_{uuid.uuid4().hex[:12]}",
        session_id=session_id,
        project_id="proj_1",
        status=PlanStatus.PENDING_APPROVAL,
        is_fallback=False,
        intent_analysis_type="single_cell_analysis",
        intent_complexity="workflow",
        plan_result=plan_result,
        task_tree=tree,
        working_memory=WorkingMemory(),
    )


@pytest.mark.skip(
    reason="Requires real domain strategies and LLM; not runnable in isolated test environment."
)
@pytest.mark.asyncio
async def test_send_message_auto_approved_creates_plan():
    with TestClient(app) as client:
        response = client.post(
            "/api/chat/send",
            json={
                "project_id": "proj_1",
                "session_id": "sess_auto",
                "message": "帮我分析单细胞数据",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("queued", "awaiting_plan_approval")
        assert data["job_id"] is not None or data["plan_id"] is not None

        plan_id = data.get("plan_id")
        if plan_id:
            plan_response = client.get(f"/api/plan/{plan_id}")
            assert plan_response.status_code == 200
            plan_data = plan_response.json()
            assert plan_data["plan_id"] == plan_id
            assert plan_data["is_fallback"] is False
            assert len(plan_data["phases"]) > 0


@pytest.mark.asyncio
async def test_approve_plan_endpoint_enqueues_job():
    with TestClient(app) as client:
        plan_store = app.state.plan_store
        plan = _make_pending_plan(plan_store)
        await plan_store.create(plan)

        response = client.post(
            f"/api/plan/{plan.plan_id}/approve",
            json={"approved": True, "modifications": []},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == PlanStatus.APPROVED
        assert data["job_id"] is not None

        final = _poll_job(client, data["job_id"])
        assert final["status"] in ("completed", "failed")


@pytest.mark.asyncio
async def test_reject_plan_endpoint():
    with TestClient(app) as client:
        plan_store = app.state.plan_store
        plan = _make_pending_plan(plan_store)
        await plan_store.create(plan)

        response = client.post(
            f"/api/plan/{plan.plan_id}/approve",
            json={"approved": False, "modifications": []},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == PlanStatus.REJECTED
        assert data["job_id"] is None


@pytest.mark.asyncio
async def test_modify_plan_creates_new_version():
    with TestClient(app) as client:
        plan_store = app.state.plan_store
        plan = _make_pending_plan_with_phase(plan_store)
        await plan_store.create(plan)

        response = client.post(
            f"/api/plan/{plan.plan_id}/modify",
            json={
                "approved": False,
                "modifications": [
                    {
                        "phase_type": "qc",
                        "parameter": "min_genes",
                        "old_value": 200,
                        "new_value": 300,
                        "action": "update",
                    }
                ],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == PlanStatus.PENDING_APPROVAL
        assert data["new_plan_id"] is not None
        assert data["new_plan_id"] != plan.plan_id

        new_plan = await plan_store.get(data["new_plan_id"])
        assert new_plan.version == plan.version + 1
        assert new_plan.plan_result.phases[0].parameters["min_genes"] == 300


@pytest.mark.asyncio
async def test_modify_and_approve_enqueues_job():
    with TestClient(app) as client:
        plan_store = app.state.plan_store
        plan = _make_pending_plan_with_phase(plan_store)
        await plan_store.create(plan)

        response = client.post(
            f"/api/plan/{plan.plan_id}/modify",
            json={
                "approved": True,
                "modifications": [
                    {
                        "phase_type": "qc",
                        "parameter": "min_genes",
                        "old_value": 200,
                        "new_value": 300,
                        "action": "update",
                    }
                ],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == PlanStatus.APPROVED
        assert data["job_id"] is not None
        assert data["new_plan_id"] is not None


@pytest.mark.asyncio
async def test_list_session_plans():
    with TestClient(app) as client:
        plan_store = app.state.plan_store
        plan = _make_pending_plan(plan_store)
        plan.session_id = "sess_list"
        await plan_store.create(plan)

        response = client.get("/api/plan/session/sess_list")
        assert response.status_code == 200
        data = response.json()
        assert any(p["plan_id"] == plan.plan_id for p in data["plans"])


@pytest.mark.asyncio
async def test_diff_plans_endpoint():
    with TestClient(app) as client:
        plan_store = app.state.plan_store
        plan_a = _make_pending_plan_with_phase(plan_store, session_id="sess_diff")
        await plan_store.create(plan_a)
        plan_b = await plan_store.modify(
            plan_a.plan_id,
            modifications=[
                {
                    "phase_type": "qc",
                    "parameter": "min_genes",
                    "old_value": 200,
                    "new_value": 300,
                    "action": "update",
                }
            ],
            approved=False,
        )

        response = client.get(f"/api/plan/{plan_b.plan_id}/diff")
        assert response.status_code == 200
        data = response.json()
        assert data["plan_a_id"] == plan_b.plan_id
        assert data["plan_b_id"] == plan_a.plan_id
        diffs = data["differences"]
        assert any(
            d["change"] == "parameter_changed" and d["parameter"] == "min_genes"
            for d in diffs
        )


@pytest.mark.asyncio
async def test_plan_job_endpoint():
    with TestClient(app) as client:
        plan_store = app.state.plan_store
        plan = _make_pending_plan(plan_store)
        await plan_store.create(plan)

        response = client.post(
            f"/api/plan/{plan.plan_id}/approve",
            json={"approved": True, "modifications": []},
        )
        data = response.json()
        job_id = data["job_id"]

        response = client.get(f"/api/plan/{plan.plan_id}/job")
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == job_id


@pytest.mark.asyncio
async def test_plan_status_updated_by_job():
    with TestClient(app) as client:
        plan_store = app.state.plan_store
        plan = _make_pending_plan(plan_store)
        await plan_store.create(plan)

        response = client.post(
            f"/api/plan/{plan.plan_id}/approve",
            json={"approved": True, "modifications": []},
        )
        data = response.json()

        final = _poll_job(client, data["job_id"])
        assert final["status"] in ("completed", "failed")

        updated = await plan_store.get(plan.plan_id)
        expected_status = (
            PlanStatus.COMPLETED
            if final["status"] == "completed"
            else PlanStatus.FAILED
        )
        assert updated.status == expected_status


class _FakePlanEngine:
    """Fast deterministic plan engine for switch-strategy API tests."""

    def __init__(self, *args, **kwargs):
        pass

    async def plan(self, intent, data_state=None, **kwargs):
        from homomics_lab.agent.plan.models import DataState as PlanDataState
        from homomics_lab.agent.plan.models import Phase, PlanResult

        strategy_name = kwargs.get("strategy_name") or intent.analysis_type
        # Always emit a single qc phase so parameter preservation can be asserted.
        return PlanResult(
            phases=[
                Phase(
                    phase_type="qc",
                    description="quality control",
                    parameters={"min_genes": 100},
                )
            ],
            strategy_name=strategy_name,
            data_state=data_state or PlanDataState(),
        )


def _make_plan_with_trace(store: PlanStore, session_id: str = "sess_trace") -> Plan:
    plan_result = PlanResult(
        phases=[
            Phase(
                phase_type="qc",
                description="quality control",
                parameters={"min_genes": 200},
            )
        ],
        strategy_name="single_cell_standard",
        data_state=DataState(),
        strategy_trace=StrategyTrace(
            intent_analysis_type="single_cell_analysis",
            selected_strategy_name="single_cell_standard",
            strategy_candidates=[
                {
                    "name": "single_cell_standard",
                    "score": 1.5,
                    "description": "scRNA-seq",
                },
                {"name": "generic", "score": 0.5, "description": "generic"},
            ],
            quality_score=0.95,
        ),
    )
    return Plan(
        plan_id=f"plan_{uuid.uuid4().hex[:12]}",
        session_id=session_id,
        project_id="proj_1",
        status=PlanStatus.PENDING_APPROVAL,
        is_fallback=False,
        intent_analysis_type="single_cell_analysis",
        intent_complexity="workflow",
        original_intent={
            "analysis_type": "single_cell_analysis",
            "complexity": "complex",
            "confidence": 0.9,
            "original_message": "analyze single cell",
            "metadata": {},
        },
        plan_result=plan_result,
        task_tree=TaskTree(
            tasks=[
                TaskNode(
                    id="qc1",
                    name="qc",
                    description="quality control",
                    phase="qc",
                    skills_required=["scanpy_qc"],
                    parameters={"min_genes": 200},
                )
            ]
        ),
        working_memory=WorkingMemory(),
    )


@pytest.mark.asyncio
async def test_get_plan_rationale_endpoint():
    with TestClient(app) as client:
        plan_store = app.state.plan_store
        plan = _make_plan_with_trace(plan_store)
        await plan_store.create(plan)

        response = client.get(f"/api/plan/{plan.plan_id}/rationale")
        assert response.status_code == 200
        data = response.json()
        assert data["plan_id"] == plan.plan_id
        assert data["strategy_name"] == "single_cell_standard"
        trace = data["strategy_trace"]
        assert trace["intent_analysis_type"] == "single_cell_analysis"
        assert trace["selected_strategy_name"] == "single_cell_standard"
        assert len(trace["strategy_candidates"]) == 2


@pytest.mark.asyncio
async def test_switch_strategy_endpoint_creates_new_version(monkeypatch):
    monkeypatch.setattr("homomics_lab.api.plan.PlanEngine", _FakePlanEngine)
    with TestClient(app) as client:
        plan_store = app.state.plan_store
        plan = _make_plan_with_trace(plan_store, session_id="sess_switch")
        await plan_store.create(plan)

        response = client.post(
            f"/api/plan/{plan.plan_id}/switch-strategy",
            json={"strategy_name": "spatial-transcriptomics", "preserve_user_modifications": True},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == PlanStatus.PENDING_APPROVAL
        assert data["new_plan_id"] is not None
        assert data["new_plan_id"] != plan.plan_id

        new_plan = await plan_store.get(data["new_plan_id"])
        assert new_plan is not None
        assert new_plan.parent_plan_id == plan.plan_id
        assert new_plan.plan_result.strategy_name == "spatial-transcriptomics"
        # User parameter should be preserved for the matching qc phase.
        qc_phase = next(
            (p for p in new_plan.plan_result.phases if p.phase_type == "qc"), None
        )
        assert qc_phase is not None
        assert qc_phase.parameters.get("min_genes") == 200


@pytest.mark.asyncio
async def test_switch_strategy_for_non_pending_plan_returns_400(monkeypatch):
    monkeypatch.setattr("homomics_lab.api.plan.PlanEngine", _FakePlanEngine)
    with TestClient(app) as client:
        plan_store = app.state.plan_store
        plan = _make_plan_with_trace(plan_store, session_id="sess_switch_bad")
        plan.status = PlanStatus.APPROVED
        await plan_store.create(plan)

        response = client.post(
            f"/api/plan/{plan.plan_id}/switch-strategy",
            json={"strategy_name": "spatial-transcriptomics"},
        )
        assert response.status_code == 400
