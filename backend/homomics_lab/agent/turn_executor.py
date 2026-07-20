"""TurnExecutor — execution-orchestration collaborator for the turn pipeline.

Merges the former ``turn_workflow_handler``, ``turn_agent_loop`` and
``turn_approval_handler`` collaborators into one cognitively cohesive module:

- ``WorkflowHandler`` — executes task trees through the orchestrator /
  Nextflow backend: single-step trees, multi-step workflows, HITL resume,
  and pre-built tree dispatch (``execute_tree``).
- ``AgentLoopHandler`` — LLM-driven MCP tool-calling loop for a turn.
- ``ToolApprovalHandler`` — resume the agent loop after a tool approval
  decision.

No runner back-reference: services that are never reassigned after
``TurnRunner`` construction are constructor-injected, lazily-built services
(orchestrator, workflow execution service, LLM client) are injected as
provider callables, cross-collaborator helpers arrive as the injected
``TurnResponder`` / ``TurnState`` facades or plain callables, and per-turn
mutable state arrives via an explicit ``ctx`` dict with the keys
``session_id``, ``project_id``, ``request_id`` and ``event_callback``.
"""

from __future__ import annotations

import json
import logging
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Optional,
)

from homomics_lab.agent.agent_loop import AgentLoop, ToolCallRecord, TurnBudget
from homomics_lab.agent.errors import ExecutionError
from homomics_lab.models.common import (
    ChatMessage,
    HITLCheckpoint,
    HITLTrigger,
    MessageType,
    Option,
)

if TYPE_CHECKING:
    from homomics_lab.agent.intent_analyzer import UserIntent
    from homomics_lab.agent.orchestrator import Orchestrator
    from homomics_lab.agent.turn_feedback_recorder import FeedbackRecorder
    from homomics_lab.agent.turn_responder import TurnResponder
    from homomics_lab.agent.turn_runner import TurnResult
    from homomics_lab.agent.turn_state import TurnState
    from homomics_lab.context.working_memory import WorkingMemory
    from homomics_lab.llm_client import LLMClient
    from homomics_lab.plan.models import Plan
    from homomics_lab.tasks.task_tree import TaskTree
    from homomics_lab.tools.registry import ToolRegistry
    from homomics_lab.workflow.execution_service import WorkflowExecutionService

logger = logging.getLogger(__name__)


