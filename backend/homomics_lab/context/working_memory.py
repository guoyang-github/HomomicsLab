import json
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from homomics_lab.models.common import ChatMessage, MessageType


class WorkingMemory:
    """Short-lived session memory for current conversation and task."""

    def __init__(self, max_messages: int = 20):
        self.max_messages = max_messages
        self.messages: deque[ChatMessage] = deque(maxlen=max_messages)
        self.current_task_id: Optional[str] = None
        self.pinned_items: List[str] = []

    def _importance(self, msg: ChatMessage) -> int:
        """Return an integer importance score for eviction ordering."""
        if msg.id in self.pinned_items:
            return 100
        if msg.type == MessageType.HITL_REQUEST:
            return 90
        if msg.type == MessageType.ERROR:
            return 85
        if msg.type == MessageType.PLAN_REQUEST:
            return 80
        if msg.type in (MessageType.RESULT_PREVIEW, MessageType.PLOT, MessageType.PLOT_DATA, MessageType.ARTIFACT):
            return 70
        if msg.type == MessageType.TODO_LIST:
            return 60
        if msg.sender == "user":
            return 50
        return 30

    def add_message(self, message: ChatMessage) -> None:
        self.messages.append(message)
        if len(self.messages) > self.max_messages:
            self._evict_least_important()

    def _evict_least_important(self) -> None:
        """Remove the least important non-pinned message when over soft limit."""
        candidates = [m for m in self.messages if m.id not in self.pinned_items]
        if not candidates:
            return
        candidates.sort(
            key=lambda m: (
                self._importance(m),
                m.timestamp or datetime.min.replace(tzinfo=timezone.utc),
            )
        )
        to_remove = candidates[0]
        # deque.remove is O(n); max_messages is small.
        self.messages.remove(to_remove)

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

    def to_context_items(self):
        """Convert messages to ContextParts for the ContextEngine."""
        # Local import to avoid a circular dependency with the ContextEngine.
        from homomics_lab.context.context_engine.models import ContextPart, ContextSource

        items: List[ContextPart] = []
        now = datetime.now(timezone.utc)
        for msg in self.messages:
            content = msg.content
            if not isinstance(content, str):
                try:
                    content = json.dumps(content, ensure_ascii=False)
                except Exception:
                    content = str(content)
            if not content.strip():
                continue
            hours = 0.0
            if msg.timestamp:
                try:
                    hours = (now - msg.timestamp).total_seconds() / 3600.0
                except Exception:
                    hours = 0.0
            items.append(
                ContextPart(
                    content=f"{msg.sender}: {content}",
                    source=ContextSource.CHAT,
                    priority=self._importance(msg),
                    is_pinned=msg.id in self.pinned_items,
                    is_upstream_result=bool(msg.task_id),
                    agent_importance=self._importance(msg) / 100.0,
                    hours_since_created=hours,
                    metadata={"message_id": msg.id, "task_id": msg.task_id},
                )
            )
        return items

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
