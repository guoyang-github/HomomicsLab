import pytest
from homomics_lab.hitl.detector import HITLDetector
from homomics_lab.tasks.models import TaskNode
from homomics_lab.models.common import HITLTrigger


@pytest.fixture
def detector():
    return HITLDetector()


def test_detects_policy_checkpoint(detector):
    task = TaskNode(
        id="t1",
        name="clustering",
        description="cluster cells",
        hitl_checkpoints=[{
            "trigger_reason": HITLTrigger.POLICY,
            "context_summary": "Confirm parameters",
            "options": [{"id": "default", "label": "Default"}],
        }],
    )

    checkpoint = detector.check(task, context={})
    assert checkpoint is not None
    assert checkpoint.trigger_reason == HITLTrigger.POLICY


def test_detects_high_cost(detector):
    task = TaskNode(
        id="t1",
        name="big_analysis",
        description="run big analysis",
        estimated_duration_minutes=200,
    )

    checkpoint = detector.check(
        task,
        context={"cost_threshold_minutes": 180},
    )
    assert checkpoint is not None
    assert checkpoint.trigger_reason == HITLTrigger.HIGH_COST


def test_no_checkpoint_for_simple_task(detector):
    task = TaskNode(id="t1", name="load", description="load data")
    checkpoint = detector.check(task, context={})
    assert checkpoint is None
