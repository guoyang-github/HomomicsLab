"""ToolApprovalHandler — resume the agent loop after a tool approval decision.

Extracted from ``turn_runner.TurnRunner`` as a pure code move (no logic
changes). The handler holds a back-reference to the runner for per-turn
mutable state (``_session_id``, ``_project_id``, ``_turn_request_id``) and
shared services (``_approval_store``, ``_tool_registry``, ``_llm_client``).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homomics_lab.agent.agent_loop import ToolCallRecord
from homomics_lab.models.common import ChatMessage, MessageType

if TYPE_CHECKING:
    from homomics_lab.agent.turn_runner import TurnResult, TurnRunner
    from homomics_lab.context.working_memory import WorkingMemory

logger = logging.getLogger(__name__)


class ToolApprovalHandler:
    """Resume an agent loop after a high-risk tool approval decision."""

    def __init__(self, runner: "TurnRunner"):
        self._runner = runner

    async def respond(
        self,
        call_id: str,
        approved: bool,
        working_memory: "WorkingMemory",
        project_id: str,
    ) -> "TurnResult":
        """Resume an agent loop after a high-risk tool approval decision."""
        from homomics_lab.tools.approval_store import PersistentApprovalStore
        from homomics_lab.agent.agent_loop import AgentLoop
        from homomics_lab.agent.turn_runner import ExecutionMode, TurnResult

        runner = self._runner
        store = runner._approval_store or PersistentApprovalStore()
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

        if runner._tool_registry is None:
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
            tool_result = await runner._tool_registry.invoke_async(
                tool_name, tool_inputs
            )
            summary = AgentLoop(
                llm_client=runner._llm_client,
                tool_registry=runner._tool_registry,
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
            runner._llm_client is not None
            and getattr(runner._llm_client, "is_configured", lambda: False)()
        ):
            try:
                final_msg, _ = await runner._llm_client.chat_completion_message(
                    messages=messages,
                    temperature=0.3,
                    max_tokens=2000,
                    session_id=runner._session_id,
                    project_id=runner._project_id,
                    request_id=f"{runner._turn_request_id or 'agent'}_approval_resume",
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
