from homics_lab.models.common import (
    TaskStatus, MessageType, AgentType, HITLTrigger
)

def test_task_status_values():
    assert TaskStatus.PENDING.value == "pending"
    assert TaskStatus.RUNNING.value == "running"
    assert TaskStatus.COMPLETED.value == "completed"

def test_hitl_triggers():
    assert HITLTrigger.LOW_CONFIDENCE.value == "low_confidence"
    assert HITLTrigger.HIGH_COST.value == "high_cost"
