import pytest
from homics_lab.agent.message_bus import MessageBus
from homics_lab.models.common import AgentMessage


@pytest.fixture
def bus():
    return MessageBus()


@pytest.mark.asyncio
async def test_send_and_receive(bus):
    await bus.send(AgentMessage(from_agent="a", to_agent="b", content="hello"))
    messages = await bus.get_messages_for("b")
    assert len(messages) == 1
    assert messages[0].content == "hello"


@pytest.mark.asyncio
async def test_broadcast(bus):
    await bus.broadcast(AgentMessage(from_agent="a", to_agent=None, content="all"))
    messages = await bus.get_all_messages()
    assert len(messages) == 1
    assert messages[0].content == "all"


@pytest.mark.asyncio
async def test_clear_messages(bus):
    await bus.send(AgentMessage(from_agent="a", to_agent="b", content="hello"))
    await bus.clear("b")
    messages = await bus.get_messages_for("b")
    assert len(messages) == 0
