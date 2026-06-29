"""LLM-driven ReAct-style tool-calling loop for the chat agent.

This module implements the core "agent loop": the model decides whether to call
one or more registered tools, the tools are executed, and the results are fed
back to the model until a final answer is produced or a budget is exhausted.

It is intentionally decoupled from ``TurnRunner`` so it can be tested in
isolation.
"""

from __future__ import annotations

import inspect
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional, Union

from homomics_lab.models.common import ChatMessage, MessageType
from homomics_lab.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


@dataclass
class ToolCallRecord:
    """A single tool call that was made during an agent loop."""

    tool_call_id: str
    tool_name: str
    inputs: Dict[str, Any]
    success: bool
    output_summary: str
    raw_output: Any = None


@dataclass
class AgentLoopResult:
    """Result of running the agent loop."""

    response_text: str
    tool_calls: List[ToolCallRecord] = field(default_factory=list)
    stopped_reason: Optional[str] = None
    cost_usd: float = 0.0
    llm_calls: int = 0
    tool_calls_count: int = 0


@dataclass
class TurnBudget:
    """Budget for a single agent loop invocation."""

    max_llm_calls: int = 5
    max_tool_calls: int = 10
    max_cost_usd: Optional[float] = None

    def check_llm_call(self, current: int) -> bool:
        return current < self.max_llm_calls

    def check_tool_call(self, current: int) -> bool:
        return current < self.max_tool_calls

    def check_cost(self, current_cost: float) -> bool:
        if self.max_cost_usd is None:
            return True
        return current_cost < self.max_cost_usd


