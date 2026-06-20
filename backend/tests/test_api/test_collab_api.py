"""Tests for the real-time collaboration WebSocket and presence REST API."""

import asyncio

import pytest
from fastapi.testclient import TestClient

from homomics_lab.api.collab import _ProjectRoom
from homomics_lab.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_presence_rest_empty(client):
    response = client.get("/api/collab/proj_123/presence")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_room_join_broadcasts_to_other_users():
    room = _ProjectRoom()

    class FakeSocket:
        def __init__(self):
            self.sent: list = []

        async def send_json(self, data):
            self.sent.append(data)

        async def receive_json(self):
            # Never returns in this unit test.
            await asyncio.sleep(3600)

    alice = FakeSocket()
    bob = FakeSocket()

    await room.join("alice", alice)
    await room.join("bob", bob)

    assert len(alice.sent) == 1
    assert alice.sent[0]["type"] == "user_joined"
    assert alice.sent[0]["user"]["user_id"] == "bob"
    assert len(bob.sent) == 0


@pytest.mark.asyncio
async def test_room_cursor_update_broadcasts():
    room = _ProjectRoom()

    class FakeSocket:
        def __init__(self):
            self.sent: list = []

        async def send_json(self, data):
            self.sent.append(data)

    alice = FakeSocket()
    bob = FakeSocket()

    await room.join("alice", alice)
    await room.join("bob", bob)
    alice.sent.clear()

    await room.update_state("bob", {"cursor_x": 42, "cursor_y": 99})

    assert len(alice.sent) == 1
    assert alice.sent[0]["type"] == "presence"
    assert alice.sent[0]["user"]["cursor_x"] == 42


@pytest.mark.asyncio
async def test_room_leave_broadcasts():
    room = _ProjectRoom()

    class FakeSocket:
        def __init__(self):
            self.sent: list = []

        async def send_json(self, data):
            self.sent.append(data)

    alice = FakeSocket()
    bob = FakeSocket()

    await room.join("alice", alice)
    await room.join("bob", bob)
    alice.sent.clear()

    await room.leave("bob")

    assert len(alice.sent) == 1
    assert alice.sent[0]["type"] == "user_left"
    assert alice.sent[0]["user_id"] == "bob"
