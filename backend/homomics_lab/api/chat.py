import logging
import uuid
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel

from homomics_lab.api.auth import require_auth, require_ws_auth
from homomics_lab.logging_config import get_correlation_id

from homomics_lab.agent.intent.analyzer import CascadeIntentAnalyzer as IntentAnalyzer
from homomics_lab.agent.sla import SLAEngine
from homomics_lab.agent.turn_runner import TurnRunner
from homomics_lab.api.chat_references import resolve_chat_references
from homomics_lab.api.deps import get_job_service, get_plan_store, get_trace_store
from homomics_lab.context.memory_manager import MemoryManager
from homomics_lab.debate_store import DebateStore
from homomics_lab.hitl.nlu import HITLNLUParser
from homomics_lab.hitl.preference_resolver import HITLPreferenceResolver
from homomics_lab.jobs import JobService, JobStatus
from homomics_lab.models.common import ChatMessage, MessageType
from homomics_lab.observability.trace_store import TraceStore
from homomics_lab.plan import PlanPresenter, PlanStore

router = APIRouter()
logger = logging.getLogger(__name__)

_debate_store = DebateStore()


class SendMessageRequest(BaseModel):
    project_id: str
    session_id: str
    message: str
    plan_mode: bool = False


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
    remember: bool = False


class HITLResponseResponse(BaseModel):
    message: str
    result: Dict[str, Any] = {}
    job_id: str | None = None
    status: str = "completed"


class ToolApprovalResponseRequest(BaseModel):
    session_id: str
    call_id: str
    approved: bool


class ToolApprovalResponseResponse(BaseModel):
    message: str
    response: str
    messages: List[dict]
    status: str


class DebateResponseRequest(BaseModel):
    session_id: str
    debate_id: str
    choice_id: str
    parameters: Dict[str, Any] = {}


class DebateResponseResponse(BaseModel):
    message: str
    result: Dict[str, Any] = {}
    status: str = "completed"


class ChatSessionSummary(BaseModel):
    id: str
    project_id: Optional[str]
    name: str
    updated_at: str
    created_at: str


class FeedbackResponse(BaseModel):
    status: str


@router.post("/send", response_model=SendMessageResponse, dependencies=[Depends(require_auth)])
async def send_message(
    request: SendMessageRequest,
    http_request: Request,
    job_service: JobService = Depends(get_job_service),
    plan_store: PlanStore = Depends(get_plan_store),
    trace_store: TraceStore = Depends(get_trace_store),
):
    memory_manager: MemoryManager = http_request.app.state.memory_manager
    working_memory, task_tree = await memory_manager.load_session(
        request.session_id, request.project_id
    )

    skill_executor = getattr(http_request.app.state, "skill_executor", None)
    user_message = await resolve_chat_references(
        request.message, request.project_id, skill_executor
    )

    trace_id = str(uuid.uuid4())
    try:
        await trace_store.start_trace(
            trace_id=trace_id,
            session_id=request.session_id,
            project_id=request.project_id,
            root_name="chat_turn",
        )
    except Exception as exc:
        logger.warning(
            "Failed to start execution trace (correlation_id=%s, session=%s): %s",
            get_correlation_id(),
            request.session_id,
            exc,
        )

    # Use TurnRunner for consistent handling of all intents, including LLM fallback.
    runner = TurnRunner(
        tool_registry=getattr(http_request.app.state, "tool_registry", None),
        memory_manager=memory_manager,
        cbkb=getattr(http_request.app.state, "cbkb", None),
        context_engine=getattr(http_request.app.state, "context_engine", None),
        project_state_manager=getattr(http_request.app.state, "project_state_manager", None),
        llm_client=getattr(http_request.app.state, "llm_client", None),
        trace_store=trace_store,
        capability_index=getattr(http_request.app.state, "capability_index", None),
        analysis_template_store=getattr(http_request.app.state, "analysis_template_store", None),
        workflow_execution_service=getattr(http_request.app.state, "workflow_execution_service", None),
        skill_executor=skill_executor,
    )
    result = await runner.run_turn(
        session_id=request.session_id,
        user_message=user_message,
        working_memory=working_memory,
        project_id=request.project_id,
        job_service=job_service,
        enqueue_skills=True,
        plan_store=plan_store,
        plan_mode=request.plan_mode,
        trace_id=trace_id,
    )

    # Extract plot attachments produced during execution
    plot_messages = result.attachments
    response_text = result.response_text

    agent_msg = result.agent_message
    if agent_msg is None:
        agent_msg = ChatMessage(
            id=f"msg_{len(working_memory.messages)}",
            type=MessageType.TEXT,
            content=response_text,
            sender="agent",
        )
        working_memory.add_message(agent_msg)

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
            await _debate_store.save(request.session_id, dict(result.agent_message.content))

    return SendMessageResponse(
        response=response_text,
        task_tree={"tasks": [t.model_dump() for t in result.task_tree.tasks]} if result.task_tree else {},
        messages=[m.model_dump() for m in working_memory.get_recent_messages()],
        attachments=[m.model_dump() for m in plot_messages],
        job_id=job_id,
        plan_id=plan_id,
        plan=plan_payload,
        status=status,
    )


