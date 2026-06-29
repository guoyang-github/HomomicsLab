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
import re
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

from homomics_lab.agent.agent_registry import AgentRegistry, get_default_registry
from homomics_lab.agent.agent_loop import AgentLoop, TurnBudget
from homomics_lab.agent.debate import LightweightDebate
from homomics_lab.agent.errors import (
    ExecutionError,
    IntentError,
    TurnError,
)
from homomics_lab.agent.factory import create_default_agents
from homomics_lab.agent.intent_analyzer import IntentAnalyzer, UserIntent
from homomics_lab.agent.intent.models import IntentMatch
from homomics_lab.agent.message_bus import AgentMessageBus
from homomics_lab.agent.orchestrator import Orchestrator
from homomics_lab.agent.phase_gate import PhaseGateEvaluator
from homomics_lab.agent.plan.replanning import DynamicReplanningEngine
from homomics_lab.agent.task_decomposer import TaskDecomposer
from homomics_lab.config import settings
from homomics_lab.context.compressor import ContextCompressor
from homomics_lab.context.context_engine.engine import ContextEngine
from homomics_lab.context.context_engine.models import ContextBundle
from homomics_lab.context.memory_manager import MemoryManager
from homomics_lab.context.project_state import ProjectStateManager
from homomics_lab.context.prompter import Prompter
from homomics_lab.context.relevance_filter import ContextItem
from homomics_lab.context.working_memory import WorkingMemory
from homomics_lab.hpc.state import ExecutionState
from homomics_lab.jobs.constants import JobMode
from homomics_lab.llm_client import LLMClient
from homomics_lab.models.common import ChatMessage, MessageType
from homomics_lab.plan.models import Plan, PlanStatus
from homomics_lab.tools.registry import ToolRegistry
from homomics_lab.plan.presenter import PlanPresenter
from homomics_lab.plan.store import PlanStore, _new_plan_id
from homomics_lab.plots import extract_plot_attachments
from homomics_lab.tasks.task_tree import TaskTree


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
    ):
        self._cbkb = cbkb
        self._llm_client = llm_client
        self._trace_store = trace_store
        self._orchestrator = orchestrator
        self._registry = registry
        self._progress_callback = progress_callback
        self._workspace_manager = workspace_manager
        self._phase_gate_evaluator = phase_gate_evaluator
        self._replanning_engine = replanning_engine
        self._supervisor = supervisor
        self._reviewer = reviewer
        self._message_bus = message_bus
        self._tool_registry = tool_registry
        self.memory_manager = memory_manager
        self.prompter = prompter or Prompter()
        self.compressor = compressor or ContextCompressor(max_items=6, max_chars_per_item=1000)
        self.context_engine = context_engine
        self.project_state_manager = project_state_manager
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

        self.intent_analyzer = intent_analyzer or IntentAnalyzer(debate=self._debate, cbkb=self._cbkb)
        self.task_decomposer = task_decomposer or TaskDecomposer(cbkb=self._cbkb)

    def _get_orchestrator(self) -> Orchestrator:
        """Lazy init orchestrator with registry."""
        if self._orchestrator is None:
            registry = self._registry or get_default_registry()
            # Always ensure default agents are registered; the factory is idempotent.
            create_default_agents()
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
            )
        return self._orchestrator

    async def execute_tree(
        self,
        tree: TaskTree,
        working_memory: WorkingMemory,
        project_id: str,
        trace_id: Optional[str] = None,
        session_id: str = "",
    ) -> TurnResult:
        """Execute a pre-built task tree.

        This is used by the background worker after a job has been enqueued.
        It skips intent analysis and decomposition.
        """
        self._trace_id = trace_id

        if self._is_fallback_suggestion(tree):
            turn_result = self._build_fallback_result(tree, working_memory)
        elif len(tree.tasks) == 1:
            turn_result = await self._handle_single_step(tree, working_memory, project_id)
        else:
            turn_result = await self._handle_workflow(tree, working_memory, project_id)

        # Persist turn to long-term memory (best-effort)
        if self.memory_manager is not None:
            try:
                # Derive a user_message placeholder from the tree for memory summary
                user_message = tree.tasks[0].description if tree.tasks else "background execution"
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
                    backoff = (2 ** attempt) * 0.5 + random.uniform(0, 0.25)
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
                ExecutionError(str(exc), context={"exception_type": type(exc).__name__}),
                working_memory,
            )

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
                        "mode": str(turn_result.mode.value if hasattr(turn_result.mode, "value") else turn_result.mode),
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
                    outputs={"response_preview": (turn_result.response_text or "")[:200]},
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
                    "ContextEngine build failed; falling back to raw working memory", exc_info=True
                )
        self._context_bundle = context_bundle

        # 3. Analyze intent with conversation context
        if debate_response is not None:
            intent = self._build_debate_resolved_intent(
                debate_response, user_message
            )
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
        """Handle questions and general help requests that need no skill execution."""
        if intent.analysis_type == "greeting":
            response_text = await self._generate_greeting_response(
                user_message, working_memory, project_id
            )
        elif intent.analysis_type == "general_help":
            response_text = await self._generate_general_help_response(
                user_message, working_memory
            )
        elif intent.analysis_type == "information_request":
            response_text = await self._generate_information_request_response(
                intent, working_memory, project_id
            )
        else:
            response_text = await self._generate_qa_response(
                intent, user_message, working_memory, project_id
            )

        # Never store or return a completely empty assistant text bubble.
        if not response_text or not str(response_text).strip():
            response_text = (
                "我暂时无法生成回答，请稍后再试，或换一种方式描述您的问题。"
            )

        agent_msg = ChatMessage(
            id=f"msg_{len(working_memory.messages)}",
            type=MessageType.TEXT,
            content=response_text,
            sender="agent",
        )
        working_memory.add_message(agent_msg)

        return TurnResult(
            mode=ExecutionMode.DIRECT_RESPONSE,
            response_text=response_text,
            agent_message=agent_msg,
        )

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
        if self._llm_client is None or not getattr(self._llm_client, "is_configured", lambda: False)():
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
                    {"role": "system", "content": "You are a helpful assistant that suggests follow-up questions."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=200,
                response_format={"type": "json_object"},
            )
            parsed = json.loads(raw)
            suggestions = parsed.get("suggestions", parsed) if isinstance(parsed, dict) else parsed
            if isinstance(suggestions, list):
                return [str(s) for s in suggestions[:max_suggestions]]
        except Exception:
            logger.debug("Follow-up suggestion generation failed", exc_info=True)
        return []

    def _working_memory_to_history(
        self, working_memory: WorkingMemory
    ) -> List[Dict[str, Any]]:
        """Convert recent working-memory messages to OpenAI-compatible history."""
        history: List[Dict[str, Any]] = []
        for msg in working_memory.get_recent_messages()[-10:]:
            if msg.sender == "user":
                role = "user"
            elif msg.sender == "agent":
                role = "assistant"
            else:
                continue
            content = msg.content
            if isinstance(content, dict):
                content = content.get("response_text") or content.get("text") or str(content)
            if not isinstance(content, str):
                content = str(content)
            history.append({"role": role, "content": content})
        return history

    @staticmethod
    def _summarize_mcp_result(
        tool_name: str,
        output: Any,
        tool_inputs: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Generate a useful text summary from an MCP tool output."""
        if not isinstance(output, dict):
            return f"{tool_name} 调用完成"

        error = output.get("error")
        if error:
            return f"工具返回错误：{error}"

        if tool_name == "pubmed_search":
            return TurnRunner._format_pubmed_search(output, tool_inputs)
        if tool_name == "pubmed_fetch":
            return TurnRunner._format_pubmed_fetch(output, tool_inputs)

        count = output.get("count")
        if count is not None:
            return f"{tool_name} 返回 {count} 条结果"
        return f"{tool_name} 调用完成"

    @staticmethod
    def _format_pubmed_search(
        output: Dict[str, Any],
        tool_inputs: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Format PubMed search results into a readable Markdown list."""
        from urllib.parse import quote

        query = ""
        if isinstance(tool_inputs, dict):
            query = tool_inputs.get("query", "") or ""
        count = output.get("count", "0")
        try:
            count_int = int(count)
        except (TypeError, ValueError):
            count_int = 0

        encoded_query = quote(query.encode("utf-8")) if query else ""
        pubmed_url = f"https://pubmed.ncbi.nlm.nih.gov/?term={encoded_query}"

        if count_int == 0:
            return (
                f"未找到与“{query}”相关的 PubMed 文献。\n\n"
                "建议：\n"
                "- 尝试用英文关键词或同义词；\n"
                "- 去掉过于具体的限定词，扩大检索范围；\n"
                "- 直接提供 PMID 或 DOI，我可以帮你解读。\n\n"
                f"[在 PubMed 中打开检索]({pubmed_url})"
            )

        articles = output.get("articles", []) or []
        lines = [f"找到 {count_int} 条相关文献，以下是前 {len(articles)} 条：\n"]
        for idx, article in enumerate(articles, start=1):
            if not isinstance(article, dict):
                continue
            title = article.get("title", "未知标题") or "未知标题"
            authors = article.get("authors", []) or []
            authors_str = ", ".join(authors[:3])
            if len(authors) > 3:
                authors_str += " et al."
            journal = article.get("journal", "") or ""
            pubdate = article.get("pubdate", "") or ""
            pmid = article.get("pmid", "") or ""
            doi = article.get("doi", "") or ""
            pmid_link = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""
            parts = [p for p in [authors_str, f"*{journal}*" if journal else "", pubdate] if p]
            meta = " · ".join(parts)
            pmid_part = f" · PMID: [{pmid}]({pmid_link})" if pmid else ""
            doi_part = f" · DOI: {doi}" if doi else ""
            lines.append(
                f"{idx}. **{title}**  \n"
                f"   {meta}{pmid_part}{doi_part}"
            )

        lines.append(f"\n[在 PubMed 中查看全部结果]({pubmed_url})")
        return "\n".join(lines)

    @staticmethod
    def _format_pubmed_fetch(
        output: Dict[str, Any],
        tool_inputs: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Format a fetched PubMed article into a readable summary."""
        # `pubmed_fetch` returns the article directly, not wrapped in an `articles` list.
        if isinstance(output, dict) and output.get("articles"):
            article = output["articles"][0]
        elif isinstance(output, dict) and output.get("pmid"):
            article = output
        else:
            return "未获取到 PubMed 文章详情。"
        if not isinstance(article, dict):
            return "PubMed 返回格式异常。"
        title = article.get("title", "未知标题") or "未知标题"
        abstract = article.get("abstract", "") or ""
        pmid = article.get("pmid", "") or ""
        pmid_link = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""
        lines = [f"**{title}**"]
        if pmid:
            lines.append(f"PMID: [{pmid}]({pmid_link})")
        if abstract:
            lines.append(f"\n{abstract}")
        return "\n".join(lines)

    def _handle_clarification(
        self,
        intent: UserIntent,
        working_memory: WorkingMemory,
    ) -> TurnResult:
        """Return a clarification question or debate request to the user."""
        debate_data = intent.metadata.get("debate")
        if debate_data and debate_data.get("options"):
            agent_msg = ChatMessage(
                id=f"msg_{len(working_memory.messages)}",
                type=MessageType.DEBATE_REQUEST,
                content={
                    "debate_id": f"debate_{intent.original_message or 'clarify'}",
                    "topic": debate_data.get("topic", "请选择最符合您需求的选项"),
                    "options": debate_data.get("options", []),
                    "recommendation": debate_data.get("recommendation"),
                    "round_summaries": debate_data.get("round_summaries", []),
                },
                sender="agent",
            )
            working_memory.add_message(agent_msg)
            return TurnResult(
                mode=ExecutionMode.AWAITING_DEBATE,
                response_text=agent_msg.content["topic"],
                agent_message=agent_msg,
            )

        question = (
            intent.metadata.get("clarification_question")
            or "我不太确定您的需求，请再具体描述一下。"
        )

        agent_msg = ChatMessage(
            id=f"msg_{len(working_memory.messages)}",
            type=MessageType.TEXT,
            content=question,
            sender="agent",
        )
        working_memory.add_message(agent_msg)

        return TurnResult(
            mode=ExecutionMode.DIRECT_RESPONSE,
            response_text=question,
            agent_message=agent_msg,
        )

    def _build_debate_resolved_intent(
        self,
        debate_response: Dict[str, Any],
        user_message: str,
    ) -> UserIntent:
        """Convert a user's debate choice into a concrete intent."""
        choice_id = debate_response.get("choice_id", "")
        return self.intent_analyzer._to_user_intent(
            IntentMatch(
                analysis_type=choice_id,
                confidence=1.0,
                source="debate",
                reason="user selected debate option",
            ),
            user_message,
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
        """Route a user intent to the right execution path.

        Uses the structured ``interaction_mode`` and ``scope`` fields when
        available, with backward-compatible fallbacks to ``analysis_type`` and
        ``complexity``.
        """
        interaction_mode = intent.interaction_mode
        scope = intent.scope

        # Backward compatibility for legacy intents that don't set the new fields.
        if intent.analysis_type == "clarification":
            interaction_mode = "clarify"
        elif intent.complexity == "direct_response" and not intent.metadata.get("tool_name"):
            interaction_mode = "answer"

        if interaction_mode == "clarify":
            return self._handle_clarification(intent, working_memory)

        if interaction_mode == "answer":
            return await self._handle_direct_response(
                intent, user_message, working_memory, project_id
            )

        # MCP tool agent loop.
        mcp_tool_name = intent.metadata.get("tool_name")
        if mcp_tool_name and self._tool_registry is not None:
            try:
                return await self._handle_agent_loop(
                    user_message=user_message,
                    working_memory=working_memory,
                    allowed_tools=[t.name for t in self._tool_registry.list_by_source("mcp")],
                )
            except Exception as exc:
                logger.warning(
                    "AgentLoop failed, falling back to direct MCP tool: %s", exc, exc_info=True
                )
                return await self._handle_mcp_tool(
                    mcp_tool_name,
                    intent.metadata.get("tool_inputs", {}),
                    working_memory,
                )

        # Everything else is some form of execution.
        plan_result, tree = await self.task_decomposer.decompose_with_plan(
            intent, context={"project_id": project_id}
        )

        plan: Optional[Plan] = None
        if plan_store is not None:
            plan = Plan(
                plan_id=_new_plan_id(),
                session_id=session_id,
                project_id=project_id,
                status=PlanStatus.PENDING_APPROVAL,
                is_fallback=plan_result.is_fallback,
                intent_analysis_type=intent.analysis_type,
                intent_complexity=intent.complexity,
                plan_result=plan_result,
                task_tree=tree,
                working_memory=working_memory,
            )
            await plan_store.create(plan)

        if enqueue_skills and job_service is not None:
            return await self._enqueue_execution(
                intent=intent,
                tree=tree,
                plan=plan,
                working_memory=working_memory,
                session_id=session_id,
                project_id=project_id,
                job_service=job_service,
                plan_store=plan_store,
                plan_mode=plan_mode,
            )

        if scope == "single_step" or intent.complexity == "single_step":
            return await self._handle_single_step(
                tree, working_memory, project_id, intent=intent, user_message=user_message
            )

        return await self._handle_workflow(
            tree, working_memory, project_id, intent=intent, user_message=user_message
        )

    @staticmethod
    def _is_domain_template_analysis(intent: UserIntent) -> bool:
        """Return True for domain-specific analysis workflows that belong on canvas."""
        return intent.domain is not None

    async def _enqueue_execution(
        self,
        intent: UserIntent,
        tree: TaskTree,
        plan: Optional[Plan],
        working_memory: WorkingMemory,
        session_id: str,
        project_id: str,
        job_service: Any,
        plan_store: Optional[PlanStore],
        plan_mode: bool = False,
    ) -> TurnResult:
        """Submit a task tree to the background job queue or request approval."""
        is_domain = self._is_domain_template_analysis(intent)
        needs_approval = plan_mode or is_domain or intent.complexity == "complex"

        if plan is not None and needs_approval:
            if is_domain:
                response_text = "我为您生成了一个分析计划，请确认后再执行。"
                plan_payload = PlanPresenter.to_user_payload(plan)
                agent_msg = ChatMessage(
                    id=f"msg_{len(working_memory.messages)}",
                    type=MessageType.PLAN_REQUEST,
                    content={
                        "plan_id": plan.plan_id,
                        "plan": plan_payload,
                        "response_text": response_text,
                    },
                    sender="agent",
                )
            else:
                response_text = "我为您规划了以下执行步骤，请确认后再执行。"
                estimates = {}
                if plan is not None:
                    estimates = {
                        "total_estimated_cost_usd": plan.plan_result.total_estimated_cost_usd,
                        "total_estimated_duration_seconds": plan.plan_result.total_estimated_duration_seconds,
                    }
                agent_msg = ChatMessage(
                    id=f"msg_{len(working_memory.messages)}",
                    type=MessageType.EXECUTION_PLAN,
                    content={
                        "plan_id": plan.plan_id,
                        "response_text": response_text,
                        "tasks": [t.model_dump() for t in tree.tasks],
                        "progress": self._build_initial_progress(tree),
                        "estimates": estimates,
                    },
                    sender="agent",
                )
            working_memory.add_message(agent_msg)
            return TurnResult(
                mode=ExecutionMode.AWAITING_PLAN_APPROVAL,
                response_text=response_text,
                task_tree=tree,
                agent_message=agent_msg,
                plan_id=plan.plan_id,
            )

        mode = (
            JobMode.SINGLE_STEP
            if intent.scope == "single_step" or intent.complexity == "single_step"
            else JobMode.WORKFLOW
        )
        job = await job_service.create_job(
            session_id=session_id,
            project_id=project_id,
            working_memory=working_memory,
            task_tree=tree,
            mode=mode,
            plan_id=plan.plan_id if plan is not None else None,
        )
        if plan is not None and plan_store is not None:
            plan.status = PlanStatus.APPROVED
            plan.approved_by = "system"
            await plan_store.update(plan)

        response_text = "已提交后台执行，完成后会通知您。"
        agent_msg = ChatMessage(
            id=f"msg_{len(working_memory.messages)}",
            type=MessageType.TODO_LIST,
            content={
                "text": response_text,
                "tasks": [t.model_dump() for t in tree.tasks],
                "progress": self._build_initial_progress(tree),
                "job_id": job.job_id,
            },
            sender="agent",
        )
        working_memory.add_message(agent_msg)
        return TurnResult(
            mode=ExecutionMode.QUEUED,
            response_text=response_text,
            task_tree=tree,
            agent_message=agent_msg,
            job_id=job.job_id,
            plan_id=plan.plan_id if plan is not None else None,
        )

    @staticmethod
    def _build_initial_progress(tree: TaskTree) -> Dict[str, Any]:
        total = len(tree.tasks)
        return {
            "total": total,
            "pending": total,
            "running": 0,
            "completed": 0,
            "failed": 0,
            "awaiting_human": 0,
            "percent": 0,
        }

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
        low_risk_keywords = {"analysis", "plot", "qc", "visualize", "统计", "画图", "质控"}
        high_risk_keywords = {"delete", "drop", "overwrite", "remove", "清空", "删除", "覆盖", "替换"}

        if self._llm_client is None:
            return self._heuristic_risk_score(
                user_message, intent, low_risk_keywords, high_risk_keywords
            )

        try:
            prompt = self._build_risk_prompt(intent, user_message, working_memory, project_id)
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

    @staticmethod
    def _build_risk_prompt(
        intent: UserIntent,
        user_message: str,
        working_memory: WorkingMemory,
        project_id: Optional[str] = None,
    ) -> str:
        return (
            "Evaluate the risk that executing this user request will lead to "
            "data loss, destruction, or unintended modification of project state.\n\n"
            f"User message: {user_message}\n"
            f"Intent: {intent.analysis_type}\n"
            f"Intent confidence: {intent.confidence:.2f}\n"
            f"Project ID: {project_id or 'unknown'}\n\n"
            "Respond with a JSON object: {\"risk_score\": 0.0} where the score is "
            "a float between 0.0 (no risk) and 1.0 (very high risk)."
        )

    @staticmethod
    def _parse_risk_score(response: Any) -> float:
        """Parse a risk score from an LLM response."""
        text = ""
        if isinstance(response, str):
            text = response
        elif isinstance(response, dict):
            if "risk_score" in response:
                return float(response["risk_score"])
            text = str(response.get("content", response))
        else:
            text = str(response)

        # Try to extract JSON from the text.
        try:
            match = re.search(r"\{[^}]*\"risk_score\"[^}]*\}", text)
            if match:
                data = json.loads(match.group(0))
                return float(data["risk_score"])
        except Exception:
            pass

        # Fall back to a plain float in the response.
        try:
            return float(text.strip())
        except Exception:
            pass

        return 0.0

    @staticmethod
    def _heuristic_risk_score(
        user_message: str,
        intent: UserIntent,
        low_risk_keywords: set,
        high_risk_keywords: set,
    ) -> float:
        message_lower = user_message.lower()
        score = 0.0
        if any(kw in message_lower for kw in high_risk_keywords):
            score += 0.7
        if any(kw in message_lower for kw in low_risk_keywords):
            score -= 0.3
        if intent.analysis_type in ("file_conversion", "qa", "information_request"):
            score -= 0.2
        return max(0.0, min(1.0, score))

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

        if intent is not None and user_message is not None and working_memory is not None:
            context["risk_score"] = await self._evaluate_risk(
                intent, user_message, working_memory, project_id
            )
        else:
            context["risk_score"] = 0.0

        return context

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
        context = await self._build_orchestrator_context(
            project_id, intent=intent, user_message=user_message, working_memory=working_memory
        )
        results = await orchestrator.run_tree(tree, context=context)

        # Check for HITL
        hitl_info = self._extract_hitl(results)
        if hitl_info:
            return self._build_hitl_result(tree, hitl_info, working_memory)

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

    async def _handle_workflow(
        self,
        tree: TaskTree,
        working_memory: WorkingMemory,
        project_id: str,
        intent: Optional[UserIntent] = None,
        user_message: Optional[str] = None,
    ) -> TurnResult:
        """Handle complex multi-step workflows."""
        # Handle non-executable fallback suggestions directly.
        if self._is_fallback_suggestion(tree):
            return self._build_fallback_result(tree, working_memory)

        orchestrator = self._get_orchestrator()
        context = await self._build_orchestrator_context(
            project_id, intent=intent, user_message=user_message, working_memory=working_memory
        )
        results = await orchestrator.run_tree(tree, context=context)

        # Check for HITL
        hitl_info = self._extract_hitl(results)
        if hitl_info:
            return self._build_hitl_result(tree, hitl_info, working_memory)

        response_text = f"已为您规划 {len(tree.tasks)} 个分析步骤。"

        # Extract any plots produced during the workflow
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
            },
            sender="agent",
        )
        working_memory.add_message(agent_msg)

        return TurnResult(
            mode=ExecutionMode.WORKFLOW,
            response_text=response_text,
            task_tree=tree,
            progress=orchestrator.get_progress(tree),
            agent_message=agent_msg,
            attachments=plot_messages,
        )

    async def resume_hitl(
        self,
        session_id: str,
        task_id: str,
        choice: str,
        parameters: Dict[str, Any],
        working_memory: WorkingMemory,
        task_tree: TaskTree,
    ) -> TurnResult:
        """Resume execution after receiving HITL response."""
        orchestrator = self._get_orchestrator()

        result = await orchestrator.resume_task(
            task_tree,
            task_id,
            {"choice": choice, "parameters": parameters},
        )

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

    def _build_fallback_result(
        self,
        tree: TaskTree,
        working_memory: WorkingMemory,
    ) -> TurnResult:
        """Build a TurnResult for a non-executable fallback suggestion."""
        suggestion = tree.tasks[0].description
        agent_msg = ChatMessage(
            id=f"msg_{len(working_memory.messages)}",
            type=MessageType.TODO_LIST,
            content={
                "text": suggestion,
                "is_fallback": True,
                "tasks": [],
            },
            sender="agent",
        )
        working_memory.add_message(agent_msg)

        return TurnResult(
            mode=ExecutionMode.WORKFLOW,
            response_text=suggestion,
            task_tree=tree,
            agent_message=agent_msg,
        )

    def _extract_hitl(self, results: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Scan execution results for HITL checkpoints."""
        for task_id, result in results.items():
            if isinstance(result, dict) and "hitl" in result:
                return {"checkpoint": result["hitl"], "task_id": task_id}
        return None

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
            skill_id = result.get("skill") or (task.skills_required[0] if task and task.skills_required else None)

            plot_type = skill_output.get("plot_type") or (task.name if task else "visualization")
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

    def _build_hitl_result(
        self,
        tree: TaskTree,
        hitl_info: Dict[str, Any],
        working_memory: WorkingMemory,
    ) -> TurnResult:
        """Build a TurnResult when execution pauses for HITL."""
        response_text = "部分步骤需要您确认参数。"
        agent_msg = ChatMessage(
            id=f"msg_{len(working_memory.messages)}",
            type=MessageType.HITL_REQUEST,
            content=hitl_info,
            sender="agent",
        )
        working_memory.add_message(agent_msg)

        return TurnResult(
            mode=ExecutionMode.AWAITING_HITL,
            response_text=response_text,
            task_tree=tree,
            hitl_task_id=hitl_info["task_id"],
            hitl_checkpoint=hitl_info["checkpoint"],
            agent_message=agent_msg,
        )

    def _build_error_result(
        self, error: Union[str, TurnError], working_memory: WorkingMemory
    ) -> TurnResult:
        """Build a TurnResult when an error occurs."""
        if isinstance(error, TurnError):
            payload = error.to_payload()
            recovery = payload["recovery_action"]
            response_text = f"抱歉，处理您的请求时出现了问题：{payload['message']}"
            if recovery == "retry":
                response_text += " 已自动重试一次仍未成功，请稍后再试或换一种方式描述。"
            elif recovery == "clarify":
                response_text += " 能否补充说明一下您的具体需求？"
            elif recovery == "approve":
                response_text += " 该操作需要您确认授权。"
        else:
            payload = {
                "error_type": "ExecutionError",
                "message": str(error),
                "recovery_action": "escalate",
                "retryable": False,
                "context": {},
            }
            response_text = f"抱歉，处理您的请求时出现了问题：{error}"

        agent_msg = ChatMessage(
            id=f"msg_{len(working_memory.messages)}",
            type=MessageType.ERROR,
            content={"error": payload, "message": response_text},
            sender="agent",
        )
        working_memory.add_message(agent_msg)

        return TurnResult(
            mode=ExecutionMode.ERROR,
            response_text=response_text,
            error=payload["message"],
            agent_message=agent_msg,
        )

    def _compress_working_memory(
        self, working_memory: WorkingMemory, current_goal: str
    ) -> str:
        """Compress recent conversation history into a concise context string.

        Uses ContextCompressor to keep only the most relevant messages for the
        current user request. Falls back to the latest 6 raw messages if
        compression fails.
        """
        messages = working_memory.get_recent_messages()
        if not messages:
            return ""

        now = datetime.now(timezone.utc)
        items: List[ContextItem] = []
        for msg in messages:
            raw_content = msg.content
            if not isinstance(raw_content, str):
                try:
                    text = json.dumps(raw_content, ensure_ascii=False)
                except Exception:
                    text = str(raw_content)
            else:
                text = raw_content
            if not text.strip():
                continue
            hours = 0.0
            if msg.timestamp:
                try:
                    hours = (now - msg.timestamp).total_seconds() / 3600.0
                except Exception:
                    hours = 0.0
            items.append(
                ContextItem(
                    content=f"{msg.sender}: {text}",
                    type=msg.type.value,
                    is_pinned=msg.id in working_memory.pinned_items,
                    is_upstream_result=bool(msg.task_id),
                    agent_importance=0.7 if msg.sender == "agent" else 0.5,
                    hours_since_created=hours,
                )
            )

        try:
            compressed = self.compressor.compress(items, current_goal=current_goal)
        except Exception:
            compressed = items[-6:]

        return "\n".join(item.content for item in compressed)

    def _format_extra_context(self) -> str:
        """Render CBKB/semantic-memory enrichment into a short project context string."""
        if not self._extra_context:
            return ""
        parts: List[str] = []
        snippets = self._extra_context.get("memory_snippets") or []
        if snippets:
            parts.append("Relevant memory snippets:\n" + "\n".join(f"- {s}" for s in snippets[:3]))
        experiments = self._extra_context.get("recent_experiments") or []
        if experiments:
            parts.append(
                "Recent experiments:\n"
                + "\n".join(f"- {e.get('bundle_id', '')}: {e.get('summary', '')}" for e in experiments[:3])
            )
        sops = self._extra_context.get("recent_sops") or []
        if sops:
            parts.append(
                "Relevant SOPs:\n"
                + "\n".join(f"- {s.get('name', '')} ({s.get('category', '')})" for s in sops[:3])
            )
        anomalies = self._extra_context.get("recent_anomalies") or []
        if anomalies:
            parts.append(
                "Recent anomalies:\n"
                + "\n".join(f"- {a.get('phase_type', '')}: {a.get('summary', '')}" for a in anomalies[:3])
            )
        return "\n\n".join(parts)

    async def _generate_general_help_response(
        self, user_message: str, working_memory: WorkingMemory
    ) -> str:
        """Generate a code/explanation response for general help requests.

        Uses Prompter with compressed conversation history and CBKB-enriched
        project context. Falls back to a safe template response if LLM is not
        configured or fails.
        """
        llm = LLMClient()
        if not llm.is_configured():
            return (
                "我可以帮您写代码或解释数据处理逻辑，但需要配置 LLM 才能生成具体代码。\n"
                "请设置 OPENAI_API_KEY，或告诉我您想处理什么数据，我会尽量给出建议。"
            )

        if self._context_bundle is not None:
            # Use the already assembled, token-safe context from ContextEngine.
            messages = self._context_bundle.to_prompt(user_message)
            # Keep only system/assistant messages; the user message will be appended below.
            prompt_messages = [m for m in messages if m.get("role") != "user"]
            prompt_messages.append({"role": "user", "content": user_message})
        else:
            compressed_history = self._compress_working_memory(working_memory, user_message)
            extra_context = self._format_extra_context()
            project_context = "\n\n".join(filter(None, [compressed_history, extra_context]))

            prompt = self.prompter.build_prompt(
                user_message=user_message,
                working_memory=WorkingMemory(max_messages=0),
                project_context=project_context,
            )
            prompt_messages = [{"role": "user", "content": prompt}]

        try:
            return await llm.chat_completion(
                messages=prompt_messages,
                temperature=0.2,
                max_tokens=1500,
                session_id=getattr(self, "_session_id", None),
                project_id=getattr(self, "_project_id", None),
                request_id=f"{getattr(self, '_turn_request_id', 'code')}_code",
            )
        except Exception:
            return (
                "我目前无法调用 LLM 生成代码。请检查 OPENAI_API_KEY 配置，"
                "或把需求拆分成更具体的步骤。"
            )

    async def _generate_direct_response_via_llm(
        self,
        response_type: str,
        user_message: str,
        intent: UserIntent,
        working_memory: WorkingMemory,
        project_id: Optional[str] = None,
    ) -> Optional[str]:
        """Generate a greeting/QA/information direct response via the configured LLM.

        Falls back to static templates when the LLM client is unavailable or fails.
        """
        if self._llm_client is None:
            return None

        import logging

        logger = logging.getLogger(__name__)

        # Build response-type-specific instructions.
        type_instructions = {
            "greeting": (
                "Greet the user warmly and briefly introduce HomomicsLab. "
                "Mention that you can help with bioinformatics analysis, "
                "experiment design, code snippets, and workflow building."
            ),
            "qa": (
                "Answer the user's question accurately in a bioinformatics context. "
                "When project context, SOPs, or skills are relevant, use them to give "
                "actionable HomomicsLab-specific guidance rather than a generic answer."
            ),
            "information_request": (
                "Explain what HomomicsLab can do for the requested domain. List relevant "
                "analysis steps, SOPs, and executable skills when known, and offer to run "
                "them for the user. Keep the response structured and actionable."
            ),
        }

        system_prompt = (
            "You are HomomicsLab, an AI assistant specialized in bioinformatics and computational biology. "
            "You have access to project context, SOPs, CBKB knowledge, and executable skills/workflows. "
            "Respond to the user in a helpful, accurate, and structured way.\n\n"
            f"Task type: {response_type}\n"
            f"Instructions: {type_instructions.get(response_type, type_instructions['qa'])}\n\n"
            "Use the provided context and intent, but do not mention internal fields or system internals."
        )

        messages: List[Dict[str, str]] = []

        if self._context_bundle is not None:
            # The ContextEngine already assembles token-safe project state, CBKB
            # retrieval, semantic memory, and conversation history. Prepend our
            # direct-response system instruction so the model knows how to answer.
            messages = self._context_bundle.to_prompt(user_message)
            messages.insert(0, {"role": "system", "content": system_prompt})
        else:
            # Fallback minimal context when the context engine is not used.
            context_parts: List[str] = [
                f"Intent: type={intent.analysis_type}, domain={intent.domain or 'none'}, "
                f"analysis_type={intent.analysis_type or 'none'}, confidence={intent.confidence:.2f}"
            ]
            recent_messages = working_memory.get_recent_messages()[-6:]
            if recent_messages:
                history_lines = []
                for msg in recent_messages:
                    content = msg.content
                    if not isinstance(content, str):
                        try:
                            content = json.dumps(content, ensure_ascii=False)
                        except Exception:
                            content = str(content)
                    history_lines.append(f"{msg.sender}: {content}")
                context_parts.append("Recent conversation:\n" + "\n".join(history_lines))

            if self.project_state_manager is not None and project_id is not None:
                try:
                    project_state = self.project_state_manager.load(project_id)
                    context_parts.append(project_state.to_prompt_text())
                except Exception:
                    logger.debug("Failed to load project state for LLM direct response", exc_info=True)

            context_text = "\n\n".join(context_parts)
            messages = [{"role": "system", "content": system_prompt}]
            if context_text:
                messages.append({"role": "system", "content": context_text})
            messages.append({"role": "user", "content": user_message})

        try:
            return await self._llm_client.chat_completion(
                messages=messages,
                temperature=0.3,
                max_tokens=2000,
                session_id=getattr(self, "_session_id", None),
                project_id=getattr(self, "_project_id", None),
                request_id=f"{getattr(self, '_turn_request_id', 'direct')}_direct",
            )
        except Exception:
            logger.warning("LLM direct response failed for type %s; using fallback", response_type, exc_info=True)
            return None

    async def _generate_greeting_response(
        self,
        user_message: str,
        working_memory: WorkingMemory,
        project_id: Optional[str] = None,
    ) -> str:
        """Return a friendly self-introduction for greeting intents.

        Greetings are answered instantly with a static template to avoid blocking the
        chat on an LLM call; the LLM is still used for substantive questions.
        """
        return (
            "Hello! I'm **HomomicsLab**, your AI assistant specialized in bioinformatics "
            "and computational biology.\n\n"
            "I can help you with:\n"
            "- Bioinformatics analysis (genomics, transcriptomics, single-cell, proteomics, etc.)\n"
            "- Experimental design and statistical frameworks\n"
            "- Code snippets in Python, R, bash, SQL, Nextflow, Snakemake, and WDL\n"
            "- Workflow building, automation, reproducibility, and HPC/cloud optimization\n\n"
            "What project or analysis can I help you with today?"
        )

    async def _generate_qa_response(
        self,
        intent: UserIntent,
        user_message: str,
        working_memory: WorkingMemory,
        project_id: Optional[str] = None,
    ) -> str:
        """Generate a direct text response for QA-style queries.

        Uses the configured LLM when available; falls back to domain-specific
        Chinese templates.
        """
        llm_response = await self._generate_direct_response_via_llm(
            response_type="qa",
            user_message=user_message,
            intent=intent,
            working_memory=working_memory,
            project_id=project_id,
        )
        if llm_response:
            return llm_response

        domain = intent.domain or intent.analysis_type
        qa_responses = {
            "single_cell": (
                "单细胞测序（scRNA-seq）是一种在单个细胞水平上分析基因表达的技术。"
                "它可以揭示细胞异质性，发现稀有细胞类型，并追踪细胞发育轨迹。"
            ),
            "spatial": (
                "空间转录组学结合了基因表达分析和空间位置信息，"
                "可以在组织切片上绘制基因表达图谱。"
            ),
            "metagenomics": (
                "宏基因组学通过直接提取环境样本中全部微生物基因组 DNA，"
                "研究群落组成、功能和多样性，无需培养。"
            ),
            "genomics": (
                "基因组学是对生物体全部 DNA 的研究，包括变异检测、结构变异、"
                "功能注释等分析内容。"
            ),
            "transcriptomics": (
                "转录组学研究细胞或组织中全部 RNA 分子的表达情况，"
                "常用于差异表达、通路富集等分析。"
            ),
            "proteomics": (
                "蛋白质组学是对生物体全部蛋白质的研究，包括蛋白鉴定、定量、"
                "翻译后修饰等分析。"
            ),
            "epigenomics": (
                "表观基因组学研究不改变 DNA 序列的遗传调控机制，"
                "如 DNA 甲基化、组蛋白修饰、染色质可及性等。"
            ),
            "file_conversion": (
                "我可以帮您转换常见的生物信息学数据格式，"
                "如 CSV、h5ad、10x Genomics 格式等。"
            ),
            "general": (
                "我是一个生物信息学分析助手，可以帮您进行单细胞分析、"
                "空间转录组分析、实验设计等任务。请问有什么具体需求？"
            ),
        }
        return qa_responses.get(domain, qa_responses["general"])

    async def _generate_information_request_response(
        self,
        intent: UserIntent,
        working_memory: WorkingMemory,
        project_id: Optional[str] = None,
    ) -> str:
        """Respond to "what can you do / what are the steps" style queries.

        Uses the configured LLM when available; falls back to step-by-step
        Chinese templates.
        """
        llm_response = await self._generate_direct_response_via_llm(
            response_type="information_request",
            user_message=intent.original_message or "",
            intent=intent,
            working_memory=working_memory,
            project_id=project_id,
        )
        if llm_response:
            return llm_response

        domain = intent.domain
        if domain == "single_cell":
            return (
                "单细胞转录组分析通常包括以下主要步骤：\n"
                "1. 数据质控（QC）：过滤低质量细胞和基因；\n"
                "2. 标准化与归一化；\n"
                "3. 高变基因选择；\n"
                "4. 降维（PCA、UMAP/t-SNE）；\n"
                "5. 聚类与细胞类型注释；\n"
                "6. 差异表达分析；\n"
                "7. 通路富集与可视化。\n\n"
                "您可以上传数据后，让我直接帮您跑完整流程或只做其中某一步。"
            )
        if domain == "spatial":
            return (
                "空间转录组分析通常包括以下主要步骤：\n"
                "1. 数据加载与质控；\n"
                "2. 空间坐标与表达矩阵整合；\n"
                "3. 降维与聚类；\n"
                "4. 空间可变基因分析；\n"
                "5. 组织区域注释与细胞类型去卷积；\n"
                "6. 可视化（spot/细胞空间表达图）。\n\n"
                "请上传数据或告诉我您想重点关注的空间生物学问题。"
            )
        if domain == "metagenomics":
            return (
                "宏基因组分析通常包括以下主要步骤：\n"
                "1. 原始数据质控与去宿主；\n"
                "2. 序列拼接与基因预测；\n"
                "3. 物种注释与分类；\n"
                "4. 功能注释（KEGG/GO/CAZy 等）；\n"
                "5. Alpha/Beta 多样性分析；\n"
                "6. 差异物种/功能分析。\n\n"
                "您可以提供原始测序数据或 OTU/ASV 表，让我帮您分析。"
            )
        return (
            "HomomicsLab 支持多种生物信息学分析，包括：\n"
            "- 单细胞转录组分析（质控、聚类、差异表达、细胞注释等）\n"
            "- 空间转录组分析\n"
            "- 宏基因组/微生物组分析\n"
            "- 基因组、转录组、蛋白质组、表观组分析\n"
            "- 文献检索（PubMed）、蛋白查询（UniProt）、数据集查询（GEO）\n"
            "- 代码/脚本生成与数据处理帮助\n\n"
            "请告诉我您想进行哪类分析，或上传数据让我开始。"
        )