class AgentLoop:
    """ReAct-style loop using native LLM tool calling."""

    def __init__(
        self,
        llm_client: Any,
        tool_registry: ToolRegistry,
        session_id: Optional[str] = None,
        project_id: Optional[str] = None,
        request_id: Optional[str] = None,
        max_rounds: int = 3,
        budget: Optional[TurnBudget] = None,
        progress_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        event_callback: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
        system_prompt: Optional[str] = None,
    ):
        self.llm_client = llm_client
        self.tool_registry = tool_registry
        self.session_id = session_id
        self.project_id = project_id
        self.request_id = request_id
        self.max_rounds = max(max_rounds, 1)
        self.budget = budget or TurnBudget()
        self.progress_callback = progress_callback
        self.event_callback = event_callback
        self.system_prompt = system_prompt or (
            "You are HomomicsLab, an AI assistant for bioinformatics and computational biology. "
            "You have access to tools such as PubMed/GEO/UniProt search. "
            "Use tools when they help answer the user's question, then summarize the results "
            "in a helpful, structured way. Prefer concise, actionable answers."
        )

    def _report(self, event: str, payload: Dict[str, Any]) -> None:
        if self.progress_callback is not None:
            try:
                self.progress_callback(event, payload)
            except Exception:
                logger.debug("Progress callback failed", exc_info=True)

    async def _emit(self, event: str, payload: Dict[str, Any]) -> None:
        """Emit an async event (e.g. to a WebSocket/SSE consumer)."""
        if self.event_callback is not None:
            try:
                await self.event_callback({"event": event, **payload})
            except Exception:
                logger.debug("Event callback failed", exc_info=True)

    async def run(
        self,
        user_message: str,
        history: List[Dict[str, Any]],
        allowed_tools: Optional[List[str]] = None,
    ) -> AgentLoopResult:
        """Run the agent loop and return the final response.

        Args:
            user_message: The current user utterance.
            history: Prior conversation messages as OpenAI-compatible dicts.
            allowed_tools: Optional subset of tool names the loop may use.
        """
        if self.tool_registry is None:
            return AgentLoopResult(
                response_text=user_message,
                stopped_reason="no_tool_registry",
            )

        tools = self.tool_registry.to_openai_tools(allowed_names=allowed_tools)
        if not tools:
            return AgentLoopResult(
                response_text=user_message,
                stopped_reason="no_tools",
            )

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt},
            *history,
            {"role": "user", "content": user_message},
        ]

        tool_records: List[ToolCallRecord] = []
        llm_calls = 0
        tool_calls_count = 0
        total_cost = 0.0

        for round_idx in range(self.max_rounds):
            if not self.budget.check_llm_call(llm_calls):
                return AgentLoopResult(
                    response_text=self._compose_budget_message(messages),
                    tool_calls=tool_records,
                    stopped_reason="llm_call_budget",
                    cost_usd=total_cost,
                    llm_calls=llm_calls,
                    tool_calls_count=tool_calls_count,
                )

            await self._emit("agent.thinking", {"round": round_idx + 1})
            self._report("thinking", {"round": round_idx + 1})
            try:
                message, usage = await self.llm_client.chat_completion_message(
                    messages=messages,
                    temperature=0.3,
                    max_tokens=2000,
                    tools=tools,
                    session_id=self.session_id,
                    project_id=self.project_id,
                    request_id=f"{self.request_id or 'agent'}_round{round_idx}",
                )
            except Exception as exc:
                logger.warning("AgentLoop LLM call failed: %s", exc, exc_info=True)
                return AgentLoopResult(
                    response_text=f"调用 LLM 时出错：{exc}",
                    tool_calls=tool_records,
                    stopped_reason="llm_error",
                    cost_usd=total_cost,
                    llm_calls=llm_calls,
                    tool_calls_count=tool_calls_count,
                )

            llm_calls += 1
            total_cost += usage.get("cost_usd", 0.0) or 0.0

            tool_calls = getattr(message, "tool_calls", None)
            if not tool_calls:
                content = (getattr(message, "content", None) or "").strip()
                return AgentLoopResult(
                    response_text=content,
                    tool_calls=tool_records,
                    stopped_reason="complete",
                    cost_usd=total_cost,
                    llm_calls=llm_calls,
                    tool_calls_count=tool_calls_count,
                )

            # Model requested tool calls. Add the assistant message first.
            assistant_message = self._message_to_dict(message)
            messages.append(assistant_message)

            # Execute each requested tool call.
            for tool_call in tool_calls:
                if not self.budget.check_tool_call(tool_calls_count):
                    messages.append(self._tool_result_message(tool_call.id, "工具调用次数已达上限，停止执行。"))
                    continue
                if not self.budget.check_cost(total_cost):
                    messages.append(self._tool_result_message(tool_call.id, "成本预算已达上限，停止执行。"))
                    continue

                tool_name = getattr(tool_call.function, "name", "")
                try:
                    inputs = json.loads(tool_call.function.arguments or "{}")
                except json.JSONDecodeError:
                    inputs = {}

                await self._emit(
                    "tool_call.start",
                    {"tool_name": tool_name, "inputs": inputs, "round": round_idx + 1},
                )
                self._report(
                    "tool_call",
                    {"tool_name": tool_name, "inputs": inputs, "round": round_idx + 1},
                )

                record = await self._execute_tool(tool_call.id, tool_name, inputs)
                tool_records.append(record)
                tool_calls_count += 1
                await self._emit(
                    "tool_call.complete",
                    {
                        "tool_name": tool_name,
                        "success": record.success,
                        "output_summary": record.output_summary,
                        "inputs": inputs,
                    },
                )
                messages.append(self._tool_result_message(tool_call.id, record.output_summary))

        # If we exit the loop without a final answer, ask the model one last time
        # without tools to produce a graceful summary.
        if not self.budget.check_llm_call(llm_calls):
            return AgentLoopResult(
                response_text=self._compose_budget_message(messages),
                tool_calls=tool_records,
                stopped_reason="llm_call_budget",
                cost_usd=total_cost,
                llm_calls=llm_calls,
                tool_calls_count=tool_calls_count,
            )

        try:
            final_message, usage = await self.llm_client.chat_completion_message(
                messages=messages,
                temperature=0.3,
                max_tokens=2000,
                session_id=self.session_id,
                project_id=self.project_id,
                request_id=f"{self.request_id or 'agent'}_final",
            )
            llm_calls += 1
            total_cost += usage.get("cost_usd", 0.0) or 0.0
            content = (getattr(final_message, "content", None) or "").strip()
        except Exception as exc:
            content = self._compose_budget_message(messages)
            logger.warning("AgentLoop final summarization failed: %s", exc, exc_info=True)

        return AgentLoopResult(
            response_text=content,
            tool_calls=tool_records,
            stopped_reason="max_rounds",
            cost_usd=total_cost,
            llm_calls=llm_calls,
            tool_calls_count=tool_calls_count,
        )

    async def _execute_tool(
        self, tool_call_id: str, tool_name: str, inputs: Dict[str, Any]
    ) -> ToolCallRecord:
        """Execute a single tool and return a summarized record."""
        tool = self.tool_registry.get(tool_name)
        if tool is None:
            return ToolCallRecord(
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                inputs=inputs,
                success=False,
                output_summary=f"工具 `{tool_name}` 未注册。",
            )

        # High-risk tools require explicit approval before execution.
        if tool.risk_level == "high":
            return ToolCallRecord(
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                inputs=inputs,
                success=False,
                output_summary=(
                    f"工具 `{tool_name}` 属于高风险操作（风险等级：high），"
                    "已暂停执行。请在确认后再授权运行。"
                ),
            )

        try:
            result = await self.tool_registry.invoke_async(tool_name, inputs)
        except Exception as exc:
            return ToolCallRecord(
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                inputs=inputs,
                success=False,
                output_summary=f"调用工具 `{tool_name}` 失败：{exc}",
            )

        if not result.success:
            return ToolCallRecord(
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                inputs=inputs,
                success=False,
                output_summary=f"工具 `{tool_name}` 返回错误：{result.error_message}",
            )

        summary = self._summarize_tool_output(tool_name, result.output)
        return ToolCallRecord(
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            inputs=inputs,
            success=True,
            output_summary=summary,
            raw_output=result.output,
        )

    def _summarize_tool_output(self, tool_name: str, output: Any) -> str:
        """Produce a compact, LLM-friendly summary of a tool result."""
        if not isinstance(output, dict):
            text = str(output)
            if len(text) > 800:
                text = text[:800] + "..."
            return text

        # For search tools, keep the count and top hits.
        count = output.get("count")
        if count is not None:
            count_str = f"{count} 条结果"
            articles = output.get("articles") or output.get("results") or []
            if articles:
                previews = []
                for item in articles[:3]:
                    if isinstance(item, dict):
                        title = item.get("title") or item.get("name") or str(item)
                        previews.append(f"- {title}")
                    else:
                        previews.append(f"- {item}")
                return f"{count_str}\n" + "\n".join(previews)
            return count_str

        # Generic dict: serialize and truncate.
        text = json.dumps(output, ensure_ascii=False)
        if len(text) > 800:
            text = text[:800] + "..."
        return text

    def _tool_result_message(self, tool_call_id: str, summary: str) -> Dict[str, Any]:
        return {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": summary,
        }

    def _message_to_dict(self, message: Any) -> Dict[str, Any]:
        """Convert an OpenAI assistant message to a serializable dict."""
        data: Dict[str, Any] = {"role": "assistant"}
        content = getattr(message, "content", None)
        if content:
            data["content"] = content
        tool_calls = getattr(message, "tool_calls", None)
        if tool_calls:
            data["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": getattr(tc, "type", "function"),
                    "function": {
                        "name": getattr(tc.function, "name", ""),
                        "arguments": getattr(tc.function, "arguments", ""),
                    },
                }
                for tc in tool_calls
            ]
        return data

    def _compose_budget_message(self, messages: List[Dict[str, Any]]) -> str:
        """Return a graceful message when a budget is exhausted."""
        return (
            "已使用较多步骤仍未完成，当前工具调用或成本预算已达上限。"
            "如果问题较复杂，请拆分成更具体的步骤再试。"
        )
