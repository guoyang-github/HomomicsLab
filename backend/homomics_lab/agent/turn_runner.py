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

from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from homomics_lab.agent.agent_registry import AgentRegistry, get_default_registry
from homomics_lab.agent.factory import create_default_agents
from homomics_lab.agent.intent_analyzer import IntentAnalyzer, UserIntent
from homomics_lab.agent.intent.models import IntentMatch
from homomics_lab.agent.message_bus import AgentMessageBus
from homomics_lab.agent.orchestrator import Orchestrator
from homomics_lab.agent.phase_gate import PhaseGateEvaluator
from homomics_lab.agent.plan.replanning import DynamicReplanningEngine
from homomics_lab.agent.task_decomposer import TaskDecomposer
from homomics_lab.context.memory_manager import MemoryManager
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
    ):
        self._cbkb = cbkb
        self.intent_analyzer = intent_analyzer or IntentAnalyzer(debate=debate)
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
    ) -> TurnResult:
        """Execute one full turn: from user message to agent response.

        This is the unified entry point. All conversational flows go through here.

        Args:
            job_service: Optional JobService for background execution.
            enqueue_skills: If True, skill-executing turns are enqueued instead of
                awaited synchronously.
        """
        # 1. Record user message
        user_msg = ChatMessage(
            id=f"msg_{len(working_memory.messages)}",
            type=MessageType.TEXT,
            content=user_message,
            sender="user",
        )
        working_memory.add_message(user_msg)

        try:
            # 2. Enrich context from long-term memory
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

            # 3. Analyze intent with conversation context
            if debate_response is not None:
                intent = self._build_debate_resolved_intent(
                    debate_response, user_message
                )
            else:
                intent = await self.intent_analyzer.analyze(
                    user_message,
                    working_memory=working_memory,
                    extra_context=extra_context,
                )

            # 3.5 Clarification handling
            if intent.analysis_type == "clarification":
                turn_result = self._handle_clarification(intent, working_memory)
            else:
                # 3.6 MCP tool fast path
                mcp_tool_name = intent.metadata.get("tool_name")
                if mcp_tool_name and self._tool_registry is not None:
                    turn_result = await self._handle_mcp_tool(
                        mcp_tool_name,
                        intent.metadata.get("tool_inputs", {}),
                        working_memory,
                    )
                else:
                    # 4. Route based on intent complexity
                    if intent.complexity == "direct_response":
                        turn_result = await self._handle_direct_response(
                            intent, user_message, working_memory
                        )
                    else:
                        # Decompose into a canonical plan and executable task tree.
                        plan_result, tree = await self.task_decomposer.decompose_with_plan(
                            intent, context={"project_id": project_id}
                        )

                        # Persist the plan if a store is available.
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

                        # Optionally submit skill execution to the background queue.
                        if enqueue_skills and job_service is not None:
                            # Fallback / LLM-generated plans require explicit approval first.
                            if plan is not None and plan.is_fallback:
                                response_text = (
                                    "我为您生成了一个分析计划，请确认后再执行。"
                                )
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
                                working_memory.add_message(agent_msg)
                                turn_result = TurnResult(
                                    mode=ExecutionMode.AWAITING_PLAN_APPROVAL,
                                    response_text=response_text,
                                    task_tree=tree,
                                    agent_message=agent_msg,
                                    plan_id=plan.plan_id,
                                )
                            else:
                                mode = (
                                    JobMode.SINGLE_STEP
                                    if intent.complexity == "single_step"
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
                                # Record the plan on the job for reproducibility.
                                if plan is not None:
                                    plan.status = PlanStatus.APPROVED
                                    plan.approved_by = "system"
                                    await plan_store.update(plan)

                                response_text = "已提交后台执行，完成后会通知您。"
                                agent_msg = ChatMessage(
                                    id=f"msg_{len(working_memory.messages)}",
                                    type=MessageType.TEXT,
                                    content=response_text,
                                    sender="agent",
                                )
                                working_memory.add_message(agent_msg)
                                turn_result = TurnResult(
                                    mode=ExecutionMode.QUEUED,
                                    response_text=response_text,
                                    task_tree=tree,
                                    agent_message=agent_msg,
                                    job_id=job.job_id,
                                    plan_id=plan.plan_id if plan is not None else None,
                                )
                        elif intent.complexity == "single_step":
                            turn_result = await self._handle_single_step(
                                tree, working_memory, project_id
                            )
                        else:
                            # Complex workflow
                            turn_result = await self._handle_workflow(
                                tree, working_memory, project_id
                            )
        except Exception as e:
            turn_result = self._build_error_result(str(e), working_memory)

        # 5. Persist turn to long-term memory (best-effort)
        if self.memory_manager is not None:
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

        return turn_result

    async def _handle_direct_response(
        self,
        intent: UserIntent,
        user_message: str,
        working_memory: WorkingMemory,
    ) -> TurnResult:
        """Handle questions and general help requests that need no skill execution."""
        if intent.analysis_type == "general_help":
            response_text = await self._generate_general_help_response(user_message)
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
        import json

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
        self, error: str, working_memory: WorkingMemory
    ) -> TurnResult:
        """Build a TurnResult when an error occurs."""
        response_text = f"抱歉，处理您的请求时出现了问题：{error}"
        agent_msg = ChatMessage(
            id=f"msg_{len(working_memory.messages)}",
            type=MessageType.ERROR,
            content={"error": error, "message": response_text},
            sender="agent",
        )
        working_memory.add_message(agent_msg)

        return TurnResult(
            mode=ExecutionMode.ERROR,
            response_text=response_text,
            error=error,
            agent_message=agent_msg,
        )

    async def _generate_general_help_response(self, user_message: str) -> str:
        """Generate a code/explanation response for general help requests.

        Delegates to an LLM when configured; otherwise returns a safe template
        response asking the user to provide an LLM key or rephrase.
        """
        llm = LLMClient()
        if not llm.is_configured():
            return (
                "我可以帮您写代码或解释数据处理逻辑，但需要配置 LLM 才能生成具体代码。\n"
                "请设置 OPENAI_API_KEY，或告诉我您想处理什么数据，我会尽量给出建议。"
            )

        system_prompt = (
            "You are a helpful coding and data-processing assistant. "
            "The user is asking for help with a general programming or data task. "
            "Respond in the user's language when possible. "
            "Provide a short code snippet followed by a brief explanation. "
            "Do not execute any code; only return text. "
            "If the request is unsafe or could modify files, include a warning."
        )
        user_prompt = f"User request: {user_message}\n\nProvide code and explanation."

        try:
            return await llm.chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=1500,
            )
        except Exception:
            return (
                "我目前无法调用 LLM 生成代码。请检查 OPENAI_API_KEY 配置，"
                "或把需求拆分成更具体的步骤。"
            )

    def _generate_qa_response(self, intent: UserIntent, user_message: str) -> str:
        """Generate a direct text response for QA-style queries.

        In production this delegates to an LLM. For MVP we use templates.
        """
        # Simple template-based responses for MVP
        qa_responses = {
            "single_cell_analysis": (
                "单细胞测序（scRNA-seq）是一种在单个细胞水平上分析基因表达的技术。"
                "它可以揭示细胞异质性，发现稀有细胞类型，并追踪细胞发育轨迹。"
            ),
            "spatial_analysis": (
                "空间转录组学结合了基因表达分析和空间位置信息，"
                "可以在组织切片上绘制基因表达图谱。"
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
        return qa_responses.get(
            intent.analysis_type,
            qa_responses["general"],
        )
