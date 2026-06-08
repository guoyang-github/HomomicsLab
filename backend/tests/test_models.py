from homics_lab.models.common import (
    TaskStatus, MessageType, HITLTrigger,
    Option, HITLCheckpoint, ChatMessage,
)

def test_task_status_values():
    assert TaskStatus.PENDING.value == "pending"
    assert TaskStatus.RUNNING.value == "running"
    assert TaskStatus.COMPLETED.value == "completed"

def test_hitl_triggers():
    assert HITLTrigger.LOW_CONFIDENCE.value == "low_confidence"
    assert HITLTrigger.HIGH_COST.value == "high_cost"

def test_chat_message_defaults():
    msg = ChatMessage(id="msg_1", content="hello", sender="user")
    assert msg.type == MessageType.TEXT
    assert msg.timestamp.tzinfo is not None
    assert msg.related_files == []


def test_hitl_checkpoint_creation():
    checkpoint = HITLCheckpoint(
        id="hitl_1",
        trigger_reason=HITLTrigger.POLICY,
        context_summary="Confirm parameters",
        options=[Option(id="ok", label="OK")],
    )
    assert checkpoint.timeout_minutes == 24 * 60
    assert checkpoint.default_option is None
