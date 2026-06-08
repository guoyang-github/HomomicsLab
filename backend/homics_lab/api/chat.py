from typing import List, Dict, Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel

from homics_lab.agent.agent_registry import get_default_registry
from homics_lab.agent.factory import create_default_agents
from homics_lab.agent.intent_analyzer import IntentAnalyzer
from homics_lab.agent.orchestrator import Orchestrator
from homics_lab.agent.task_decomposer import TaskDecomposer
from homics_lab.context.working_memory import WorkingMemory
from homics_lab.models.common import ChatMessage, MessageType
from homics_lab.tasks.task_tree import TaskTree

router = APIRouter()

# In-memory session store for MVP
_sessions: dict[str, WorkingMemory] = {}
_task_trees: dict[str, TaskTree] = {}


class SendMessageRequest(BaseModel):
    project_id: str
    session_id: str
    message: str


class SendMessageResponse(BaseModel):
    response: str
    task_tree: dict
    messages: List[dict]


class HITLResponseRequest(BaseModel):
    session_id: str
    task_id: str
    choice: str
    parameters: Dict[str, Any] = {}


class HITLResponseResponse(BaseModel):
    message: str
    result: Dict[str, Any]


@router.post("/send", response_model=SendMessageResponse)
async def send_message(request: SendMessageRequest):
    # Get or create session memory
    wm = _sessions.get(request.session_id, WorkingMemory())
    _sessions[request.session_id] = wm

    # Add user message
    user_msg = ChatMessage(
        id=f"msg_{len(wm.messages)}",
        type=MessageType.TEXT,
        content=request.message,
        sender="user",
    )
    wm.add_message(user_msg)

    # Analyze intent
    analyzer = IntentAnalyzer()
    intent = await analyzer.analyze(request.message)

    # Decompose into task tree
    decomposer = TaskDecomposer()
    tree = await decomposer.decompose(intent, context={"project_id": request.project_id})
    _task_trees[request.session_id] = tree

    # Ensure agents are registered
    registry = get_default_registry()
    if not registry.list_agents():
        create_default_agents()

    # Run orchestrator
    orchestrator = Orchestrator(registry=registry)
    results = await orchestrator.run_tree(tree)

    # Build response
    response_text = f"已为您规划 {len(tree.tasks)} 个分析步骤。"
    if any("hitl" in r for r in results.values()):
        response_text += " 部分步骤需要您确认参数。"

    # Add agent message
    agent_msg = ChatMessage(
        id=f"msg_{len(wm.messages)}",
        type=MessageType.TODO_LIST,
        content={
            "text": response_text,
            "tasks": [t.model_dump() for t in tree.tasks],
            "progress": orchestrator.get_progress(tree),
        },
        sender="agent",
    )
    wm.add_message(agent_msg)

    return SendMessageResponse(
        response=response_text,
        task_tree={"tasks": [t.model_dump() for t in tree.tasks]},
        messages=[m.model_dump() for m in wm.get_recent_messages()],
    )


@router.get("/messages")
async def get_messages(session_id: str) -> List[dict]:
    wm = _sessions.get(session_id)
    if not wm:
        return []
    return [m.model_dump() for m in wm.get_recent_messages()]


@router.post("/hitl/respond", response_model=HITLResponseResponse)
async def respond_to_hitl(request: HITLResponseRequest):
    tree = _task_trees.get(request.session_id)
    if not tree:
        raise HTTPException(status_code=404, detail="Session not found")

    registry = get_default_registry()
    if not registry.list_agents():
        create_default_agents()

    orchestrator = Orchestrator(registry=registry)
    result = await orchestrator.resume_task(
        tree,
        request.task_id,
        {"choice": request.choice, "parameters": request.parameters},
    )

    return HITLResponseResponse(
        message="Task resumed successfully",
        result=result,
    )


@router.websocket("/ws/{session_id}")
async def chat_websocket(websocket: WebSocket, session_id: str):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            # Echo back with type
            await websocket.send_json({
                "type": "ack",
                "session_id": session_id,
                "received": data,
            })
    except WebSocketDisconnect:
        pass
