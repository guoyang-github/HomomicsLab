from collections import defaultdict
from typing import Dict, List
from homomics_lab.models.common import AgentMessage


class MessageBus:
    """In-memory message bus for inter-agent communication."""

    def __init__(self):
        self._inboxes: Dict[str, List[AgentMessage]] = defaultdict(list)
        self._broadcasts: List[AgentMessage] = []

    async def send(self, message: AgentMessage) -> None:
        if message.to_agent:
            self._inboxes[message.to_agent].append(message)
        else:
            self._broadcasts.append(message)

    async def broadcast(self, message: AgentMessage) -> None:
        self._broadcasts.append(message)

    async def get_messages_for(self, agent_name: str) -> List[AgentMessage]:
        return list(self._inboxes[agent_name])

    async def get_all_messages(self) -> List[AgentMessage]:
        all_msgs = []
        for msgs in self._inboxes.values():
            all_msgs.extend(msgs)
        all_msgs.extend(self._broadcasts)
        return all_msgs

    async def clear(self, agent_name: str = None) -> None:
        if agent_name:
            self._inboxes[agent_name].clear()
        else:
            self._inboxes.clear()
            self._broadcasts.clear()
