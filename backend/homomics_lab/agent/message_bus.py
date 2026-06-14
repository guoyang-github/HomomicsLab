"""AgentMessageBus — lightweight in-memory pub/sub for agent collaboration.

Supports Supervisor ↔ Worker ↔ Reviewer messaging. The current implementation
is in-memory; it can later be replaced with Redis/RabbitMQ without changing the
public interface.
"""

import inspect
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional

from homomics_lab.models.common import AgentMessage


class AgentMessageBus:
    """In-memory message bus for inter-agent communication."""

    def __init__(self):
        self._callbacks: Dict[str, List[Callable[[str, AgentMessage], Any]]] = defaultdict(list)
        self._history: Dict[str, List[AgentMessage]] = defaultdict(list)

    def subscribe(
        self,
        topic: str,
        callback: Callable[[str, AgentMessage], Any],
    ) -> Callable[[], None]:
        """Subscribe to a topic.

        Returns an unsubscribe function.
        """
        self._callbacks[topic].append(callback)

        def unsubscribe() -> None:
            try:
                self._callbacks[topic].remove(callback)
            except ValueError:
                pass

        return unsubscribe

    async def publish(self, topic: str, message: AgentMessage) -> None:
        """Publish a message to all subscribers of a topic."""
        self._history[topic].append(message)
        for callback in list(self._callbacks[topic]):
            result = callback(topic, message)
            if inspect.isawaitable(result):
                await result

    def get_history(self, topic: str, limit: Optional[int] = None) -> List[AgentMessage]:
        """Return published messages for a topic, newest first."""
        history = list(reversed(self._history[topic]))
        if limit is not None:
            history = history[:limit]
        return history

    def clear(self) -> None:
        """Clear all subscriptions and history."""
        self._callbacks.clear()
        self._history.clear()
