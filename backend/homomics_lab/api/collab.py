"""Real-time collaboration endpoints for shared workspaces.

Provides a lightweight WebSocket presence channel per project. Clients send
cursor position and editing state; the server broadcasts them to all other
clients in the same project. No persistence: presence is ephemeral and scoped
to the process.
"""

import asyncio
from typing import Dict, List, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from homomics_lab.api.auth import require_ws_auth

router = APIRouter()


class PresenceUser(BaseModel):
    user_id: str
    cursor_x: float | None = None
    cursor_y: float | None = None
    editing: bool = False
    color: str | None = None


class _ProjectRoom:
    """Manage all active connections for a single project."""

    def __init__(self) -> None:
        self.connections: Dict[str, WebSocket] = {}
        self.states: Dict[str, PresenceUser] = {}
        self._lock: Optional[asyncio.Lock] = None

    def _get_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def join(self, user_id: str, websocket: WebSocket) -> None:
        async with self._get_lock():
            self.connections[user_id] = websocket
            self.states[user_id] = PresenceUser(user_id=user_id)
        await self._broadcast_except(user_id, {"type": "user_joined", "user": self.states[user_id].model_dump()})

    async def leave(self, user_id: str) -> None:
        async with self._get_lock():
            self.connections.pop(user_id, None)
            self.states.pop(user_id, None)
        await self._broadcast_except(user_id, {"type": "user_left", "user_id": user_id})

    async def update_state(self, user_id: str, payload: Dict) -> None:
        async with self._get_lock():
            if user_id not in self.states:
                return
            state = self.states[user_id]
            if "cursor_x" in payload:
                state.cursor_x = payload["cursor_x"]
            if "cursor_y" in payload:
                state.cursor_y = payload["cursor_y"]
            if "editing" in payload:
                state.editing = payload["editing"]
            if "color" in payload:
                state.color = payload["color"]
        await self._broadcast_except(user_id, {"type": "presence", "user": state.model_dump()})

    async def _broadcast_except(self, sender_id: str, message: Dict) -> None:
        async with self._get_lock():
            recipients: List[WebSocket] = [
                ws for uid, ws in self.connections.items() if uid != sender_id
            ]
        if not recipients:
            return
        results = await asyncio.gather(
            *[self._safe_send(ws, message) for ws in recipients],
            return_exceptions=True,
        )
        for recipient, result in zip(recipients, results):
            if isinstance(result, Exception):
                # Disconnect broken sockets lazily.
                await self._disconnect(recipient)

    @staticmethod
    async def _safe_send(websocket: WebSocket, message: Dict) -> None:
        await websocket.send_json(message)

    async def _disconnect(self, websocket: WebSocket) -> None:
        async with self._get_lock():
            for uid, ws in list(self.connections.items()):
                if ws is websocket:
                    self.connections.pop(uid, None)
                    self.states.pop(uid, None)
                    break


class _RoomManager:
    def __init__(self) -> None:
        self._rooms: Dict[str, _ProjectRoom] = {}

    def room(self, project_id: str) -> _ProjectRoom:
        if project_id not in self._rooms:
            self._rooms[project_id] = _ProjectRoom()
        return self._rooms[project_id]

    def active_users(self, project_id: str) -> List[PresenceUser]:
        return list(self.room(project_id).states.values())


room_manager = _RoomManager()


@router.websocket("/{project_id}/ws")
async def collab_websocket(websocket: WebSocket, project_id: str):
    """WebSocket presence channel for a project.

    Expected client messages:
        {"type": "cursor", "cursor_x": 120, "cursor_y": 340}
        {"type": "editing", "editing": true}
    """
    await require_ws_auth(websocket)
    query_params = dict(websocket.query_params)
    user_id = query_params.get("user_id") or "anonymous"
    await websocket.accept()

    room = room_manager.room(project_id)
    await room.join(user_id, websocket)

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            if msg_type == "cursor":
                await room.update_state(
                    user_id,
                    {
                        "cursor_x": data.get("cursor_x"),
                        "cursor_y": data.get("cursor_y"),
                    },
                )
            elif msg_type == "editing":
                await room.update_state(user_id, {"editing": bool(data.get("editing"))})
            elif msg_type == "identify":
                await room.update_state(user_id, {"color": data.get("color")})
    except WebSocketDisconnect:
        await room.leave(user_id)
    except Exception:
        await room.leave(user_id)


@router.get("/{project_id}/presence", response_model=List[PresenceUser])
async def list_presence(project_id: str):
    """Return the list of users currently active in a project."""
    return room_manager.active_users(project_id)
