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
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

from homomics_lab.agent.agent_registry import AgentRegistry, get_default_registry
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
    ):
        self._cbkb = cbkb
        self.intent_analyzer = intent_analyzer or IntentAnalyzer(debate=debate, cbkb=self._cbkb)
        self.task_decomposer = task_decomposer or TaskDecomposer(cbkb=self._cbkb)
        self._orchestrator = orchestrator
        self._registry = registry
        self._progress_callback = progress_callback
        self._workspace_manager = workspace_manager
        self._phase_gate_evaluator = phase_gate_evaluator
        self._replanning_engine = replanning_engine
        self._supervisor = supervisor
        self._reviewer = reviewer
        self._message_bus = message_bus
        self._debate = debate
        self._tool_registry = tool_registry
        self.memory_manager = memory_manager
        self.prompter = prompter or Prompter()
        self.compressor = compressor or ContextCompressor(max_items=6, max_chars_per_item=1000)
        self.context_engine = context_engine
        self.project_state_manager = project_state_manager
        self._extra_context: Dict[str, Any] = {}
        self._context_bundle: Optional[ContextBundle] = None

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
        # 1. Record user message
        user_msg = ChatMessage(
            id=f"msg_{len(working_memory.messages)}",
            type=MessageType.TEXT,
            content=user_message,
            sender="user",
        )
        working_memory.add_message(user_msg)

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
                try:
                    await asyncio.sleep(0.5)
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
                except TurnError as exc2:
                    turn_result = self._build_error_result(exc2, working_memory)
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

        return turn_result or self._build_error_result(
            ExecutionError("Turn produced no result"), working_memory
        )

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
    ) -> TurnResult:
        """Handle questions and general help requests that need no skill execution."""
        if intent.analysis_type == "greeting":
            response_text = self._generate_greeting_response(user_message)
        elif intent.analysis_type == "general_help":
            response_text = await self._generate_general_help_response(
                user_message, working_memory
            )
        elif intent.analysis_type == "information_request":
            response_text = self._generate_information_request_response(intent)
        else:
            response_text = self._generate_qa_response(intent, user_message)

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
            response_text = self._summarize_mcp_result(tool_name, content)
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

    @staticmethod
    def _summarize_mcp_result(tool_name: str, output: Any) -> str:
        """Generate a short text summary from an MCP tool output."""
        if isinstance(output, dict):
            count = output.get("count")
            if count is not None:
                return f"{tool_name} 返回 {count} 条结果"
            error = output.get("error")
            if error:
                return f"工具返回错误：{error}"
        return f"{tool_name} 调用完成"

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
                intent, user_message, working_memory
            )

        # MCP tool fast path.
        mcp_tool_name = intent.metadata.get("tool_name")
        if mcp_tool_name and self._tool_registry is not None:
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
            return await self._handle_single_step(tree, working_memory, project_id)

        return await self._handle_workflow(tree, working_memory, project_id)

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
                agent_msg = ChatMessage(
                    id=f"msg_{len(working_memory.messages)}",
                    type=MessageType.EXECUTION_PLAN,
                    content={
                        "plan_id": plan.plan_id,
                        "response_text": response_text,
                        "tasks": [t.model_dump() for t in tree.tasks],
                        "progress": self._build_initial_progress(tree),
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

    async def _handle_single_step(
        self,
        tree: TaskTree,
        working_memory: WorkingMemory,
        project_id: str,
    ) -> TurnResult:
        """Handle single-step tasks (e.g., file conversion)."""
        # Handle non-executable fallback suggestions directly.
        if self._is_fallback_suggestion(tree):
            return self._build_fallback_result(tree, working_memory)

        orchestrator = self._get_orchestrator()
        context = {"project_id": project_id}
        if getattr(self, "_trace_id", None):
            context["trace_id"] = self._trace_id
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
    ) -> TurnResult:
        """Handle complex multi-step workflows."""
        # Handle non-executable fallback suggestions directly.
        if self._is_fallback_suggestion(tree):
            return self._build_fallback_result(tree, working_memory)

        orchestrator = self._get_orchestrator()
        context = {"project_id": project_id}
        if getattr(self, "_trace_id", None):
            context["trace_id"] = self._trace_id
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
            )
        except Exception:
            return (
                "我目前无法调用 LLM 生成代码。请检查 OPENAI_API_KEY 配置，"
                "或把需求拆分成更具体的步骤。"
            )

    def _generate_greeting_response(self, user_message: str) -> str:
        """Return a friendly self-introduction for greeting intents."""
        return (
            "Hello! I'm HomomicsLab, an AI assistant specialized in bioinformatics. "
            "I can help you design experiments, analyze omics data (single-cell, spatial, "
            "genomics, transcriptomics, etc.), write code snippets, interpret results, "
            "and build analysis workflows. What would you like to work on?"
        )

    def _generate_qa_response(self, intent: UserIntent, user_message: str) -> str:
        """Generate a direct text response for QA-style queries.

        Uses structured intent metadata to pick a domain-specific explanation
        when available, falling back to a generic answer.
        """
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

    def _generate_information_request_response(self, intent: UserIntent) -> str:
        """Respond to "what can you do / what are the steps" style queries."""
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
