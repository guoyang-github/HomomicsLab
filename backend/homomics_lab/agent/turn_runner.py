"""Unified TurnRunner — single execution loop for all conversational turns.

The TurnRunner handles every user message through a single, consistent pipeline:
  1. Load context (working memory, pinned items, previous task trees)
  2. Analyze intent (direct response, single step, complex workflow)
  3. Route to the appropriate execution mode
  4. Execute (or schedule for execution)
  5. Format output (text, TODO list, HITL request, error)
  6. Save state (working memory, task tree)

This replaces the ad-hoc logic in chat.py with a testable, extensible loop.
"""

import json
import asyncio
import logging
import random
import time
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple, Union

from homomics_lab.agent.agent_registry import AgentRegistry, get_default_registry
from homomics_lab.agent.agent_loop import AgentLoop, ToolCallRecord, TurnBudget
from homomics_lab.agent.debate import LightweightDebate
from homomics_lab.agent.errors import (
    ExecutionError,
    IntentError,
    TurnError,
)
from homomics_lab.agent.factory import create_default_agents
from homomics_lab.agent.general_agent import GeneralScientificAgent
from homomics_lab.agent.intent_analyzer import IntentAnalyzer, UserIntent
from homomics_lab.agent.open_agent.executor import OpenAgentExecutor
from homomics_lab.agent.message_bus import AgentMessageBus
from homomics_lab.agent.orchestrator import Orchestrator
from homomics_lab.agent.phase_gate import PhaseGateEvaluator
from homomics_lab.agent.plan.replanning import DynamicReplanningEngine
from homomics_lab.agent.plan.self_correction import SelfCorrectionEngine
from homomics_lab.agent.task_decomposer import TaskDecomposer
from homomics_lab.agent.turn_clarification import ClarificationHandler
from homomics_lab.agent.turn_context_formatter import ContextFormatter
from homomics_lab.agent.turn_file_resolver import FileReferenceResolver
from homomics_lab.agent.turn_intent_router import IntentRouter
from homomics_lab.agent.turn_response_generator import ResponseGenerator
from homomics_lab.agent.turn_result_assembler import ResultAssembler
from homomics_lab.agent.turn_risk_assessor import RiskAssessor
from homomics_lab.agent.turn_self_correction import SelfCorrectionHandler
from homomics_lab.agent.turn_workflow_handler import WorkflowHandler
from homomics_lab.agent.permission_ruleset import (
    PermissionRegistry,
    get_permission_registry,
)
from homomics_lab.config import settings
from homomics_lab.workflow.execution_service import WorkflowExecutionService
from homomics_lab.context.compressor import ContextCompressor
from homomics_lab.context.context_engine.engine import ContextEngine
from homomics_lab.context.context_engine.models import ContextBundle
from homomics_lab.context.feedback_store import FeedbackOutcome
from homomics_lab.context.memory_backend import MemoryBackend
from homomics_lab.context.memory_manager import MemoryManager
from homomics_lab.context.project_state import ProjectStateManager
from homomics_lab.context.prompter import Prompter
from homomics_lab.context.working_memory import WorkingMemory
from homomics_lab.hpc.state import ExecutionState
from homomics_lab.workspace.context import current_workspace
from homomics_lab.workspace.manager import WorkspaceManager
from homomics_lab.llm_client import LLMClient
from homomics_lab.models.common import (
    ChatMessage,
    HITLCheckpoint,
    HITLTrigger,
    MessageType,
    Option,
)
from homomics_lab.plan.models import Plan
from homomics_lab.tools.registry import ToolRegistry
from homomics_lab.plan.store import PlanStore
from homomics_lab.plots import extract_plot_attachments
from homomics_lab.skills.capability_index import CapabilityIndex, CapabilityType
from homomics_lab.tasks.models import TaskStatus
from homomics_lab.tasks.task_tree import TaskTree

logger = logging.getLogger(__name__)


class ExecutionMode(str, Enum):
    """All possible outcomes of a single conversational turn."""

    DIRECT_RESPONSE = "direct_response"
    """Answered immediately without skill execution (e.g., QA)."""

    SINGLE_STEP = "single_step"
    """One skill executed, result returned immediately."""

    WORKFLOW = "workflow"
    """Multi-step task tree executed (possibly with parallel steps)."""

    AWAITING_HITL = "awaiting_hitl"
    """Execution paused, waiting for human input."""

    RESUME_HITL = "resume_hitl"
    """Resumed from HITL and continued execution."""

    QUEUED = "queued"
    """Submitted to the background job queue for execution."""

    AWAITING_PLAN_APPROVAL = "awaiting_plan_approval"
    """Execution paused, waiting for user approval of the generated plan."""

    AWAITING_DEBATE = "awaiting_debate"
    """Execution paused, waiting for user to resolve a debate."""

    ERROR = "error"
    """Something went wrong during the turn."""


class TurnResult:
    """Unified result of a single turn.

    Contains everything the caller (e.g., chat API) needs to send a response
    back to the user, regardless of execution mode.
    """

    def __init__(
        self,
        mode: ExecutionMode,
        response_text: str,
        task_tree: Optional[TaskTree] = None,
        progress: Optional[Dict[str, Any]] = None,
        hitl_task_id: Optional[str] = None,
        hitl_checkpoint: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        agent_message: Optional[ChatMessage] = None,
        attachments: Optional[List[ChatMessage]] = None,
        job_id: Optional[str] = None,
        plan_id: Optional[str] = None,
    ):
        self.mode = mode
        self.response_text = response_text
        self.task_tree = task_tree
        self.progress = progress
        self.hitl_task_id = hitl_task_id
        self.hitl_checkpoint = hitl_checkpoint
        self.error = error
        self.agent_message = agent_message
        self.attachments = attachments or []
        self.job_id = job_id
        self.plan_id = plan_id


