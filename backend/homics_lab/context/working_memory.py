from collections import deque
from typing import List, Optional
from homics_lab.models.common import ChatMessage


class WorkingMemory:
    """Short-lived session memory for current conversation and task."""

    def __init__(self, max_messages: int = 20):
        self.max_messages = max_messages
        self.messages: deque[ChatMessage] = deque(maxlen=max_messages)
        self.current_task_id: Optional[str] = None
        self.pinned_items: List[str] = []

    def add_message(self, message: ChatMessage) -> None:
        self.messages.append(message)

    def get_recent_messages(self, n: int = None) -> List[ChatMessage]:
        if n is None:
            n = self.max_messages
        return list(self.messages)[-n:]

    def set_current_task(self, task_id: str) -> None:
        self.current_task_id = task_id

    def pin_item(self, item_id: str) -> None:
        if item_id not in self.pinned_items:
            self.pinned_items.append(item_id)

    def clear(self) -> None:
        self.messages.clear()
        self.current_task_id = None
        self.pinned_items.clear()