@router.get("/messages", response_model=List[ChatMessage], dependencies=[Depends(require_auth)])
async def get_messages(session_id: str, http_request: Request) -> List[ChatMessage]:
    memory_manager: MemoryManager = http_request.app.state.memory_manager
    working_memory, _ = await memory_manager.load_session(session_id, "")
    return working_memory.get_recent_messages()


@router.get("/sessions", response_model=List[ChatSessionSummary], dependencies=[Depends(require_auth)])
async def list_sessions(http_request: Request, project_id: Optional[str] = None) -> List[ChatSessionSummary]:
    """List persisted chat sessions, optionally filtered by project."""
    memory_manager: MemoryManager = http_request.app.state.memory_manager
    return await memory_manager.list_sessions(project_id=project_id)


@router.post("/regenerate", response_model=SendMessageResponse, dependencies=[Depends(require_auth)])
async def regenerate_message(
    request: SendMessageRequest,
    http_request: Request,
    job_service: JobService = Depends(get_job_service),
    plan_store: PlanStore = Depends(get_plan_store),
):
    """Regenerate the last assistant response for the most recent user message."""
    memory_manager: MemoryManager = http_request.app.state.memory_manager
    working_memory, task_tree = await memory_manager.load_session(
        request.session_id, request.project_id
    )

    runner = TurnRunner(
        tool_registry=getattr(http_request.app.state, "tool_registry", None),
        memory_manager=memory_manager,
        cbkb=getattr(http_request.app.state, "cbkb", None),
        context_engine=getattr(http_request.app.state, "context_engine", None),
        project_state_manager=getattr(http_request.app.state, "project_state_manager", None),
        llm_client=getattr(http_request.app.state, "llm_client", None),
        capability_index=getattr(http_request.app.state, "capability_index", None),
        analysis_template_store=getattr(http_request.app.state, "analysis_template_store", None),
        workflow_execution_service=getattr(http_request.app.state, "workflow_execution_service", None),
    )
    result = await runner.regenerate_response(
        session_id=request.session_id,
        working_memory=working_memory,
        project_id=request.project_id,
        task_tree=task_tree,
        job_service=job_service,
        enqueue_skills=True,
        plan_store=plan_store,
        plan_mode=request.plan_mode,
    )

    plot_messages = result.attachments
    response_text = result.response_text

    agent_msg = result.agent_message
    if agent_msg is None:
        agent_msg = ChatMessage(
            id=f"msg_{len(working_memory.messages)}",
            type=MessageType.TEXT,
            content=response_text,
            sender="agent",
        )
        working_memory.add_message(agent_msg)

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
            await _debate_store.save(request.session_id, dict(result.agent_message.content))

    return SendMessageResponse(
        response=response_text,
        task_tree={"tasks": [t.model_dump() for t in result.task_tree.tasks]} if result.task_tree else {},
        messages=[m.model_dump() for m in working_memory.get_recent_messages()],
        attachments=[m.model_dump() for m in plot_messages],
        job_id=job_id,
        plan_id=plan_id,
        plan=plan_payload,
        status=status,
    )