class TurnRunner:
    """Executes one conversational turn end-to-end.

    Usage:
        runner = TurnRunner()
        result = await runner.run_turn(
            session_id="sess_1",
            user_message="帮我分析单细胞数据",
            working_memory=wm,
            project_id="proj_1",
        )
        # result.response_text, result.task_tree, result.progress, ...
    """

    def __init__(
        self,
        intent_analyzer: Optional[IntentAnalyzer] = None,
        task_decomposer: Optional[TaskDecomposer] = None,
        orchestrator: Optional[Orchestrator] = None,
        registry: Optional[AgentRegistry] = None,
        progress_callback: Optional[Callable[[ExecutionState], None]] = None,
        workspace_manager=None,
        phase_gate_evaluator: Optional[PhaseGateEvaluator] = None,
        replanning_engine: Optional[DynamicReplanningEngine] = None,
        self_correction_engine: Optional[SelfCorrectionEngine] = None,
        general_agent: Optional[GeneralScientificAgent] = None,
        supervisor=None,
        reviewer=None,
        message_bus: Optional[AgentMessageBus] = None,
        debate: Optional[Any] = None,
        tool_registry: Optional[ToolRegistry] = None,
        cbkb=None,
        memory_manager: Optional[MemoryManager] = None,
        prompter: Optional[Prompter] = None,
        compressor: Optional[ContextCompressor] = None,
        context_engine: Optional[ContextEngine] = None,
        project_state_manager: Optional[ProjectStateManager] = None,
        llm_client: Optional[LLMClient] = None,
        trace_store=None,
        approval_store=None,
        capability_index: Optional[CapabilityIndex] = None,
        memory_backend: Optional[MemoryBackend] = None,
        analysis_template_store: Optional[Any] = None,
        workflow_execution_service: Optional[WorkflowExecutionService] = None,
        skill_executor: Optional[Any] = None,
        permission_registry: Optional[PermissionRegistry] = None,
        skill_dag: Optional[Any] = None,
    ):
        self._cbkb = cbkb
        self.skill_dag = skill_dag
        self._skill_executor = skill_executor
        self._llm_client = llm_client
        self._trace_store = trace_store
        self._approval_store = approval_store
        self._permission_registry = permission_registry or get_permission_registry()
        self._orchestrator = orchestrator
        self._registry = registry
        self._progress_callback = progress_callback
        self._workspace_manager = workspace_manager
        self._phase_gate_evaluator = phase_gate_evaluator
        self._replanning_engine = replanning_engine
        self._self_correction_engine = self_correction_engine
        self._general_agent = general_agent
        self._supervisor = supervisor
        self._reviewer = reviewer
        self._message_bus = message_bus
        self._open_agent_executor: Optional[OpenAgentExecutor] = None
        self._tool_registry = tool_registry
        self.memory_manager = memory_manager
        self.memory_backend = memory_backend
        self.capability_index = capability_index
        self.prompter = prompter or Prompter()
        self.compressor = compressor or ContextCompressor(
            max_items=6, max_chars_per_item=1000
        )
        self.context_engine = context_engine
        self.project_state_manager = project_state_manager
        self._workflow_execution_service = workflow_execution_service
        self._extra_context: Dict[str, Any] = {}
        self._context_bundle: Optional[ContextBundle] = None

        # Configure debate judge based on settings and available LLM client.
        if debate is not None:
            self._debate = debate
        else:
            judge = None
            if settings.debate_judge_backend == "llm" and self._llm_client is not None:
                from homomics_lab.agent.debate import LLMDebateJudge

                judge = LLMDebateJudge(self._llm_client)
            self._debate = LightweightDebate(judge=judge)

        self.intent_analyzer = intent_analyzer or IntentAnalyzer(
            debate=self._debate, cbkb=self._cbkb
        )
        self.task_decomposer = task_decomposer or TaskDecomposer(
            cbkb=self._cbkb,
            capability_index=self.capability_index,
            analysis_template_store=analysis_template_store,
        )

        # Collaborators extracted from TurnRunner (pure code move, no logic
        # changes). The private delegate shells live at the end of the class.
        self._result_assembler = ResultAssembler(self)
        self._context_formatter = ContextFormatter(self)
        self._risk_assessor = RiskAssessor(self)
        self._file_resolver = FileReferenceResolver(self)
        self._clarification_handler = ClarificationHandler(self)
        self._intent_router = IntentRouter(self)
        self._response_generator = ResponseGenerator(self)
        self._self_correction_handler = SelfCorrectionHandler(self)
        self._workflow_handler = WorkflowHandler(self)

    def _get_orchestrator(self) -> Orchestrator:
        """Lazy init orchestrator with registry."""
        if self._orchestrator is None:
            registry = self._registry or get_default_registry()
            # Always ensure default agents are registered; the factory is idempotent.
            # Pass the shared skill executor so agents can actually run skills.
            create_default_agents(
                skill_executor=self._skill_executor,
                tool_registry=self._tool_registry,
            )
            phase_gate_evaluator = self._phase_gate_evaluator or PhaseGateEvaluator()
            replanning_engine = self._replanning_engine
            if replanning_engine is None:
                plan_engine = self.task_decomposer._get_plan_engine()
                replanning_engine = DynamicReplanningEngine(plan_engine=plan_engine)

            message_bus = self._message_bus or AgentMessageBus()
            supervisor = self._supervisor
            reviewer = self._reviewer
            if supervisor is None:
                from homomics_lab.models.common import AgentType

                supervisor = registry.get_agent(AgentType.SUPERVISOR)
            if reviewer is None:
                from homomics_lab.models.common import AgentType

                reviewer = registry.get_agent(AgentType.REVIEWER)

            # Wire the message bus into SWR agents so they can publish events.
            if supervisor is not None:
                supervisor.message_bus = message_bus
            if reviewer is not None:
                reviewer.message_bus = message_bus

            self._orchestrator = Orchestrator(
                registry=registry,
                progress_callback=self._progress_callback,
                workspace_manager=self._workspace_manager,
                phase_gate_evaluator=phase_gate_evaluator,
                replanning_engine=replanning_engine,
                supervisor=supervisor,
                reviewer=reviewer,
                message_bus=message_bus,
                cbkb=self._cbkb,
                skill_registry=(
                    self._skill_executor.registry
                    if self._skill_executor is not None
                    else None
                ),
            )
        return self._orchestrator

    def _get_self_correction_engine(self) -> SelfCorrectionEngine:
        """Lazy initialize the self-correction engine."""
        if self._self_correction_engine is None:
            replanning_engine = self._replanning_engine
            if replanning_engine is None:
                plan_engine = self.task_decomposer._get_plan_engine()
                replanning_engine = DynamicReplanningEngine(plan_engine=plan_engine)
            self._self_correction_engine = SelfCorrectionEngine(
                replanning_engine=replanning_engine
            )
        return self._self_correction_engine

    def _get_general_agent(self) -> GeneralScientificAgent:
        """Lazy initialize the general scientific agent."""
        if self._general_agent is None:
            if self._llm_client is None:
                self._llm_client = LLMClient()
            self._general_agent = GeneralScientificAgent(
                llm_client=self._llm_client,
                tool_registry=self._tool_registry,
                skill_registry=getattr(self, "registry", None),
                prompter=self.prompter,
            )
        return self._general_agent

    def _get_open_agent_executor(self) -> OpenAgentExecutor:
        """Lazy initialize the open agent executor."""
        if self._open_agent_executor is None:
            if self._llm_client is None:
                self._llm_client = LLMClient()
            self._open_agent_executor = OpenAgentExecutor(
                llm_client=self._llm_client,
                tool_registry=self._tool_registry,
                trace_store=self._trace_store,
            )
        return self._open_agent_executor

    def _get_workflow_execution_service(self) -> Optional[WorkflowExecutionService]:
        """Lazy init the workflow execution service."""
        if self._workflow_execution_service is None:
            cbkb = getattr(self, "_cbkb", None)
            self._workflow_execution_service = WorkflowExecutionService(
                skill_registry=getattr(self, "registry", None),
                tool_registry=self._tool_registry,
                llm_client=self._llm_client,
                progress_callback=self._progress_callback,
                cbkb=cbkb,
            )
        return self._workflow_execution_service

    async def execute_tree(
        self,
        tree: TaskTree,
        working_memory: WorkingMemory,
        project_id: str,
        trace_id: Optional[str] = None,
        session_id: str = "",
        plan_id: Optional[str] = None,
    ) -> TurnResult:
        """Execute a pre-built task tree.

        This is used by the background worker after a job has been enqueued.
        It skips intent analysis and decomposition. When ``plan_id`` is provided
        and the workflow execution service decides a Nextflow backend is
        appropriate, the whole plan is executed as a Nextflow workflow.
        """
        self._trace_id = trace_id

        plan: Optional[Plan] = None
        if plan_id is not None:
            plan = await PlanStore().get(plan_id)
            if plan is not None:
                tree = plan.task_tree

        if self._is_fallback_suggestion(tree):
            turn_result = self._build_fallback_result(tree, working_memory)
        elif len(tree.tasks) == 1:
            turn_result = await self._handle_single_step(
                tree, working_memory, project_id
            )
        else:
            turn_result = await self._handle_workflow(
                tree, working_memory, project_id, plan=plan
            )

        # Persist turn to long-term memory (best-effort)
        if self.memory_manager is not None:
            try:
                # Derive a user_message placeholder from the tree for memory summary
                user_message = (
                    tree.tasks[0].description if tree.tasks else "background execution"
                )
                await self.memory_manager.persist_turn(
                    session_id=session_id,
                    project_id=project_id,
                    user_message=user_message,
                    turn_result=turn_result,
                    working_memory=working_memory,
                    task_tree=turn_result.task_tree,
                )
            except Exception:
                import logging

                logging.getLogger(__name__).warning(
                    "Failed to persist background execution to memory", exc_info=True
                )

        return turn_result

    async def run_turn(
        self,
        session_id: str,
        user_message: str,
        working_memory: WorkingMemory,
        project_id: str,
        task_tree: Optional[TaskTree] = None,
        job_service=None,
        enqueue_skills: bool = False,
        plan_store: Optional[PlanStore] = None,
        debate_response: Optional[Dict[str, Any]] = None,
        plan_mode: bool = False,
        trace_id: Optional[str] = None,
        event_callback: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
    ) -> TurnResult:
        """Execute one full turn: from user message to agent response.

        This is the unified entry point. All conversational flows go through here.

        Args:
            job_service: Optional JobService for background execution.
            enqueue_skills: If True, skill-executing turns are enqueued instead of
                awaited synchronously.
            plan_mode: If True, always present an execution plan for approval before
                running non-domain tasks.
        """
        # Track turn context for cost attribution and tracing.
        self._session_id = session_id
        self._project_id = project_id
        self._trace_id = trace_id
        self._turn_request_id = f"turn_{session_id}_{int(time.time() * 1000)}"
        self._event_callback = event_callback

        # 1. Record user message
        user_msg = ChatMessage(
            id=f"msg_{len(working_memory.messages)}",
            type=MessageType.TEXT,
            content=user_message,
            sender="user",
        )
        working_memory.add_message(user_msg)

        return await self._run_turn_with_state(
            session_id=session_id,
            user_message=user_message,
            working_memory=working_memory,
            project_id=project_id,
            task_tree=task_tree,
            job_service=job_service,
            enqueue_skills=enqueue_skills,
            plan_store=plan_store,
            debate_response=debate_response,
            plan_mode=plan_mode,
            trace_id=trace_id,
        )

    async def regenerate_response(
        self,
        session_id: str,
        working_memory: WorkingMemory,
        project_id: str,
        task_tree: Optional[TaskTree] = None,
        job_service=None,
        enqueue_skills: bool = False,
        plan_store: Optional[PlanStore] = None,
        plan_mode: bool = False,
    ) -> TurnResult:
        """Regenerate the last assistant response without adding a new user message.

        Finds the most recent user message, removes any assistant messages that
        followed it, and re-runs the turn so the caller gets a fresh response.
        """
        recent = list(working_memory.messages)
        last_user_index = None
        for i in range(len(recent) - 1, -1, -1):
            if recent[i].sender == "user":
                last_user_index = i
                break

        if last_user_index is None:
            return self._build_error_result(
                ExecutionError("No user message found to regenerate from"),
                working_memory,
            )

        user_message = str(recent[last_user_index].content)

        # Drop all messages after the last user message (assistant replies,
        # tool results, etc.) so the turn can be replayed cleanly.
        while len(working_memory.messages) > last_user_index + 1:
            working_memory.messages.pop()

        return await self._run_turn_with_state(
            session_id=session_id,
            user_message=user_message,
            working_memory=working_memory,
            project_id=project_id,
            task_tree=task_tree,
            job_service=job_service,
            enqueue_skills=enqueue_skills,
            plan_store=plan_store,
            plan_mode=plan_mode,
        )

    async def _run_turn_with_state(
        self,
        session_id: str,
        user_message: str,
        working_memory: WorkingMemory,
        project_id: str,
        task_tree: Optional[TaskTree] = None,
        job_service=None,
        enqueue_skills: bool = False,
        plan_store: Optional[PlanStore] = None,
        debate_response: Optional[Dict[str, Any]] = None,
        plan_mode: bool = False,
        trace_id: Optional[str] = None,
    ) -> TurnResult:
        """Run the turn pipeline once and persist state."""
        turn_result: Optional[TurnResult] = None
        workspace_token = None
        if project_id:
            workspace = WorkspaceManager(settings.data_dir, project_id)
            workspace_token = current_workspace.set(workspace)
        try:
            turn_result = await self._run_turn_once(
                session_id=session_id,
                user_message=user_message,
                working_memory=working_memory,
                project_id=project_id,
                task_tree=task_tree,
                job_service=job_service,
                enqueue_skills=enqueue_skills,
                plan_store=plan_store,
                debate_response=debate_response,
                plan_mode=plan_mode,
            )
        except TurnError as exc:
            if exc.retryable:
                max_retries = 2
                for attempt in range(max_retries):
                    backoff = (2**attempt) * 0.5 + random.uniform(0, 0.25)
                    logger.warning(
                        "Retryable turn error, retrying in %.2fs: %s",
                        backoff,
                        exc,
                    )
                    await asyncio.sleep(backoff)
                    try:
                        turn_result = await self._run_turn_once(
                            session_id=session_id,
                            user_message=user_message,
                            working_memory=working_memory,
                            project_id=project_id,
                            task_tree=task_tree,
                            job_service=job_service,
                            enqueue_skills=enqueue_skills,
                            plan_store=plan_store,
                            debate_response=debate_response,
                            plan_mode=plan_mode,
                        )
                        break
                    except TurnError as exc2:
                        exc = exc2
                        if not exc2.retryable or attempt == max_retries - 1:
                            turn_result = self._build_error_result(exc2, working_memory)
                            break
                else:
                    turn_result = self._build_error_result(exc, working_memory)
            else:
                turn_result = self._build_error_result(exc, working_memory)
        except Exception as exc:
            # Wrap unexpected errors as ExecutionError for structured reporting.
            turn_result = self._build_error_result(
                ExecutionError(
                    str(exc), context={"exception_type": type(exc).__name__}
                ),
                working_memory,
            )
        finally:
            if workspace_token is not None:
                current_workspace.reset(workspace_token)

        # 5. Persist turn to long-term memory (best-effort)
        if self.memory_manager is not None and turn_result is not None:
            try:
                await self.memory_manager.persist_turn(
                    session_id=session_id,
                    project_id=project_id,
                    user_message=user_message,
                    turn_result=turn_result,
                    working_memory=working_memory,
                    task_tree=turn_result.task_tree,
                )
            except Exception:
                import logging

                logging.getLogger(__name__).warning(
                    "Failed to persist turn to memory", exc_info=True
                )

        # 6. Update structured project state (best-effort)
        if self.project_state_manager is not None and turn_result is not None:
            try:
                project_state = self.project_state_manager.load(project_id)
                project_state = self.project_state_manager.update_from_turn(
                    project_state,
                    task_tree=getattr(turn_result, "task_tree", None),
                    turn_result=turn_result,
                )
                self.project_state_manager.save(project_state)
            except Exception:
                import logging

                logging.getLogger(__name__).warning(
                    "Failed to update project state", exc_info=True
                )

        turn_result = turn_result or self._build_error_result(
            ExecutionError("Turn produced no result"), working_memory
        )

        # Record a lightweight summary node in the execution trace.
        if self._trace_store is not None and trace_id is not None:
            try:
                await self._trace_store.add_node(
                    trace_id=trace_id,
                    node_type="turn",
                    name="chat_turn",
                    metadata={
                        "mode": str(
                            turn_result.mode.value
                            if hasattr(turn_result.mode, "value")
                            else turn_result.mode
                        ),
                        "response_length": len(turn_result.response_text or ""),
                        "has_error": turn_result.error is not None,
                        "job_id": turn_result.job_id,
                        "plan_id": turn_result.plan_id,
                    },
                )
                await self._trace_store.update_node(
                    trace_id=trace_id,
                    node_id="root",
                    status="completed" if not turn_result.error else "failed",
                    outputs={
                        "response_preview": (turn_result.response_text or "")[:200]
                    },
                )
            except Exception:
                logger.warning("Failed to record turn trace node", exc_info=True)

        return turn_result

    async def _run_turn_once(
        self,
        session_id: str,
        user_message: str,
        working_memory: WorkingMemory,
        project_id: str,
        task_tree: Optional[TaskTree] = None,
        job_service=None,
        enqueue_skills: bool = False,
        plan_store: Optional[PlanStore] = None,
        debate_response: Optional[Dict[str, Any]] = None,
        plan_mode: bool = False,
    ) -> TurnResult:
        """Execute the core turn pipeline once."""
        # 2. Build a token-safe context bundle from the ContextEngine.
        extra_context = None
        if self.memory_manager is not None:
            try:
                extra_context = await self.memory_manager.enrich_context(
                    project_id, user_message, working_memory
                )
            except Exception:
                import logging

                logging.getLogger(__name__).warning(
                    "Memory enrichment failed; continuing without it", exc_info=True
                )
        self._extra_context = extra_context or {}

        # 2.5 Enrich context with semantically relevant capabilities (skills/tools/SOPs).
        if self.capability_index is not None:
            try:
                capability_candidates = await self.capability_index.search(
                    query=user_message,
                    top_k=5,
                    item_types=[
                        CapabilityType.SKILL,
                        CapabilityType.TOOL,
                        CapabilityType.SOP,
                    ],
                    project_id=project_id,
                )
                self._extra_context["capability_candidates"] = [
                    {
                        "id": c.id,
                        "type": c.type.value,
                        "name": c.name,
                        "description": c.description,
                        "category": c.category,
                        "score": c.score,
                    }
                    for c in capability_candidates
                ]
            except Exception:
                logger.warning(
                    "Capability index enrichment failed; continuing without it",
                    exc_info=True,
                )

        context_bundle = None
        if self.context_engine is not None:
            try:
                context_bundle = await self.context_engine.build(
                    user_message=user_message,
                    working_memory=working_memory,
                    project_id=project_id,
                    intent=None,
                    reserved_output_tokens=2000,
                )
            except Exception:
                import logging

                logging.getLogger(__name__).warning(
                    "ContextEngine build failed; falling back to raw working memory",
                    exc_info=True,
                )
        self._context_bundle = context_bundle

        # 3. Analyze intent with conversation context
        if debate_response is not None:
            intent = self._build_debate_resolved_intent(debate_response, user_message)
        else:
            try:
                intent = await self.intent_analyzer.analyze(
                    user_message,
                    working_memory=working_memory,
                    extra_context=extra_context,
                    context_bundle=context_bundle,
                )
            except Exception as exc:
                raise IntentError(
                    f"Intent analysis failed: {exc}",
                    context={"original_error": str(exc)},
                ) from exc

        # 3.5 Route based on structured intent (backward compatible).
        try:
            turn_result = await self._route_by_intent(
                intent=intent,
                user_message=user_message,
                working_memory=working_memory,
                project_id=project_id,
                session_id=session_id,
                plan_store=plan_store,
                job_service=job_service,
                enqueue_skills=enqueue_skills,
                plan_mode=plan_mode,
            )
        except TurnError:
            raise
        except Exception as exc:
            raise ExecutionError(
                f"Execution routing failed: {exc}",
                context={"original_error": str(exc)},
            ) from exc

        return turn_result

    async def _handle_direct_response(
        self,
        intent: UserIntent,
        user_message: str,
        working_memory: WorkingMemory,
        project_id: Optional[str] = None,
    ) -> TurnResult:
        """Handle questions and general help requests that need no skill execution.

        Delegates to the general scientific agent, which can answer directly,
        generate code, or call lightweight tools without assembling a rigid
        domain workflow.
        """
        context = {"project_id": project_id, "project_path": None}
        if project_id:
            from homomics_lab.config import settings

            context["project_path"] = str(settings.data_dir / "workspaces" / project_id)

        result = await self._get_general_agent().answer(
            intent=intent,
            working_memory=working_memory,
            context=context,
        )

        # Ensure we never return a completely empty assistant text bubble.
        if not result.response_text or not str(result.response_text).strip():
            result.response_text = (
                "我暂时无法生成回答，请稍后再试，或换一种方式描述您的问题。"
            )
            if result.agent_message is not None:
                result.agent_message.content = result.response_text

        return result

    async def _handle_mcp_tool(
        self,
        tool_name: str,
        tool_inputs: Dict[str, Any],
        working_memory: WorkingMemory,
    ) -> TurnResult:
        """Directly invoke an MCP tool and return its result."""

        result = await self._tool_registry.invoke_async(tool_name, tool_inputs)

        if result.success:
            content = result.output
            response_text = self._summarize_mcp_result(tool_name, content, tool_inputs)
        else:
            content = {"error": result.error_message}
            response_text = f"调用工具 {tool_name} 失败：{result.error_message}"

        agent_msg = ChatMessage(
            id=f"msg_{len(working_memory.messages)}",
            type=MessageType.RESULT_PREVIEW,
            content={
                "tool_name": tool_name,
                "inputs": tool_inputs,
                "result": content,
                "response_text": response_text,
            },
            sender="agent",
        )
        working_memory.add_message(agent_msg)

        return TurnResult(
            mode=ExecutionMode.DIRECT_RESPONSE,
            response_text=response_text,
            agent_message=agent_msg,
        )

    async def _handle_agent_loop(
        self,
        user_message: str,
        working_memory: WorkingMemory,
        allowed_tools: Optional[List[str]] = None,
        intent: Optional[UserIntent] = None,
    ) -> TurnResult:
        """Run the LLM-driven tool-calling loop for MCP tool intents."""
        if self._llm_client is None or self._tool_registry is None:
            raise RuntimeError("AgentLoop requires both llm_client and tool_registry")

        history = self._working_memory_to_history(working_memory)
        loop = AgentLoop(
            llm_client=self._llm_client,
            tool_registry=self._tool_registry,
            session_id=getattr(self, "_session_id", None),
            project_id=getattr(self, "_project_id", None),
            request_id=getattr(self, "_turn_request_id", None),
            max_rounds=3,
            budget=TurnBudget(max_llm_calls=5, max_tool_calls=10),
            event_callback=getattr(self, "_event_callback", None),
        )
        result = await loop.run(
            user_message=user_message,
            history=history,
            allowed_tools=allowed_tools,
        )

        if result.awaiting_approval and result.approval_request:
            tool_name = result.approval_request.get("tool_name", "")
            risk_level = result.approval_request.get("risk_level", "high")
            if self._permission_registry.can_auto_approve_tool(
                role_id=None,
                domain=intent.domain if intent else None,
                tool_name=tool_name,
                risk_level=risk_level,
            ):
                return await self.respond_to_tool_approval(
                    call_id=result.approval_request["call_id"],
                    approved=True,
                    working_memory=working_memory,
                    project_id=getattr(self, "_project_id", "default"),
                )
            return await self._create_tool_approval_hitl(
                result, working_memory, user_message
            )

        response_text = result.response_text
        if not response_text or not str(response_text).strip():
            response_text = "工具调用已完成，但没有生成可读的回复。"

        agent_msg = ChatMessage(
            id=f"msg_{len(working_memory.messages)}",
            type=MessageType.TEXT,
            content=response_text,
            sender="agent",
        )
        working_memory.add_message(agent_msg)

        # Preserve a structured preview if any tool calls were made.
        if result.tool_calls:
            preview_msg = ChatMessage(
                id=f"msg_{len(working_memory.messages)}",
                type=MessageType.RESULT_PREVIEW,
                content={
                    "tool_calls": [
                        {
                            "tool_name": tc.tool_name,
                            "inputs": tc.inputs,
                            "success": tc.success,
                            "output_summary": tc.output_summary,
                        }
                        for tc in result.tool_calls
                    ],
                    "response_text": response_text,
                },
                sender="agent",
            )
            working_memory.add_message(preview_msg)

        # Suggest follow-up questions for direct text/tool answers.
        suggestions = await self._generate_followup_suggestions(
            user_message=user_message,
            response_text=response_text,
        )
        if suggestions:
            follow_up_msg = ChatMessage(
                id=f"msg_{len(working_memory.messages)}",
                type=MessageType.FOLLOW_UP,
                content={"suggestions": suggestions},
                sender="agent",
            )
            working_memory.add_message(follow_up_msg)

        return TurnResult(
            mode=ExecutionMode.DIRECT_RESPONSE,
            response_text=response_text,
            agent_message=agent_msg,
        )

    async def _generate_followup_suggestions(
        self,
        user_message: str,
        response_text: str,
        max_suggestions: int = 3,
    ) -> List[str]:
        """Generate concise follow-up question suggestions using the LLM."""
        if (
            self._llm_client is None
            or not getattr(self._llm_client, "is_configured", lambda: False)()
        ):
            return []

        prompt = (
            f"User question: {user_message}\n"
            f"Agent answer: {response_text}\n\n"
            f"Generate up to {max_suggestions} concise follow-up questions the user might ask next. "
            "Respond with a JSON array of strings only, no markdown."
        )
        try:
            raw = await self._llm_client.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that suggests follow-up questions.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=200,
                response_format={"type": "json_object"},
            )
            parsed = json.loads(raw)
            suggestions = (
                parsed.get("suggestions", parsed)
                if isinstance(parsed, dict)
                else parsed
            )
            if isinstance(suggestions, list):
                return [str(s) for s in suggestions[:max_suggestions]]
        except Exception:
            logger.debug("Follow-up suggestion generation failed", exc_info=True)
        return []

    async def _create_tool_approval_hitl(
        self,
        loop_result: Any,
        working_memory: WorkingMemory,
        user_message: str,
    ) -> "TurnResult":
        """Create a HITL request when the agent loop pauses for tool approval."""
        req = loop_result.approval_request
        call_id = req["call_id"]
        tool_name = req["tool_name"]
        arguments = req["arguments"]

        checkpoint = HITLCheckpoint(
            id=f"tool_approval_{call_id}",
            trigger_reason=HITLTrigger.HIGH_RISK,
            context_summary=(
                f"Agent wants to run high-risk tool `{tool_name}` "
                f"with arguments {arguments}. Please approve or decline."
            ),
            options=[
                Option(
                    id="approve", label="授权执行", description="允许执行该高风险工具"
                ),
                Option(id="decline", label="拒绝", description="跳过该工具调用"),
            ],
            metadata={
                "tool_approval_call_id": call_id,
                "tool_name": tool_name,
                "arguments": arguments,
            },
        )

        hitl_msg = ChatMessage(
            id=f"msg_{len(working_memory.messages)}",
            type=MessageType.HITL_REQUEST,
            content={
                "checkpoint": checkpoint.model_dump(),
                "task_id": call_id,
            },
            sender="agent",
        )
        working_memory.add_message(hitl_msg)

        return TurnResult(
            mode=ExecutionMode.AWAITING_HITL,
            response_text=loop_result.response_text,
            agent_message=hitl_msg,
            hitl_task_id=call_id,
            hitl_checkpoint=checkpoint.model_dump(),
        )

    async def respond_to_tool_approval(
        self,
        call_id: str,
        approved: bool,
        working_memory: WorkingMemory,
        project_id: str,
    ) -> "TurnResult":
        """Resume an agent loop after a high-risk tool approval decision."""
        from homomics_lab.tools.approval_store import PersistentApprovalStore
        from homomics_lab.agent.agent_loop import AgentLoop

        store = self._approval_store or PersistentApprovalStore()
        request = store.get(call_id)
        if request is None:
            text = f"找不到工具授权请求 `{call_id}`，请重新发起查询。"
            msg = ChatMessage(
                id=f"msg_{len(working_memory.messages)}",
                type=MessageType.TEXT,
                content=text,
                sender="agent",
            )
            working_memory.add_message(msg)
            return TurnResult(
                mode=ExecutionMode.DIRECT_RESPONSE,
                response_text=text,
                agent_message=msg,
            )

        if not approved:
            text = f"已拒绝执行高风险工具 `{request.tool_name}`。"
            msg = ChatMessage(
                id=f"msg_{len(working_memory.messages)}",
                type=MessageType.TEXT,
                content=text,
                sender="agent",
            )
            working_memory.add_message(msg)
            request.approved = False
            store.reject(call_id, resolver="user", reason="declined")
            return TurnResult(
                mode=ExecutionMode.DIRECT_RESPONSE,
                response_text=text,
                agent_message=msg,
            )

        # Mark approved and execute the tool directly.
        request.approved = True
        store.approve(call_id, resolver="user", reason="approved")

        metadata = request.metadata or {}
        messages = list(metadata.get("messages", []))
        tool_records = [ToolCallRecord(**r) for r in metadata.get("tool_records", [])]
        pending = metadata.get("pending_tool_call", {})
        tool_name = pending.get("name", request.tool_name)
        tool_inputs = pending.get("inputs", request.arguments)
        tool_call_id = pending.get("id", call_id)

        if self._tool_registry is None:
            text = "Tool registry unavailable, cannot resume tool execution."
            msg = ChatMessage(
                id=f"msg_{len(working_memory.messages)}",
                type=MessageType.TEXT,
                content=text,
                sender="agent",
            )
            working_memory.add_message(msg)
            return TurnResult(
                mode=ExecutionMode.DIRECT_RESPONSE,
                response_text=text,
                agent_message=msg,
            )

        try:
            tool_result = await self._tool_registry.invoke_async(tool_name, tool_inputs)
            summary = AgentLoop(
                llm_client=self._llm_client,
                tool_registry=self._tool_registry,
            )._summarize_tool_output(tool_name, tool_result.output)
        except Exception as exc:
            summary = f"调用工具 `{tool_name}` 失败：{exc}"
            tool_result = None

        record = ToolCallRecord(
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            inputs=tool_inputs,
            success=tool_result is not None and getattr(tool_result, "success", False),
            output_summary=summary,
        )
        tool_records.append(record)

        messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": summary,
            }
        )

        # Ask the LLM to summarize the result for the user.
        final_text = summary
        if (
            self._llm_client is not None
            and getattr(self._llm_client, "is_configured", lambda: False)()
        ):
            try:
                final_msg, _ = await self._llm_client.chat_completion_message(
                    messages=messages,
                    temperature=0.3,
                    max_tokens=2000,
                    session_id=self._session_id,
                    project_id=self._project_id,
                    request_id=f"{self._turn_request_id or 'agent'}_approval_resume",
                )
                final_text = (
                    getattr(final_msg, "content", None) or ""
                ).strip() or summary
            except Exception as exc:
                logger.warning("Tool approval final summarization failed: %s", exc)
                final_text = summary

        if not final_text or not str(final_text).strip():
            final_text = "工具调用已完成。"

        agent_msg = ChatMessage(
            id=f"msg_{len(working_memory.messages)}",
            type=MessageType.TEXT,
            content=final_text,
            sender="agent",
        )
        working_memory.add_message(agent_msg)

        preview_msg = ChatMessage(
            id=f"msg_{len(working_memory.messages)}",
            type=MessageType.RESULT_PREVIEW,
            content={
                "tool_calls": [
                    {
                        "tool_name": tc.tool_name,
                        "inputs": tc.inputs,
                        "success": tc.success,
                        "output_summary": tc.output_summary,
                    }
                    for tc in tool_records
                ],
                "response_text": final_text,
            },
            sender="agent",
        )
        working_memory.add_message(preview_msg)

        return TurnResult(
            mode=ExecutionMode.DIRECT_RESPONSE,
            response_text=final_text,
            agent_message=agent_msg,
        )

    async def _evaluate_risk(
        self,
        intent: UserIntent,
        user_message: str,
        working_memory: WorkingMemory,
        project_id: Optional[str] = None,
    ) -> float:
        """Evaluate plan/data-destruction risk for the current turn.

        Uses the configured LLM client when available, otherwise falls back to
        a simple keyword heuristic.
        """
        low_risk_keywords = {
            "analysis",
            "plot",
            "qc",
            "visualize",
            "统计",
            "画图",
            "质控",
        }
        high_risk_keywords = {
            "delete",
            "drop",
            "overwrite",
            "remove",
            "清空",
            "删除",
            "覆盖",
            "替换",
        }

        if self._llm_client is None:
            return self._heuristic_risk_score(
                user_message, intent, low_risk_keywords, high_risk_keywords
            )

        try:
            prompt = self._build_risk_prompt(
                intent, user_message, working_memory, project_id
            )
            response = await self._llm_client.chat_completion(
                prompt,
                session_id=getattr(self, "_session_id", None),
                project_id=getattr(self, "_project_id", None),
                request_id=f"{getattr(self, '_turn_request_id', 'risk')}_risk",
            )
            return self._parse_risk_score(response)
        except Exception:
            import logging

            logging.getLogger(__name__).warning(
                "LLM risk evaluation failed; falling back to heuristic", exc_info=True
            )
            return self._heuristic_risk_score(
                user_message, intent, low_risk_keywords, high_risk_keywords
            )

    async def _build_orchestrator_context(
        self,
        project_id: str,
        intent: Optional[UserIntent] = None,
        user_message: Optional[str] = None,
        working_memory: Optional[WorkingMemory] = None,
    ) -> Dict[str, Any]:
        """Build the context dict passed to the orchestrator and HITL detector."""
        context: Dict[str, Any] = {"project_id": project_id}
        if getattr(self, "_trace_id", None):
            context["trace_id"] = self._trace_id

        confidence = getattr(intent, "confidence", 1.0) if intent is not None else 1.0
        context["confidence"] = confidence
        context["confidence_threshold"] = settings.hitl_confidence_threshold

        risk_threshold = settings.hitl_risk_threshold
        context["risk_threshold"] = risk_threshold

        if (
            intent is not None
            and user_message is not None
            and working_memory is not None
        ):
            context["risk_score"] = await self._evaluate_risk(
                intent, user_message, working_memory, project_id
            )
        else:
            context["risk_score"] = 0.0

        return context

    async def _record_execution_feedback(
        self,
        tree: TaskTree,
        results: Dict[str, Any],
        project_id: str,
    ) -> None:
        """Record skill execution feedback into CapabilityIndex, MemoryBackend and SkillDAG.

        This is best-effort: failures are logged but never break the turn.
        """
        if (
            self.capability_index is None
            and self.memory_backend is None
            and self.skill_dag is None
        ):
            return

        for task in tree.tasks:
            if not task.skills_required:
                continue
            skill_id = task.skills_required[0]
            if not skill_id:
                continue

            outcome = (
                FeedbackOutcome.SUCCESS
                if task.status == TaskStatus.COMPLETED
                else FeedbackOutcome.FAILURE
            )

            if self.capability_index is not None:
                try:
                    await self.capability_index.add_feedback(
                        capability_id=skill_id,
                        capability_type=CapabilityType.SKILL,
                        outcome=outcome,
                        project_id=project_id,
                        context={
                            "task_id": task.id,
                            "phase": task.phase,
                            "result_keys": list(results.get(task.id, {}).keys())
                            if isinstance(results.get(task.id), dict)
                            else [],
                        },
                    )
                except Exception:
                    logger.warning(
                        "Failed to record capability feedback for %s",
                        skill_id,
                        exc_info=True,
                    )

            if self.memory_backend is not None:
                try:
                    await self.memory_backend.add(
                        text=(
                            f"Executed skill '{skill_id}' for task '{task.name}' "
                            f"with outcome {outcome.value}."
                        ),
                        memory_type="task",
                        metadata={
                            "skill_id": skill_id,
                            "task_id": task.id,
                            "phase": task.phase,
                            "outcome": outcome.value,
                        },
                        importance=0.7 if outcome == FeedbackOutcome.SUCCESS else 0.9,
                        project_id=project_id,
                    )
                except Exception:
                    logger.warning(
                        "Failed to record task memory for %s", skill_id, exc_info=True
                    )

        if self.skill_dag is not None:
            # Record adjacent skill transitions so the SkillDAG evolves from
            # real executions instead of only offline mining.
            try:
                from homomics_lab.skills.skill_dag import EdgeType

                prev_skill: Optional[str] = None
                prev_ok = True
                for task in tree.tasks:
                    if not task.skills_required:
                        continue
                    skill_id = task.skills_required[0]
                    if not skill_id:
                        continue
                    ok = task.status == TaskStatus.COMPLETED
                    if prev_skill is not None and prev_skill != skill_id:
                        self.skill_dag.record_observation(
                            prev_skill,
                            skill_id,
                            EdgeType.FOLLOWED_BY,
                            prev_ok and ok,
                            context=f"Turn execution in project {project_id}",
                        )
                    prev_skill = skill_id
                    prev_ok = ok
            except Exception:
                logger.warning(
                    "Failed to record SkillDAG observations", exc_info=True
                )

    async def _handle_single_step(
        self,
        tree: TaskTree,
        working_memory: WorkingMemory,
        project_id: str,
        intent: Optional[UserIntent] = None,
        user_message: Optional[str] = None,
    ) -> TurnResult:
        """Handle single-step tasks (e.g., file conversion)."""
        # Handle non-executable fallback suggestions directly.
        if self._is_fallback_suggestion(tree):
            return self._build_fallback_result(tree, working_memory)

        orchestrator = self._get_orchestrator()
        self._attach_uploaded_files_to_tree(tree, user_message, project_id)
        context = await self._build_orchestrator_context(
            project_id,
            intent=intent,
            user_message=user_message,
            working_memory=working_memory,
        )
        try:
            results = await orchestrator.run_tree(tree, context=context)
        except ExecutionError as exc:
            corrected = await self._apply_self_correction(
                tree,
                working_memory,
                project_id,
                exc,
                intent=intent,
                user_message=user_message,
            )
            if corrected is not None:
                return corrected
            raise

        # Check for HITL
        hitl_info = self._extract_hitl(results)
        if hitl_info:
            return self._build_hitl_result(tree, hitl_info, working_memory)

        await self._record_execution_feedback(tree, results, project_id)

        response_text = f"已完成：{tree.tasks[0].description}"

        # Extract any plots produced by the skill
        plot_messages = self._extract_plot_messages(results, tree, working_memory)
        for msg in plot_messages:
            working_memory.add_message(msg)

        agent_msg = ChatMessage(
            id=f"msg_{len(working_memory.messages)}",
            type=MessageType.TODO_LIST,
            content={
                "text": response_text,
                "tasks": [t.model_dump() for t in tree.tasks],
                "progress": orchestrator.get_progress(tree),
                "project_id": project_id,
            },
            sender="agent",
        )
        working_memory.add_message(agent_msg)

        return TurnResult(
            mode=ExecutionMode.SINGLE_STEP,
            response_text=response_text,
            task_tree=tree,
            progress=orchestrator.get_progress(tree),
            agent_message=agent_msg,
            attachments=plot_messages,
        )

    @staticmethod
    def _single_skill_id(tree: TaskTree) -> Optional[str]:
        ids = [t.skills_required[0] for t in tree.tasks if t.skills_required]
        return ids[0] if len(ids) == 1 else None

    async def resume_hitl(
        self,
        session_id: str,
        task_id: str,
        choice: str,
        parameters: Dict[str, Any],
        working_memory: WorkingMemory,
        task_tree: TaskTree,
        project_id: str = "default",
    ) -> TurnResult:
        """Resume execution after receiving HITL response."""
        orchestrator = self._get_orchestrator()

        result = await orchestrator.resume_task(
            task_tree,
            task_id,
            {"choice": choice, "parameters": parameters},
        )

        await self._record_execution_feedback(task_tree, result, project_id)

        response_text = f"已恢复任务 {task_id}，继续执行后续步骤。"

        # Extract any plots produced after resuming
        plot_messages = self._extract_plot_messages(result, task_tree, working_memory)
        for msg in plot_messages:
            working_memory.add_message(msg)

        agent_msg = ChatMessage(
            id=f"msg_{len(working_memory.messages)}",
            type=MessageType.TODO_LIST,
            content={
                "text": response_text,
                "tasks": [t.model_dump() for t in task_tree.tasks],
                "progress": orchestrator.get_progress(task_tree),
            },
            sender="agent",
        )
        working_memory.add_message(agent_msg)

        return TurnResult(
            mode=ExecutionMode.RESUME_HITL,
            response_text=response_text,
            task_tree=task_tree,
            progress=orchestrator.get_progress(task_tree),
            agent_message=agent_msg,
            attachments=plot_messages,
        )

    def _is_fallback_suggestion(self, tree: TaskTree) -> bool:
        """Check if the tree is a non-executable LLM fallback suggestion."""
        return (
            len(tree.tasks) == 1
            and tree.tasks[0].phase == "suggestion"
            and not tree.tasks[0].skills_required
        )

    def _extract_plot_messages(
        self,
        results: Dict[str, Any],
        tree: TaskTree,
        working_memory: WorkingMemory,
    ) -> List[ChatMessage]:
        """Scan execution results for plot outputs and build chat messages."""
        messages: List[ChatMessage] = []
        task_lookup = {t.id: t for t in tree.tasks}
        base_id = len(working_memory.messages)

        for task_id, result in results.items():
            if not isinstance(result, dict):
                continue

            skill_output = result.get("result", {})
            if not isinstance(skill_output, dict):
                continue

            task = task_lookup.get(task_id)
            skill_id = result.get("skill") or (
                task.skills_required[0] if task and task.skills_required else None
            )

            plot_type = skill_output.get("plot_type") or (
                task.name if task else "visualization"
            )
            attachments = extract_plot_attachments(
                skill_output,
                default_plot_type=plot_type,
                default_title=f"{plot_type} visualization",
            )

            for attachment in attachments:
                msg = ChatMessage(
                    id=f"msg_{base_id}",
                    type=MessageType.PLOT_DATA if attachment.data else MessageType.PLOT,
                    content=attachment.to_chat_content(),
                    sender="agent",
                    task_id=task_id,
                    skill_id=skill_id,
                )
                base_id += 1
                messages.append(msg)

        return messages

    # --- Delegated collaborators -------------------------------------------
    # Thin shells kept for backward compatibility: tests and internal callers
    # still invoke these private methods on TurnRunner, while the
    # implementations live in dedicated collaborator classes (pure code move,
    # no logic changes).

    def _working_memory_to_history(
        self, working_memory: WorkingMemory
    ) -> List[Dict[str, Any]]:
        return self._context_formatter.working_memory_to_history(working_memory)

    def _summarize_mcp_result(
        self,
        tool_name: str,
        output: Any,
        tool_inputs: Optional[Dict[str, Any]] = None,
    ) -> str:
        return self._context_formatter.summarize_mcp_result(
            tool_name, output, tool_inputs
        )

    def _format_pubmed_search(
        self,
        output: Dict[str, Any],
        tool_inputs: Optional[Dict[str, Any]] = None,
    ) -> str:
        return self._context_formatter.format_pubmed_search(output, tool_inputs)

    def _format_science_dbs(self, output: Dict[str, Any]) -> str:
        return self._context_formatter.format_science_dbs(output)

    def _format_science_search(
        self,
        output: Dict[str, Any],
        tool_inputs: Optional[Dict[str, Any]] = None,
    ) -> str:
        return self._context_formatter.format_science_search(output, tool_inputs)

    def _format_pubmed_fetch(
        self,
        output: Dict[str, Any],
        tool_inputs: Optional[Dict[str, Any]] = None,
    ) -> str:
        return self._context_formatter.format_pubmed_fetch(output, tool_inputs)

    def _format_extra_context(self) -> str:
        return self._context_formatter.format_extra_context()

    def _build_risk_prompt(
        self,
        intent: UserIntent,
        user_message: str,
        working_memory: WorkingMemory,
        project_id: Optional[str] = None,
    ) -> str:
        return self._risk_assessor.build_risk_prompt(
            intent, user_message, working_memory, project_id
        )

    def _parse_risk_score(self, response: Any) -> float:
        return self._risk_assessor.parse_risk_score(response)

    def _heuristic_risk_score(
        self,
        user_message: str,
        intent: UserIntent,
        low_risk_keywords: set,
        high_risk_keywords: set,
    ) -> float:
        return self._risk_assessor.heuristic_risk_score(
            user_message, intent, low_risk_keywords, high_risk_keywords
        )

    def _resolve_uploaded_file_references(
        self,
        user_message: Optional[str],
        project_id: str,
    ) -> List[Tuple[str, str]]:
        return self._file_resolver.resolve_uploaded_file_references(
            user_message, project_id
        )

    def _attach_uploaded_files_to_tree(
        self,
        tree: TaskTree,
        user_message: Optional[str],
        project_id: str,
    ) -> None:
        return self._file_resolver.attach_uploaded_files_to_tree(
            tree, user_message, project_id
        )

    def _envelopes_from_artifacts(
        self, artifacts: Optional[List[Any]]
    ) -> List[Dict[str, Any]]:
        return self._result_assembler.envelopes_from_artifacts(artifacts)

    def _envelopes_from_results(
        self, results: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        return self._result_assembler.envelopes_from_results(results)

    def _summarize(
        self,
        envelopes: List[Dict[str, Any]],
        user_message: str,
        skill_id: Optional[str],
    ) -> str:
        return self._result_assembler.summarize(envelopes, user_message, skill_id)

    def _build_workflow_result(
        self,
        tree: TaskTree,
        working_memory: WorkingMemory,
        backend: str,
        artifacts: Optional[List[Any]] = None,
        error: Optional[str] = None,
        user_message: str = "",
    ) -> TurnResult:
        return self._result_assembler.build_workflow_result(
            tree=tree,
            working_memory=working_memory,
            backend=backend,
            artifacts=artifacts,
            error=error,
            user_message=user_message,
        )

    def _build_fallback_result(
        self,
        tree: TaskTree,
        working_memory: WorkingMemory,
    ) -> TurnResult:
        return self._result_assembler.build_fallback_result(tree, working_memory)

    def _extract_hitl(self, results: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return self._result_assembler.extract_hitl(results)

    def _build_hitl_result(
        self,
        tree: TaskTree,
        hitl_info: Dict[str, Any],
        working_memory: WorkingMemory,
    ) -> TurnResult:
        return self._result_assembler.build_hitl_result(
            tree, hitl_info, working_memory
        )

    def _build_error_result(
        self, error: Union[str, TurnError], working_memory: WorkingMemory
    ) -> TurnResult:
        return self._result_assembler.build_error_result(error, working_memory)

    def _handle_clarification(
        self,
        intent: UserIntent,
        working_memory: WorkingMemory,
    ) -> TurnResult:
        return self._clarification_handler.handle_clarification(intent, working_memory)

    def _build_debate_resolved_intent(
        self,
        debate_response: Dict[str, Any],
        user_message: str,
    ) -> UserIntent:
        return self._clarification_handler.build_debate_resolved_intent(
            debate_response, user_message
        )

    def _compress_working_memory(
        self, working_memory: WorkingMemory, current_goal: str
    ) -> str:
        return self._context_formatter.compress_working_memory(
            working_memory, current_goal
        )

    async def _route_by_intent(
        self,
        intent: UserIntent,
        user_message: str,
        working_memory: WorkingMemory,
        project_id: str,
        session_id: str,
        plan_store: Optional[PlanStore],
        job_service: Optional[Any],
        enqueue_skills: bool,
        plan_mode: bool = False,
    ) -> TurnResult:
        return await self._intent_router.route(
            intent=intent,
            user_message=user_message,
            working_memory=working_memory,
            project_id=project_id,
            session_id=session_id,
            plan_store=plan_store,
            job_service=job_service,
            enqueue_skills=enqueue_skills,
            plan_mode=plan_mode,
        )

    async def _handle_workflow(
        self,
        tree: TaskTree,
        working_memory: WorkingMemory,
        project_id: str,
        intent: Optional[UserIntent] = None,
        user_message: Optional[str] = None,
        plan: Optional[Plan] = None,
    ) -> TurnResult:
        return await self._workflow_handler.handle(
            tree=tree,
            working_memory=working_memory,
            project_id=project_id,
            intent=intent,
            user_message=user_message,
            plan=plan,
        )

    async def _apply_self_correction(
        self,
        tree: TaskTree,
        working_memory: WorkingMemory,
        project_id: str,
        error: Exception,
        intent: Optional[UserIntent] = None,
        user_message: Optional[str] = None,
    ) -> Optional[TurnResult]:
        return await self._self_correction_handler.apply(
            tree=tree,
            working_memory=working_memory,
            project_id=project_id,
            error=error,
            intent=intent,
            user_message=user_message,
        )

    async def _generate_general_help_response(
        self, user_message: str, working_memory: WorkingMemory
    ) -> str:
        return await self._response_generator.generate_general_help_response(
            user_message, working_memory
        )

    async def _generate_direct_response_via_llm(
        self,
        response_type: str,
        user_message: str,
        intent: UserIntent,
        working_memory: WorkingMemory,
        project_id: Optional[str] = None,
        max_tokens: Optional[int] = None,
    ) -> Optional[str]:
        return await self._response_generator.generate_direct_response_via_llm(
            response_type=response_type,
            user_message=user_message,
            intent=intent,
            working_memory=working_memory,
            project_id=project_id,
            max_tokens=max_tokens,
        )

    async def _generate_greeting_response(
        self,
        user_message: str,
        working_memory: WorkingMemory,
        project_id: Optional[str] = None,
    ) -> str:
        return await self._response_generator.generate_greeting_response(
            user_message, working_memory, project_id
        )

    async def _generate_qa_response(
        self,
        intent: UserIntent,
        user_message: str,
        working_memory: WorkingMemory,
        project_id: Optional[str] = None,
    ) -> str:
        return await self._response_generator.generate_qa_response(
            intent, user_message, working_memory, project_id
        )

    async def _try_web_search_response(self, user_message: str) -> Optional[str]:
        return await self._response_generator.try_web_search_response(user_message)

    async def _generate_information_request_response(
        self,
        intent: UserIntent,
        working_memory: WorkingMemory,
        project_id: Optional[str] = None,
    ) -> str:
        return await self._response_generator.generate_information_request_response(
            intent, working_memory, project_id
        )
