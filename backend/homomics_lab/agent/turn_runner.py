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
from typing import Any, Dict, List, Optional

from homomics_lab.agent.agent_registry import AgentRegistry, get_default_registry
from homomics_lab.agent.factory import create_default_agents
from homomics_lab.agent.intent_analyzer import IntentAnalyzer, UserIntent
from homomics_lab.agent.orchestrator import Orchestrator
from homomics_lab.agent.task_decomposer import TaskDecomposer
from homomics_lab.context.working_memory import WorkingMemory
from homomics_lab.models.common import ChatMessage, MessageType, TaskStatus
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
    ):
        self.mode = mode
        self.response_text = response_text
        self.task_tree = task_tree
        self.progress = progress
        self.hitl_task_id = hitl_task_id
        self.hitl_checkpoint = hitl_checkpoint
        self.error = error
        self.agent_message = agent_message


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
    ):
        self.intent_analyzer = intent_analyzer or IntentAnalyzer()
        self.task_decomposer = task_decomposer or TaskDecomposer()
        self._orchestrator = orchestrator
        self._registry = registry

    def _get_orchestrator(self) -> Orchestrator:
        """Lazy init orchestrator with registry."""
        if self._orchestrator is None:
            registry = self._registry or get_default_registry()
            if not registry.list_agents():
                create_default_agents()
            self._orchestrator = Orchestrator(registry=registry)
        return self._orchestrator

    async def run_turn(
        self,
        session_id: str,
        user_message: str,
        working_memory: WorkingMemory,
        project_id: str,
        task_tree: Optional[TaskTree] = None,
    ) -> TurnResult:
        """Execute one full turn: from user message to agent response.

        This is the unified entry point. All conversational flows go through here.
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
            # 2. Analyze intent
            intent = await self.intent_analyzer.analyze(user_message)

            # 3. Route based on intent complexity
            if intent.complexity == "direct_response":
                return await self._handle_direct_response(
                    intent, user_message, working_memory
                )

            # Decompose into task tree
            tree = await self.task_decomposer.decompose(
                intent, context={"project_id": project_id}
            )

            if intent.complexity == "single_step":
                return await self._handle_single_step(
                    tree, working_memory, project_id
                )

            # Complex workflow
            return await self._handle_workflow(
                tree, working_memory, project_id
            )

        except Exception as e:
            return self._build_error_result(str(e), working_memory)

    async def _handle_direct_response(
        self,
        intent: UserIntent,
        user_message: str,
        working_memory: WorkingMemory,
    ) -> TurnResult:
        """Handle QA-style questions that need no skill execution."""
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

    async def _handle_single_step(
        self,
        tree: TaskTree,
        working_memory: WorkingMemory,
        project_id: str,
    ) -> TurnResult:
        """Handle single-step tasks (e.g., file conversion)."""
        orchestrator = self._get_orchestrator()
        results = await orchestrator.run_tree(tree)

        # Check for HITL
        hitl_info = self._extract_hitl(results)
        if hitl_info:
            return self._build_hitl_result(tree, hitl_info, working_memory)

        response_text = f"已完成：{tree.tasks[0].description}"
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
        )

    async def _handle_workflow(
        self,
        tree: TaskTree,
        working_memory: WorkingMemory,
        project_id: str,
    ) -> TurnResult:
        """Handle complex multi-step workflows."""
        orchestrator = self._get_orchestrator()
        results = await orchestrator.run_tree(tree)

        # Check for HITL
        hitl_info = self._extract_hitl(results)
        if hitl_info:
            return self._build_hitl_result(tree, hitl_info, working_memory)

        response_text = f"已为您规划 {len(tree.tasks)} 个分析步骤。"
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
        )

    def _extract_hitl(self, results: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Scan execution results for HITL checkpoints."""
        for task_id, result in results.items():
            if isinstance(result, dict) and "hitl" in result:
                return {"checkpoint": result["hitl"], "task_id": task_id}
        return None

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