class WorkflowHandler:
    """Run task trees through the orchestrator or the Nextflow backend.

    Owns every orchestrator-driven execution path: single-step trees,
    complex multi-step workflows, HITL resume, and the pre-built tree
    dispatch (``execute_tree``) used by the background worker.
    """

    def __init__(
        self,
        *,
        orchestrator_provider: Callable[[], "Orchestrator"],
        workflow_service_provider: Callable[[], Optional["WorkflowExecutionService"]],
        orchestrator_context_builder: Callable[..., Awaitable[Dict[str, Any]]],
        self_correction: Callable[..., Awaitable[Optional["TurnResult"]]],
        is_fallback_suggestion: Callable[["TaskTree"], bool],
        responder: "TurnResponder",
        state: "TurnState",
        feedback_recorder: "FeedbackRecorder",
        memory_manager: Optional[Any] = None,
    ):
        self._orchestrator_provider = orchestrator_provider
        self._workflow_service_provider = workflow_service_provider
        self._orchestrator_context_builder = orchestrator_context_builder
        self._self_correction = self_correction
        self._is_fallback_suggestion = is_fallback_suggestion
        self._responder = responder
        self._state = state
        self._feedback_recorder = feedback_recorder
        self._memory_manager = memory_manager

    async def handle(
        self,
        tree: "TaskTree",
        working_memory: "WorkingMemory",
        project_id: str,
        intent: Optional["UserIntent"] = None,
        user_message: Optional[str] = None,
        plan: Optional["Plan"] = None,
    ) -> "TurnResult":
        """Handle complex multi-step workflows."""
        from homomics_lab.agent.turn_runner import ExecutionMode, TurnResult

        # Handle non-executable fallback suggestions directly.
        if self._is_fallback_suggestion(tree):
            return self._responder.build_fallback_result(tree, working_memory)

        # Multi-step workflows may be offloaded to Nextflow when appropriate.
        if plan is not None and len(tree.tasks) > 1:
            service = self._workflow_service_provider()
            if service is not None:
                try:
                    context = await self._orchestrator_context_builder(
                        project_id,
                        intent=intent,
                        user_message=user_message,
                        working_memory=working_memory,
                    )
                    wf_result = await service.execute(
                        plan=plan,
                        project_id=project_id,
                        context=context,
                    )
                    return self._responder.build_workflow_result(
                        tree=wf_result.task_tree,
                        working_memory=working_memory,
                        backend=wf_result.backend,
                        artifacts=wf_result.artifacts,
                        error=wf_result.error_message,
                        user_message=user_message or "",
                    )
                except Exception as exc:
                    logger.warning(
                        "WorkflowExecutionService failed; falling back to local orchestrator: %s",
                        exc,
                        exc_info=True,
                    )

        orchestrator = self._orchestrator_provider()
        self._state.attach_uploaded_files_to_tree(tree, user_message, project_id)
        context = await self._orchestrator_context_builder(
            project_id,
            intent=intent,
            user_message=user_message,
            working_memory=working_memory,
            execution_mode=getattr(tree, "execution_mode", None),
        )
        try:
            results = await orchestrator.run_tree(tree, context=context)
        except ExecutionError as exc:
            corrected = await self._self_correction(
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
        hitl_info = self._responder.extract_hitl(results)
        if hitl_info:
            return self._responder.build_hitl_result(tree, hitl_info, working_memory)

        await self._feedback_recorder.record_execution_feedback(tree, results, project_id)

        response_text = f"已为您规划 {len(tree.tasks)} 个分析步骤。"

        # Collect rich artifact envelopes + a data-driven findings summary so the
        # chat renders tables/figures inline (not just file links) and explains
        # what the numbers mean with provenance.
        envelopes = self._responder.envelopes_from_results(results)
        summary_md = self._responder.summarize(
            envelopes, user_message or "", self._responder.single_skill_id(tree)
        )
        if summary_md:
            response_text = f"{response_text}\n\n{summary_md}"

        # Extract any plots produced during the workflow
        plot_messages = self._responder.extract_plot_messages(results, tree, working_memory)
        for msg in plot_messages:
            working_memory.add_message(msg)

        agent_msg = ChatMessage(
            id=f"msg_{len(working_memory.messages)}",
            type=MessageType.TODO_LIST,
            content={
                "text": response_text,
                "tasks": [t.model_dump() for t in tree.tasks],
                "progress": orchestrator.get_progress(tree),
                "artifacts": envelopes,
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

    async def handle_single_step(
        self,
        tree: "TaskTree",
        working_memory: "WorkingMemory",
        project_id: str,
        intent: Optional["UserIntent"] = None,
        user_message: Optional[str] = None,
    ) -> "TurnResult":
        """Handle single-step tasks (e.g., file conversion)."""
        from homomics_lab.agent.turn_runner import ExecutionMode, TurnResult

        # Handle non-executable fallback suggestions directly.
        if self._is_fallback_suggestion(tree):
            return self._responder.build_fallback_result(tree, working_memory)

        orchestrator = self._orchestrator_provider()
        self._state.attach_uploaded_files_to_tree(tree, user_message, project_id)
        context = await self._orchestrator_context_builder(
            project_id,
            intent=intent,
            user_message=user_message,
            working_memory=working_memory,
            execution_mode=getattr(tree, "execution_mode", None),
        )
        try:
            results = await orchestrator.run_tree(tree, context=context)
        except ExecutionError as exc:
            corrected = await self._self_correction(
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
        hitl_info = self._responder.extract_hitl(results)
        if hitl_info:
            return self._responder.build_hitl_result(tree, hitl_info, working_memory)

        await self._feedback_recorder.record_execution_feedback(tree, results, project_id)

        response_text = f"已完成：{tree.tasks[0].description}"

        # Extract any plots produced by the skill
        plot_messages = self._responder.extract_plot_messages(results, tree, working_memory)
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

    async def resume_hitl(
        self,
        session_id: str,
        task_id: str,
        choice: str,
        parameters: Dict[str, Any],
        working_memory: "WorkingMemory",
        task_tree: "TaskTree",
        project_id: str = "default",
    ) -> "TurnResult":
        """Resume execution after receiving HITL response."""
        from homomics_lab.agent.turn_runner import ExecutionMode, TurnResult

        orchestrator = self._orchestrator_provider()

        result = await orchestrator.resume_task(
            task_tree,
            task_id,
            {"choice": choice, "parameters": parameters},
        )

        await self._feedback_recorder.record_execution_feedback(task_tree, result, project_id)

        response_text = f"已恢复任务 {task_id}，继续执行后续步骤。"

        # Extract any plots produced after resuming
        plot_messages = self._responder.extract_plot_messages(result, task_tree, working_memory)
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

    async def execute_tree(
        self,
        tree: "TaskTree",
        working_memory: "WorkingMemory",
        project_id: str,
        trace_id: Optional[str] = None,
        session_id: str = "",
        plan_id: Optional[str] = None,
    ) -> "TurnResult":
        """Execute a pre-built task tree.

        This is used by the background worker after a job has been enqueued.
        It skips intent analysis and decomposition. When ``plan_id`` is provided
        and the workflow execution service decides a Nextflow backend is
        appropriate, the whole plan is executed as a Nextflow workflow.
        """
        from homomics_lab.plan.store import PlanStore

        plan: Optional["Plan"] = None
        if plan_id is not None:
            plan = await PlanStore().get(plan_id)
            if plan is not None:
                tree = plan.task_tree

        if self._is_fallback_suggestion(tree):
            turn_result = self._responder.build_fallback_result(tree, working_memory)
        elif len(tree.tasks) == 1:
            turn_result = await self.handle_single_step(
                tree, working_memory, project_id
            )
        else:
            turn_result = await self.handle(
                tree, working_memory, project_id, plan=plan
            )

        # Persist turn to long-term memory (best-effort)
        if self._memory_manager is not None:
            try:
                # Derive a user_message placeholder from the tree for memory summary
                user_message = (
                    tree.tasks[0].description if tree.tasks else "background execution"
                )
                await self._memory_manager.persist_turn(
                    session_id=session_id,
                    project_id=project_id,
                    user_message=user_message,
                    turn_result=turn_result,
                    working_memory=working_memory,
                    task_tree=turn_result.task_tree,
                )
            except Exception:
                logger.warning(
                    "Failed to persist background execution to memory", exc_info=True
                )

        return turn_result


class AgentLoopHandler:
    """Run the LLM-driven tool-calling loop and its approval/follow-up flow."""

    def __init__(
        self,
        *,
        llm_client_provider: Callable[[], Optional["LLMClient"]],
        tool_registry: Optional["ToolRegistry"],
        permission_registry: Any,
        state: "TurnState",
        approval_handler: "ToolApprovalHandler",
    ):
        self._llm_client_provider = llm_client_provider
        self._tool_registry = tool_registry
        self._permission_registry = permission_registry
        self._state = state
        self._approval_handler = approval_handler

    async def handle(
        self,
        user_message: str,
        working_memory: "WorkingMemory",
        allowed_tools: Optional[List[str]] = None,
        intent: Optional["UserIntent"] = None,
        ctx: Optional[Dict[str, Any]] = None,
    ) -> "TurnResult":
        """Run the LLM-driven tool-calling loop for MCP tool intents."""
        from homomics_lab.agent.turn_runner import ExecutionMode, TurnResult

        ctx = ctx or {}
        llm_client = self._llm_client_provider()
        if llm_client is None or self._tool_registry is None:
            raise RuntimeError("AgentLoop requires both llm_client and tool_registry")

        history = self._state.working_memory_to_history(working_memory)
        loop = AgentLoop(
            llm_client=llm_client,
            tool_registry=self._tool_registry,
            session_id=ctx.get("session_id"),
            project_id=ctx.get("project_id"),
            request_id=ctx.get("request_id"),
            max_rounds=3,
            budget=TurnBudget(max_llm_calls=5, max_tool_calls=10),
            event_callback=ctx.get("event_callback"),
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
                return await self._approval_handler.respond(
                    call_id=result.approval_request["call_id"],
                    approved=True,
                    working_memory=working_memory,
                    project_id=ctx.get("project_id") or "default",
                    ctx=ctx,
                )
            return await self.create_tool_approval_hitl(
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
        suggestions = await self.generate_followup_suggestions(
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

    async def generate_followup_suggestions(
        self,
        user_message: str,
        response_text: str,
        max_suggestions: int = 3,
    ) -> List[str]:
        """Generate concise follow-up question suggestions using the LLM."""
        llm_client = self._llm_client_provider()
        if (
            llm_client is None
            or not getattr(llm_client, "is_configured", lambda: False)()
        ):
            return []

        prompt = (
            f"User question: {user_message}\n"
            f"Agent answer: {response_text}\n\n"
            f"Generate up to {max_suggestions} concise follow-up questions the user might ask next. "
            "Respond with a JSON array of strings only, no markdown."
        )
        try:
            raw = await llm_client.chat_completion(
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

    async def create_tool_approval_hitl(
        self,
        loop_result: Any,
        working_memory: "WorkingMemory",
        user_message: str,
    ) -> "TurnResult":
        """Create a HITL request when the agent loop pauses for tool approval."""
        from homomics_lab.agent.turn_runner import ExecutionMode, TurnResult

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


class ToolApprovalHandler:
    """Resume an agent loop after a high-risk tool approval decision."""

    def __init__(
        self,
        *,
        approval_store: Optional[Any],
        tool_registry: Optional["ToolRegistry"],
        llm_client_provider: Callable[[], Optional["LLMClient"]],
    ):
        self._approval_store = approval_store
        self._tool_registry = tool_registry
        self._llm_client_provider = llm_client_provider

    async def respond(
        self,
        call_id: str,
        approved: bool,
        working_memory: "WorkingMemory",
        project_id: str,
        ctx: Optional[Dict[str, Any]] = None,
    ) -> "TurnResult":
        """Resume an agent loop after a high-risk tool approval decision."""
        from homomics_lab.tools.approval_store import PersistentApprovalStore
        from homomics_lab.agent.turn_runner import ExecutionMode, TurnResult

        ctx = ctx or {}
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
            tool_result = await self._tool_registry.invoke_async(
                tool_name, tool_inputs
            )
            summary = AgentLoop(
                llm_client=self._llm_client_provider(),
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
        llm_client = self._llm_client_provider()
        if (
            llm_client is not None
            and getattr(llm_client, "is_configured", lambda: False)()
        ):
            try:
                final_msg, _ = await llm_client.chat_completion_message(
                    messages=messages,
                    temperature=0.3,
                    max_tokens=2000,
                    session_id=ctx.get("session_id"),
                    project_id=ctx.get("project_id"),
                    request_id=f"{ctx.get('request_id') or 'agent'}_approval_resume",
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


class TurnExecutor:
    """Facade over the execution-orchestration collaborators of the turn pipeline.

    Groups :class:`WorkflowHandler`, :class:`AgentLoopHandler` and
    :class:`ToolApprovalHandler` behind a single entry point so ``TurnRunner``
    holds one executor collaborator instead of three.
    """

    def __init__(
        self,
        *,
        orchestrator_provider: Callable[[], "Orchestrator"],
        workflow_service_provider: Callable[[], Optional["WorkflowExecutionService"]],
        orchestrator_context_builder: Callable[..., Awaitable[Dict[str, Any]]],
        self_correction: Callable[..., Awaitable[Optional["TurnResult"]]],
        is_fallback_suggestion: Callable[["TaskTree"], bool],
        responder: "TurnResponder",
        state: "TurnState",
        feedback_recorder: "FeedbackRecorder",
        llm_client_provider: Callable[[], Optional["LLMClient"]],
        tool_registry: Optional["ToolRegistry"] = None,
        permission_registry: Optional[Any] = None,
        approval_store: Optional[Any] = None,
        memory_manager: Optional[Any] = None,
    ):
        self._workflow_handler = WorkflowHandler(
            orchestrator_provider=orchestrator_provider,
            workflow_service_provider=workflow_service_provider,
            orchestrator_context_builder=orchestrator_context_builder,
            self_correction=self_correction,
            is_fallback_suggestion=is_fallback_suggestion,
            responder=responder,
            state=state,
            feedback_recorder=feedback_recorder,
            memory_manager=memory_manager,
        )
        self._approval_handler = ToolApprovalHandler(
            approval_store=approval_store,
            tool_registry=tool_registry,
            llm_client_provider=llm_client_provider,
        )
        self._agent_loop_handler = AgentLoopHandler(
            llm_client_provider=llm_client_provider,
            tool_registry=tool_registry,
            permission_registry=permission_registry,
            state=state,
            approval_handler=self._approval_handler,
        )

    async def handle_workflow(
        self,
        tree: "TaskTree",
        working_memory: "WorkingMemory",
        project_id: str,
        intent: Optional["UserIntent"] = None,
        user_message: Optional[str] = None,
        plan: Optional["Plan"] = None,
    ) -> "TurnResult":
        return await self._workflow_handler.handle(
            tree=tree,
            working_memory=working_memory,
            project_id=project_id,
            intent=intent,
            user_message=user_message,
            plan=plan,
        )

    async def handle_single_step(
        self,
        tree: "TaskTree",
        working_memory: "WorkingMemory",
        project_id: str,
        intent: Optional["UserIntent"] = None,
        user_message: Optional[str] = None,
    ) -> "TurnResult":
        return await self._workflow_handler.handle_single_step(
            tree=tree,
            working_memory=working_memory,
            project_id=project_id,
            intent=intent,
            user_message=user_message,
        )

    async def resume_hitl(
        self,
        session_id: str,
        task_id: str,
        choice: str,
        parameters: Dict[str, Any],
        working_memory: "WorkingMemory",
        task_tree: "TaskTree",
        project_id: str = "default",
    ) -> "TurnResult":
        return await self._workflow_handler.resume_hitl(
            session_id=session_id,
            task_id=task_id,
            choice=choice,
            parameters=parameters,
            working_memory=working_memory,
            task_tree=task_tree,
            project_id=project_id,
        )

    async def execute_tree(
        self,
        tree: "TaskTree",
        working_memory: "WorkingMemory",
        project_id: str,
        trace_id: Optional[str] = None,
        session_id: str = "",
        plan_id: Optional[str] = None,
    ) -> "TurnResult":
        return await self._workflow_handler.execute_tree(
            tree=tree,
            working_memory=working_memory,
            project_id=project_id,
            trace_id=trace_id,
            session_id=session_id,
            plan_id=plan_id,
        )

    async def handle_agent_loop(
        self,
        user_message: str,
        working_memory: "WorkingMemory",
        allowed_tools: Optional[List[str]] = None,
        intent: Optional["UserIntent"] = None,
        ctx: Optional[Dict[str, Any]] = None,
    ) -> "TurnResult":
        return await self._agent_loop_handler.handle(
            user_message=user_message,
            working_memory=working_memory,
            allowed_tools=allowed_tools,
            intent=intent,
            ctx=ctx,
        )

    async def respond_to_tool_approval(
        self,
        call_id: str,
        approved: bool,
        working_memory: "WorkingMemory",
        project_id: str,
        ctx: Optional[Dict[str, Any]] = None,
    ) -> "TurnResult":
        return await self._approval_handler.respond(
            call_id=call_id,
            approved=approved,
            working_memory=working_memory,
            project_id=project_id,
            ctx=ctx,
        )
