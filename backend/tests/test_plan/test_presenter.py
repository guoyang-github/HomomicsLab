"""Tests for PlanPresenter."""

import pytest

from homomics_lab.agent.plan.models import DataState, Phase, PlannedGap, PlanResult
from homomics_lab.plan import Plan, PlanPresenter, PlanStatus
from homomics_lab.tasks.models import TaskNode
from homomics_lab.tasks.task_tree import TaskTree


@pytest.fixture
def sample_plan():
    tree = TaskTree(
        [
            TaskNode(
                id="t1",
                name="qc",
                description="Quality control",
                skills_required=["scanpy_qc"],
            ),
        ]
    )
    plan_result = PlanResult(
        phases=[Phase(phase_type="qc", description="Quality control")],
        strategy_name="test",
        data_state=DataState(),
        gaps=[
            PlannedGap(
                from_phase="qc",
                to_phase="clustering",
                from_skill="scanpy_qc",
                to_skill="scanpy_cluster",
                gap_type="field_missing",
            )
        ],
    )
    return Plan(
        plan_id="plan_1",
        session_id="sess_1",
        project_id="proj_1",
        status=PlanStatus.PENDING_APPROVAL,
        intent_analysis_type="single_cell_analysis",
        plan_result=plan_result,
        task_tree=tree,
    )


def test_presenter_includes_phases_and_gaps(sample_plan):
    payload = PlanPresenter.to_user_payload(sample_plan)
    assert payload["plan_id"] == "plan_1"
    assert payload["status"] == PlanStatus.PENDING_APPROVAL
    assert len(payload["phases"]) == 1
    assert payload["phases"][0]["phase_type"] == "qc"
    assert payload["phases"][0]["skill_id"] == "scanpy_qc"
    assert len(payload["gaps"]) == 1
    assert payload["gaps"][0]["gap_type"] == "field_missing"