@router.post("/hitl/respond", response_model=HITLResponseResponse, dependencies=[Depends(require_auth)])
async def respond_to_hitl(
    request: HITLResponseRequest,
    http_request: Request,
    job_service: JobService = Depends(get_job_service),
):

    # Find the job that is currently awaiting human input for this session.
    job = await job_service.get_latest_job(
        request.session_id,
        statuses=[JobStatus.AWAITING_HUMAN],
    )
    if job is None:
        raise HTTPException(status_code=404, detail="No awaiting HITL job found")
    if job.working_memory is None or job.task_tree is None:
        raise HTTPException(status_code=500, detail="HITL job is missing required context")

    choice = request.choice
    parameters = request.parameters

    # Find the checkpoint attached to the target task.
    checkpoint = None
    if job.task_tree is not None:
        for task in job.task_tree.tasks:
            if task.id == request.task_id and task.hitl_checkpoints:
                checkpoint = task.hitl_checkpoints[0].model_dump()
                break
    if checkpoint is None:
        checkpoint = getattr(job, "hitl_checkpoint", None)

    # Natural-language fallback: if the choice does not match a known option,
    # attempt to parse it as free text.
    if checkpoint is not None:
        option_ids = {str(o.get("id", "")) for o in checkpoint.get("options", [])}
        if choice not in option_ids:
            parsed = HITLNLUParser.parse(
                choice,
                checkpoint.get("options", []),
                parameters,
            )
            if parsed["choice"]:
                choice = parsed["choice"]
                parameters = {**parameters, **parsed.get("parameters", {})}

        # Record the resolved choice as a learned preference when requested.
        if request.remember and checkpoint is not None:
            preference_store = getattr(http_request.app.state, "preference_store", None)
            if preference_store is not None:
                resolver = HITLPreferenceResolver(preference_store)
                resolver.record_resolution(
                    project_id=job.project_id,
                    checkpoint=checkpoint,
                    choice=choice,
                    parameters=parameters,
                    remember=True,
                )

    resume_job = await job_service.create_resume_job(
        session_id=request.session_id,
        project_id=job.project_id,
        working_memory=job.working_memory,
        task_tree=job.task_tree,
        task_id=request.task_id,
        choice=choice,
        parameters=parameters,
    )

    return HITLResponseResponse(
        message="Task resumed successfully",
        job_id=resume_job.job_id,
        status="queued",
    )


@router.post("/tool-approval/respond", response_model=ToolApprovalResponseResponse, dependencies=[Depends(require_auth)])
async def respond_to_tool_approval(
    request: ToolApprovalResponseRequest,
    http_request: Request,
):
    """Approve or decline a high-risk tool call requested by the agent loop."""
    memory_manager: MemoryManager = http_request.app.state.memory_manager
    llm_client = getattr(http_request.app.state, "llm_client", None)
    tool_registry = getattr(http_request.app.state, "tool_registry", None)

    working_memory, _ = await memory_manager.load_session(request.session_id, "")
    project_id = await memory_manager.get_project_id(request.session_id)
    if project_id is None:
        project_id = "default"

    runner = TurnRunner(
        memory_manager=memory_manager,
        cbkb=getattr(http_request.app.state, "cbkb", None),
        context_engine=getattr(http_request.app.state, "context_engine", None),
        project_state_manager=getattr(http_request.app.state, "project_state_manager", None),
        llm_client=llm_client,
        tool_registry=tool_registry,
        capability_index=getattr(http_request.app.state, "capability_index", None),
        analysis_template_store=getattr(http_request.app.state, "analysis_template_store", None),
        workflow_execution_service=getattr(http_request.app.state, "workflow_execution_service", None),
    )
    result = await runner.respond_to_tool_approval(
        call_id=request.call_id,
        approved=request.approved,
        working_memory=working_memory,
        project_id=project_id,
    )

    await memory_manager.save_session(request.session_id, project_id, working_memory)

    return ToolApprovalResponseResponse(
        message="Tool approval processed",
        response=result.response_text,
        messages=[m.model_dump() for m in working_memory.get_recent_messages()],
        status="completed",
    )


