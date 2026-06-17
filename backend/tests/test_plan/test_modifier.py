"""Tests for PlanModifier structural modifications."""

import uuid

import pytest

from homomics_lab.agent.plan.models import DataState, Phase, PlanResult
from homomics_lab.context.working_memory import WorkingMemory
from homomics_lab.plan import Plan, PlanModification, PlanStatus
from homomics_lab.plan.modifier import PlanModifier, PlanModifierError
from homomics_lab.tasks.models import TaskNode
from homomics_lab.tasks.task_tree import TaskTree


def _make_plan() -> Plan:
    tree = TaskTree(
        [
            TaskNode(id="t1", name="qc", description="QC"),
            TaskNode(
                id="t2",
                name="clustering",
                description="Cluster",
                dependencies=["t1"],
            ),
        ]
    )
    plan_result = PlanResult(
        phases=[
            Phase(phase_type="qc", description="QC"),
            Phase(phase_type="clustering", description="Cluster"),
        ],
        strategy_name="test",
        data_state=DataState(),
        phase_transitions=[
            {"from": "qc", "to": "clustering", "type": "followed_by"},
        ],
    )
    return Plan(
        plan_id=f"plan_{uuid.uuid4().hex[:12]}",
        session_id="sess_1",
        project_id="proj_1",
        status=PlanStatus.PENDING_APPROVAL,
        intent_analysis_type="single_cell_analysis",
        intent_complexity="complex",
        plan_result=plan_result,
        task_tree=tree,
        working_memory=WorkingMemory(),
    )


def test_add_phase_after():
    plan = _make_plan()
    modified = PlanModifier.apply(
        plan,
        [
            PlanModification(
                phase_type="normalization",
                action="add",
                after="qc",
                description="Normalize",
                required=True,
                skill_id="scanpy_normalize",
            )
        ],
    )

    phase_types = [p.phase_type for p in modified.plan_result.phases]
    assert phase_types == ["qc", "normalization", "clustering"]
    assert any(
        t.get("from") == "qc" and t.get("to") == "normalization"
        for t in modified.plan_result.phase_transitions
    )


def test_remove_phase():
    plan = _make_plan()
    modified = PlanModifier.apply(
        plan,
        [PlanModification(phase_type="clustering", action="remove")],
    )

    phase_types = [p.phase_type for p in modified.plan_result.phases]
    assert phase_types == ["qc"]
    task_names = {t.name for t in modified.task_tree.tasks}
    assert task_names == {"qc"}


def test_update_dependency():
    plan = _make_plan()
    modified = PlanModifier.apply(
        plan,
        [
            PlanModification(
                phase_type="clustering",
                action="update_dependency",
                dependencies=["qc"],
            )
        ],
    )

    clustering_task = next(
        t for t in modified.task_tree.tasks if t.name == "clustering"
    )
    assert "t1" in clustering_task.dependencies


def test_rejects_self_loop_dependency():
    plan = _make_plan()
    with pytest.raises(PlanModifierError):
        PlanModifier.apply(
            plan,
            [
                PlanModification(
                    phase_type="clustering",
                    action="update_dependency",
                    dependencies=["clustering"],
                )
            ],
        )


def test_add_phase_rejects_cycle():
    plan = _make_plan()
    # Chain qc -> clustering -> annotation -> qc creates a cycle.
    with pytest.raises(PlanModifierError):
        PlanModifier.apply(
            plan,
            [
                PlanModification(
                    phase_type="annotation",
                    action="add",
                    after="clustering",
                ),
                PlanModification(
                    phase_type="qc",
                    action="add",
                    after="annotation",
                ),
            ],
        )


def test_rejects_unknown_dependency():
    plan = _make_plan()
    with pytest.raises(PlanModifierError):
        PlanModifier.apply(
            plan,
            [
                PlanModification(
                    phase_type="clustering",
                    action="update_dependency",
                    dependencies=["nonexistent"],
                )
            ],
        )
