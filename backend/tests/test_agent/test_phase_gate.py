"""Tests for PhaseGateEvaluator."""

import pytest

from homomics_lab.agent.phase_gate import GateResult, PhaseGateEvaluator
from homomics_lab.agent.plan.models import DataState, SuccessCriterion
from homomics_lab.tasks.models import TaskNode


@pytest.fixture
def evaluator():
    data_state = DataState()
    data_state.set("n_cells", 5000)
    return PhaseGateEvaluator(data_state=data_state)


@pytest.mark.asyncio
async def test_gate_passes_when_no_criteria(evaluator):
    task = TaskNode(id="t1", name="qc", description="QC")
    result = await evaluator.evaluate(task, {"result": {"qc": {"pass_rate": 0.1}}})
    assert result.passed is True


@pytest.mark.asyncio
async def test_gate_passes_when_criteria_satisfied(evaluator):
    task = TaskNode(
        id="t1",
        name="qc",
        description="QC",
        success_criteria=[
            {
                "metric": "result.qc.pass_rate",
                "operator": ">=",
                "threshold": 0.4,
            }
        ],
    )
    result = await evaluator.evaluate(
        task, {"result": {"qc": {"pass_rate": 0.5}}}
    )
    assert result.passed is True


@pytest.mark.asyncio
async def test_gate_fails_when_criteria_not_satisfied(evaluator):
    task = TaskNode(
        id="t1",
        name="qc",
        description="QC",
        success_criteria=[
            {
                "metric": "result.qc.pass_rate",
                "operator": ">=",
                "threshold": 0.4,
            }
        ],
    )
    result = await evaluator.evaluate(
        task, {"result": {"qc": {"pass_rate": 0.2}}}
    )
    assert result.passed is False
    assert result.criterion.metric == "result.qc.pass_rate"
    assert result.actual_value == 0.2


@pytest.mark.asyncio
async def test_gate_resolves_data_state_metric(evaluator):
    task = TaskNode(
        id="t1",
        name="qc",
        description="QC",
        success_criteria=[
            {
                "metric": "data_state.n_cells",
                "operator": ">=",
                "threshold": 1000,
            }
        ],
    )
    result = await evaluator.evaluate(task, {"result": {}})
    assert result.passed is True


@pytest.mark.asyncio
async def test_gate_missing_metric_fails(evaluator):
    task = TaskNode(
        id="t1",
        name="qc",
        description="QC",
        success_criteria=[
            {
                "metric": "result.qc.pass_rate",
                "operator": ">=",
                "threshold": 0.4,
            }
        ],
    )
    result = await evaluator.evaluate(task, {"result": {}})
    assert result.passed is False


@pytest.mark.asyncio
async def test_gate_operators(evaluator):
    task = TaskNode(
        id="t1",
        name="qc",
        description="QC",
        success_criteria=[
            {"metric": "result.value", "operator": "<", "threshold": 10},
            {"metric": "result.value", "operator": "<=", "threshold": 5},
            {"metric": "result.value", "operator": "==", "threshold": 5},
            {"metric": "result.value", "operator": "!=", "threshold": 3},
            {"metric": "result.tag", "operator": "in", "threshold": ["a", "b"]},
            {"metric": "result.tags", "operator": "contains", "threshold": "x"},
        ],
    )
    result = await evaluator.evaluate(
        task,
        {"result": {"value": 5, "tag": "a", "tags": ["x", "y"]}},
    )
    assert result.passed is True


@pytest.mark.asyncio
async def test_gate_message_formatting(evaluator):
    task = TaskNode(
        id="t1",
        name="qc",
        description="QC",
        success_criteria=[
            {
                "metric": "result.qc.pass_rate",
                "operator": ">=",
                "threshold": 0.4,
                "message": "QC pass rate {actual} is below {expected}",
            }
        ],
    )
    result = await evaluator.evaluate(
        task, {"result": {"qc": {"pass_rate": 0.2}}}
    )
    assert "0.2" in result.message
    assert "0.4" in result.message


def test_success_criterion_serialization_roundtrip():
    criterion = SuccessCriterion(
        metric="result.qc.pass_rate",
        operator=">=",
        threshold=0.4,
        on_failure="replan",
        message="fail",
        replan_context={"remediation": "re_qc"},
    )
    data = criterion.__dict__
    restored = SuccessCriterion(**data)
    assert restored.metric == criterion.metric
    assert restored.on_failure == "replan"
