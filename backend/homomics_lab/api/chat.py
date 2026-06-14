from typing import List, Dict, Any
from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel

from homomics_lab.agent.turn_runner import TurnRunner
from homomics_lab.context.working_memory import WorkingMemory
from homomics_lab.jobs import JobService, JobStatus
from homomics_lab.models.common import ChatMessage, MessageType
from homomics_lab.plan import PlanPresenter, PlanStore
from homomics_lab.tasks.task_tree import TaskTree

router = APIRouter()

# In-memory session store for MVP
_sessions: dict[str, WorkingMemory] = {}
_task_trees: dict[str, TaskTree] = {}
_session_project_ids: dict[str, str] = {}
_debates: dict[str, dict] = {}


class SendMessageRequest(BaseModel):
    project_id: str
    session_id: str
    message: str


class SendMessageResponse(BaseModel):
    response: str
    task_tree: dict
    messages: List[dict]
    attachments: List[dict] = []
    job_id: str | None = None
    plan_id: str | None = None
    plan: dict | None = None
    status: str = "completed"


class HITLResponseRequest(BaseModel):
    session_id: str
    task_id: str
    choice: str
    parameters: Dict[str, Any] = {}


class HITLResponseResponse(BaseModel):
    message: str
    result: Dict[str, Any] = {}
    job_id: str | None = None
    status: str = "completed"


class DebateResponseRequest(BaseModel):
    session_id: str
    debate_id: str
    choice_id: str
    parameters: Dict[str, Any] = {}


class DebateResponseResponse(BaseModel):
    message: str
    result: Dict[str, Any] = {}
    status: str = "completed"


@router.post("/send", response_model=SendMessageResponse)
async def send_message(
    request: SendMessageRequest,
    http_request: Request,
):
    # Get or create session memory
    wm = _sessions.get(request.session_id, WorkingMemory())
    _sessions[request.session_id] = wm
    _session_project_ids[request.session_id] = request.project_id

    job_service: JobService = getattr(
        http_request.app.state, "job_service", None
    ) or JobService()
    plan_store: PlanStore = getattr(
        http_request.app.state, "plan_store", None
    ) or PlanStore()

    # Use TurnRunner for consistent handling of all intents, including LLM fallback.
    runner = TurnRunner(tool_registry=getattr(http_request.app.state, "tool_registry", None))
    result = await runner.run_turn(
        session_id=request.session_id,
        user_message=request.message,
        working_memory=wm,
        project_id=request.project_id,
        job_service=job_service,
        enqueue_skills=True,
        plan_store=plan_store,
    )

    if result.task_tree is not None:
        _task_trees[request.session_id] = result.task_tree

    # Extract plot attachments produced during execution
    plot_messages = result.attachments
    response_text = result.response_text

    agent_msg = result.agent_message
    if agent_msg is None:
        agent_msg = ChatMessage(
            id=f"msg_{len(wm.messages)}",
            type=MessageType.TEXT,
            content=response_text,
            sender="agent",
        )
        wm.add_message(agent_msg)

    status = "completed"
    job_id = None
    plan_id = result.plan_id
    plan_payload = None
    if result.mode == "queued":
        status = "queued"
        job_id = result.job_id
    elif result.mode == "awaiting_plan_approval":
        status = "awaiting_plan_approval"
        if plan_id is not None:
            plan = await plan_store.get(plan_id)
            if plan is not None:
                plan_payload = PlanPresenter.to_user_payload(plan)
    elif result.mode == "awaiting_debate":
        status = "awaiting_debate"
        if result.agent_message is not None and isinstance(result.agent_message.content, dict):
            _debates[request.session_id] = dict(result.agent_message.content)

    return SendMessageResponse(
        response=response_text,
        task_tree={"tasks": [t.model_dump() for t in result.task_tree.tasks]} if result.task_tree else {},
        messages=[m.model_dump() for m in wm.get_recent_messages()],
        attachments=[m.model_dump() for m in plot_messages],
        job_id=job_id,
        plan_id=plan_id,
        plan=plan_payload,
        status=status,
    )


@router.get("/messages")
async def get_messages(session_id: str) -> List[dict]:
    wm = _sessions.get(session_id)
    if not wm:
        return []
    return [m.model_dump() for m in wm.get_recent_messages()]


