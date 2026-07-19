import logging

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


def test_detects_high_cost_above_default_threshold(detector):
    # Default gate: estimated duration > 120 minutes pauses for confirmation.
    task = TaskNode(
        id="t1",
        name="big_analysis",
        description="run big analysis",
        estimated_duration_minutes=121,
    )

    checkpoint = detector.check(task, context={})
    assert checkpoint is not None
    assert checkpoint.trigger_reason == HITLTrigger.HIGH_COST


def test_low_confidence_does_not_pause(detector, caplog):
    # Low intent confidence is only logged, never a HITL checkpoint.
    task = TaskNode(id="t1", name="load", description="load data")
    with caplog.at_level(logging.INFO, logger="homomics_lab.hitl.detector"):
        checkpoint = detector.check(
            task,
            context={"confidence": 0.5, "confidence_threshold": 0.7},
        )
    assert checkpoint is None
    assert any(
        "confidence" in record.getMessage().lower() for record in caplog.records
    )


def test_low_confidence_with_high_risk_still_pauses_for_risk(detector, caplog):
    # The risk trigger is independent of the removed confidence trigger.
    task = TaskNode(id="t1", name="delete", description="delete dataset")
    with caplog.at_level(logging.INFO, logger="homomics_lab.hitl.detector"):
        checkpoint = detector.check(
            task,
            context={"confidence": 0.1, "risk_score": 0.8, "risk_threshold": 0.6},
        )
    assert checkpoint is not None
    assert checkpoint.trigger_reason == HITLTrigger.HIGH_RISK
    assert any(
        "confidence" in record.getMessage().lower() for record in caplog.records
    )


def test_detects_high_risk(detector):
    task = TaskNode(id="t1", name="delete", description="delete dataset")
    checkpoint = detector.check(
        task,
        context={"risk_score": 0.8, "risk_threshold": 0.6},
    )
    assert checkpoint is not None
    assert checkpoint.trigger_reason == HITLTrigger.HIGH_RISK
    assert checkpoint.metadata["risk_score"] == 0.8
    assert checkpoint.metadata["risk_threshold"] == 0.6


def test_no_checkpoint_for_simple_task(detector):
    task = TaskNode(id="t1", name="load", description="load data")
    checkpoint = detector.check(task, context={})
    assert checkpoint is None
