from homics_lab.context.working_memory import WorkingMemory
from homics_lab.models.common import ChatMessage, MessageType


def test_add_and_retrieve_messages():
    wm = WorkingMemory(max_messages=10)
    wm.add_message(ChatMessage(id="m1", type=MessageType.TEXT, content="hello", sender="user"))
    wm.add_message(ChatMessage(id="m2", type=MessageType.TEXT, content="hi", sender="agent"))

    messages = wm.get_recent_messages()
    assert len(messages) == 2
    assert messages[0].sender == "user"


def test_message_limit():
    wm = WorkingMemory(max_messages=3)
    for i in range(5):
        wm.add_message(ChatMessage(id=f"m{i}", type=MessageType.TEXT, content=str(i), sender="user"))

    messages = wm.get_recent_messages()
    assert len(messages) == 3
    assert messages[0].content == "2"


def test_set_current_task():
    wm = WorkingMemory()
    wm.set_current_task("task_123")
    assert wm.current_task_id == "task_123"