@router.post("/hitl/respond", response_model=HITLResponseResponse)
async def respond_to_hitl(
    request: HITLResponseRequest,
    http_request: Request,
):
    job_service: JobService = getattr(
        http_request.app.state, "job_service", None
    ) or JobService()

    # Find the job that is currently awaiting human input for this session.
    job = await job_service.get_latest_job(
        request.session_id,
        statuses=[JobStatus.AWAITING_HUMAN],
    )
    if job is None:
        raise HTTPException(status_code=404, detail="No awaiting HITL job found")

    resume_job = await job_service.create_resume_job(
        session_id=request.session_id,
        project_id=job.project_id,
        working_memory=job.working_memory,
        task_tree=job.task_tree,
        task_id=request.task_id,
        choice=request.choice,
        parameters=request.parameters,
    )

    return HITLResponseResponse(
        message="Task resumed successfully",
        job_id=resume_job.job_id,
        status="queued",
    )


@router.post("/debate/respond", response_model=DebateResponseResponse)
async def respond_to_debate(
    request: DebateResponseRequest,
    http_request: Request,
):
    wm = _sessions.get(request.session_id)
    if wm is None:
        raise HTTPException(status_code=404, detail="Session not found")

    debate = _debates.get(request.session_id)
    if debate is None or debate.get("debate_id") != request.debate_id:
        raise HTTPException(status_code=404, detail="Debate not found")

    options = debate.get("options", [])
    chosen = next((o for o in options if o.get("id") == request.choice_id), None)
    if chosen is None:
        raise HTTPException(status_code=400, detail="Invalid debate choice")

    job_service: JobService = getattr(
        http_request.app.state, "job_service", None
    ) or JobService()
    plan_store: PlanStore = getattr(
        http_request.app.state, "plan_store", None
    ) or PlanStore()

    runner = TurnRunner()
    user_message = f"我选择 {chosen.get('label', request.choice_id)}"
    result = await runner.run_turn(
        session_id=request.session_id,
        user_message=user_message,
        working_memory=wm,
        project_id=_session_project_ids.get(request.session_id, "default"),
        job_service=job_service,
        enqueue_skills=True,
        plan_store=plan_store,
        debate_response={
            "choice_id": request.choice_id,
            "parameters": request.parameters,
        },
    )

    if result.task_tree is not None:
        _task_trees[request.session_id] = result.task_tree

    status = "completed"
    if result.mode == "queued":
        status = "queued"
    elif result.mode == "awaiting_plan_approval":
        status = "awaiting_plan_approval"
    elif result.mode == "awaiting_hitl":
        status = "awaiting_hitl"

    return DebateResponseResponse(
        message=result.response_text,
        result={
            "status": status,
            "job_id": result.job_id,
            "plan_id": result.plan_id,
            "task_tree": (
                {"tasks": [t.model_dump() for t in result.task_tree.tasks]}
                if result.task_tree else {}
            ),
        },
        status=status,
    )


@router.websocket("/ws/{session_id}")
async def chat_websocket(websocket: WebSocket, session_id: str):
    """Realtime chat WebSocket.

    Receives JSON messages of the form ``{"project_id": "...", "message": "..."}``
    and pushes back the agent reply together with any plot attachments.
    """
    await websocket.accept()
    runner = TurnRunner()

    try:
        while True:
            data = await websocket.receive_json()
            project_id = data.get("project_id", "default")
            user_message = data.get("message", "")

            wm = _sessions.get(session_id, WorkingMemory())
            _sessions[session_id] = wm

            result = await runner.run_turn(
                session_id=session_id,
                user_message=user_message,
                working_memory=wm,
                project_id=project_id,
            )

            if result.task_tree is not None:
                _task_trees[session_id] = result.task_tree

            # Push back the main agent message
            if result.agent_message is not None:
                await websocket.send_json({
                    "type": result.agent_message.type.value,
                    "message": result.agent_message.model_dump(),
                })

            # Push any plot attachments separately so the frontend can render them
            for attachment in result.attachments:
                await websocket.send_json({
                    "type": attachment.type.value,
                    "message": attachment.model_dump(),
                })

    except WebSocketDisconnect:
        pass
