"""Tests for AgentMessageBus."""

import pytest

from homomics_lab.agent.message_bus import AgentMessageBus
from homomics_lab.models.common import AgentMessage


@pytest.mark.asyncio
async def test_publish_delivers_to_subscriber():
    bus = AgentMessageBus()
    received = []

    def on_message(topic, message):
        received.append((topic, message))

    bus.subscribe("swr", on_message)
    msg = AgentMessage(from_agent="supervisor", to_agent="worker", content="execute")
    await bus.publish("swr", msg)

    assert len(received) == 1
    assert received[0][0] == "swr"
    assert received[0][1].content == "execute"


@pytest.mark.asyncio
async def test_async_subscriber():
    bus = AgentMessageBus()
    received = []

    async def on_message(topic, message):
        received.append((topic, message.content))

    bus.subscribe("swr", on_message)
    await bus.publish("swr", AgentMessage(from_agent="worker", content="done"))

    assert received == [("swr", "done")]


@pytest.mark.asyncio
async def test_unsubscribe():
    bus = AgentMessageBus()
    received = []

    def on_message(topic, message):
        received.append(message.content)

    unsub = bus.subscribe("swr", on_message)
    unsub()
    await bus.publish("swr", AgentMessage(from_agent="supervisor", content="ignored"))

    assert received == []


def test_get_history():
    bus = AgentMessageBus()
    msg1 = AgentMessage(from_agent="a", content="first")
    msg2 = AgentMessage(from_agent="b", content="second")
    # publish is async, but history is appended synchronously; we can call it
    # directly via run_until_complete in a sync test, or just use the helper.
    import asyncio

    asyncio.run(bus.publish("topic", msg1))
    asyncio.run(bus.publish("topic", msg2))

    history = bus.get_history("topic")
    assert [m.content for m in history] == ["second", "first"]

    limited = bus.get_history("topic", limit=1)
    assert [m.content for m in limited] == ["second"]
