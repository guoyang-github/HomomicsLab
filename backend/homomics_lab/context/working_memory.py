import json
from collections import deque
from typing import Any, Dict, List, Optional
from homomics_lab.models.common import ChatMessage


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

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-friendly dict."""
        return {
            "max_messages": self.max_messages,
            "messages": [m.model_dump(mode="json") for m in self.messages],
            "current_task_id": self.current_task_id,
            "pinned_items": list(self.pinned_items),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkingMemory":
        """Deserialize from a dict."""
        wm = cls(max_messages=data.get("max_messages", 20))
        for msg_data in data.get("messages", []):
            wm.add_message(ChatMessage.model_validate(msg_data))
        wm.current_task_id = data.get("current_task_id")
        wm.pinned_items = list(data.get("pinned_items", []))
        return wm

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, raw: str) -> "WorkingMemory":
        return cls.from_dict(json.loads(raw))