@router.post("/debate/respond", response_model=DebateResponseResponse, dependencies=[Depends(require_auth)])
async def respond_to_debate(
    request: DebateResponseRequest,
    http_request: Request,
    job_service: JobService = Depends(get_job_service),
    plan_store: PlanStore = Depends(get_plan_store),
):
    memory_manager: MemoryManager = http_request.app.state.memory_manager
    working_memory, _ = await memory_manager.load_session(request.session_id, "")

    debate = await _debate_store.get(request.session_id)
    if debate is None or debate.get("debate_id") != request.debate_id:
        raise HTTPException(status_code=404, detail="Debate not found")

    options = debate.get("options", [])
    chosen = next((o for o in options if o.get("id") == request.choice_id), None)
    if chosen is None:
        raise HTTPException(status_code=400, detail="Invalid debate choice")

    project_id = await memory_manager.get_project_id(request.session_id)
    if project_id is None:
        project_id = "default"

    runner = TurnRunner(
        memory_manager=memory_manager,
        cbkb=getattr(http_request.app.state, "cbkb", None),
        context_engine=getattr(http_request.app.state, "context_engine", None),
        project_state_manager=getattr(http_request.app.state, "project_state_manager", None),
        llm_client=getattr(http_request.app.state, "llm_client", None),
        capability_index=getattr(http_request.app.state, "capability_index", None),
        analysis_template_store=getattr(http_request.app.state, "analysis_template_store", None),
        workflow_execution_service=getattr(http_request.app.state, "workflow_execution_service", None),
    )
    user_message = f"我选择 {chosen.get('label', request.choice_id)}"
    result = await runner.run_turn(
        session_id=request.session_id,
        user_message=user_message,
        working_memory=working_memory,
        project_id=project_id,
        job_service=job_service,
        enqueue_skills=True,
        plan_store=plan_store,
        debate_response={
            "choice_id": request.choice_id,
            "parameters": request.parameters,
        },
    )

    await _debate_store.delete(request.session_id)

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

    Receives JSON messages of the form ``{"project_id": "...", "message": "...", "stream": true}``
    and pushes back the agent reply together with any plot attachments. When
    ``stream`` is true the raw LLM tokens are streamed directly.
    """
    await require_ws_auth(websocket)
    await websocket.accept()
    memory_manager: MemoryManager = websocket.app.state.memory_manager
    llm_client = getattr(websocket.app.state, "llm_client", None)
    runner = TurnRunner(
        memory_manager=memory_manager,
        cbkb=getattr(websocket.app.state, "cbkb", None),
        context_engine=getattr(websocket.app.state, "context_engine", None),
        project_state_manager=getattr(websocket.app.state, "project_state_manager", None),
        llm_client=llm_client,
        analysis_template_store=getattr(websocket.app.state, "analysis_template_store", None),
        workflow_execution_service=getattr(websocket.app.state, "workflow_execution_service", None),
    )

    try:
        while True:
            data = await websocket.receive_json()
            project_id = data.get("project_id", "default")
            raw_message = data.get("message", "")

            # Stream raw LLM tokens for direct user queries
            if data.get("stream") and llm_client is not None:
                messages = [
                    {
                        "role": "system",
                        "content": "You are a helpful bioinformatics assistant.",
                    },
                    {"role": "user", "content": raw_message},
                ]
                try:
                    async for token in llm_client.chat_completion_stream(messages=messages):
                        await websocket.send_json({"type": "token", "token": token})
                    await websocket.send_json({"type": "token", "done": True})
                except Exception as exc:
                    logger.warning(
                        "WebSocket streaming failed (correlation_id=%s, session=%s): %s",
                        get_correlation_id(),
                        session_id,
                        exc,
                    )
                    await websocket.send_json({"type": "error", "error": str(exc)})
                continue

            skill_executor = getattr(websocket.app.state, "skill_executor", None)
            user_message = await resolve_chat_references(
                raw_message, project_id, skill_executor
            )

            working_memory, _ = await memory_manager.load_session(session_id, project_id)

            async def _event_callback(payload: Dict[str, Any]) -> None:
                await websocket.send_json({"type": "agent_event", "payload": payload})

            result = await runner.run_turn(
                session_id=session_id,
                user_message=user_message,
                working_memory=working_memory,
                project_id=project_id,
                event_callback=_event_callback,
            )

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


class FeedbackRequest(BaseModel):
    message_id: str
    rating: str  # "positive" | "negative"
    comment: Optional[str] = None


class SLARequest(BaseModel):
    message: str


class SLAResponse(BaseModel):
    execution_mode: str
    confidence: float
    estimated_steps: int
    required_skills: List[str]
    missing_skills: List[str]
    estimated_llm_cost_usd: Optional[float]
    estimated_compute_cost_usd: Optional[float]
    risks: List[str]
    explanation: str
    nfcore_pipeline: Optional[str] = None


@router.post("/feedback", response_model=FeedbackResponse, dependencies=[Depends(require_auth)])
async def submit_feedback(
    request: FeedbackRequest,
    http_request: Request,
):
    """Record user feedback (thumbs up/down) on a chat message."""
    from homomics_lab.metrics import record_message_feedback

    session_id = getattr(http_request.state, "session_id", None)
    record_message_feedback(
        message_id=request.message_id,
        rating=request.rating,
        session_id=session_id,
        comment=request.comment,
    )
    return FeedbackResponse(status="ok")


@router.post("/sla", response_model=SLAResponse, dependencies=[Depends(require_auth)])
async def assess_sla(
    request: SLARequest,
    http_request: Request,
):
    """Assess agent confidence and execution mode for a user message.

    This endpoint does not execute anything; it tells the user whether the
    agent can auto-run, needs confirmation, or requires human help.
    """
    intent_analyzer = IntentAnalyzer()
    intent = await intent_analyzer.analyze(request.message)

    skill_registry = getattr(
        http_request.app.state, "skill_executor", None
    )
    if skill_registry is not None:
        skill_registry = skill_registry.registry
    sla_engine = SLAEngine(skill_registry=skill_registry)
    sla = sla_engine.assess(intent)
    return SLAResponse(**sla.to_dict())
