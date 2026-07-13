"""General scientific agent mode.

For requests that are not tied to a specific domain workflow (QA, writing
scripts, general data processing, open-ended exploration), the general agent
answers directly or invokes lightweight tools instead of generating a rigid
multi-step analysis plan. This keeps the system helpful for everyday scientific
questions while preserving the workflow path for domain-specific analyses.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from homomics_lab.agent.intent import UserIntent
from homomics_lab.agent.source_attribution import (
    ensure_source_section,
    extract_sources,
)
from homomics_lab.context.prompter import Prompter
from homomics_lab.context.working_memory import WorkingMemory
from homomics_lab.llm_client import LLMClient
from homomics_lab.models.common import ChatMessage, MessageType
from homomics_lab.skills.registry import SkillRegistry, get_default_registry
from homomics_lab.tools.registry import ToolRegistry, get_default_tool_registry

if TYPE_CHECKING:
    from homomics_lab.agent.turn_runner import TurnResult


class GeneralScientificAgent:
    """Answer general scientific questions and run lightweight tasks.

    The agent is intentionally simple: it uses the configured LLM with a
    general-scientific system prompt. For ``general_help`` it can generate code
    via CodeAct; for ``tool_call`` / ``explore`` it delegates to the tool
    registry. It never assembles a domain workflow plan.
    """

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        tool_registry: Optional[ToolRegistry] = None,
        skill_registry: Optional[SkillRegistry] = None,
        prompter: Optional[Prompter] = None,
    ):
        self.llm_client = llm_client
        self.tool_registry = tool_registry or get_default_tool_registry()
        self.skill_registry = skill_registry or get_default_registry()
        self.prompter = prompter or Prompter()

    async def answer(
        self,
        intent: UserIntent,
        working_memory: WorkingMemory,
        context: Optional[Dict[str, Any]] = None,
    ) -> TurnResult:
        """Generate a direct response for a general scientific request."""
        context = context or {}

        # Explore / tool_call intents delegate to the tool registry.
        structured = getattr(intent, "structured_intent", None)
        interaction_mode = getattr(structured, "interaction_mode", intent.interaction_mode)
        if interaction_mode == "explore":
            return await self._handle_tool_call(intent, working_memory, context)

        # General help / code requests can use CodeAct if available.
        if (
            intent.analysis_type == "general_help"
            or getattr(structured, "intent_type", None) == "general_help"
        ):
            return await self._handle_general_help(intent, working_memory, context)

        # Default: direct LLM answer.
        return await self._handle_direct_answer(intent, working_memory, context)

    async def _handle_direct_answer(
        self,
        intent: UserIntent,
        working_memory: WorkingMemory,
        context: Dict[str, Any],
    ) -> TurnResult:
        """Answer knowledge or information questions directly."""
        from homomics_lab.agent.turn_runner import ExecutionMode, TurnResult

        messages = self._build_messages(intent, working_memory, context)
        response_text = await self._call_llm(messages)

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

    async def _handle_general_help(
        self,
        intent: UserIntent,
        working_memory: WorkingMemory,
        context: Dict[str, Any],
    ) -> TurnResult:
        """Generate code or scripts for general help requests."""
        from homomics_lab.agent.turn_runner import ExecutionMode, TurnResult

        # If CodeAct is available, use it to produce runnable code.
        code_act_skill = self.skill_registry.get("core_code_act")
        if code_act_skill is not None and self.llm_client is not None:
            from homomics_lab.execution.code_act import run_code_act

            user_message = intent.original_message
            result = await run_code_act(
                task=user_message,
                language="python",
                context={},
                working_dir=context.get("project_path"),
                llm_client=self.llm_client,
                skill_registry=self.skill_registry,
                tool_registry=self.tool_registry,
            )
            if result.get("success"):
                response_text = (
                    f"已为您生成脚本/代码：\n```\n{result.get('code', '')}\n```\n"
                    f"执行结果：{result.get('result', 'OK')}"
                )
            else:
                response_text = (
                    "代码生成/执行遇到问题：\n"
                    f"{result.get('stderr', result.get('error', 'unknown error'))}"
                )
        else:
            messages = self._build_messages(intent, working_memory, context)
            response_text = await self._call_llm(messages)

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

    async def _handle_tool_call(
        self,
        intent: UserIntent,
        working_memory: WorkingMemory,
        context: Dict[str, Any],
    ) -> TurnResult:
        """Invoke an external tool for explore intents."""
        from homomics_lab.agent.turn_runner import ExecutionMode, TurnResult

        tool_name = None
        tool_inputs = {}
        structured = getattr(intent, "structured_intent", None)
        if structured is not None:
            tool_name = getattr(structured, "target", None)
            tool_inputs = getattr(structured, "entities", {}) or {}
        if not tool_name:
            tool_name = intent.target
        if not tool_name:
            return await self._handle_direct_answer(intent, working_memory, context)

        tool = self.tool_registry.get(tool_name)
        if tool is None:
            response_text = f"工具 '{tool_name}' 不可用。请确认工具名称或换一种方式提问。"
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

        result = await self.tool_registry.invoke_async(tool_name, tool_inputs)
        response_text = f"工具 {tool_name} 返回结果：\n{result.output}"
        sources = extract_sources([result.output])
        response_text = ensure_source_section(response_text, sources)
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

    def _build_messages(
        self,
        intent: UserIntent,
        working_memory: WorkingMemory,
        context: Dict[str, Any],
    ) -> List[Dict[str, str]]:
        """Build a message list for the LLM, including recent conversation."""
        system_prompt = self.prompter._system_prompt(
            domain=None,
            mode="general_scientific_agent",
        )
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": system_prompt},
        ]
        # Include the last few turns for context.
        for msg in working_memory.get_recent_messages(6):
            if msg.sender == "user":
                messages.append({"role": "user", "content": str(msg.content)})
            elif msg.sender == "agent":
                messages.append({"role": "assistant", "content": str(msg.content)})
        # Ensure the current request is the last user message.
        if not messages or messages[-1].get("role") != "user":
            messages.append(
                {"role": "user", "content": intent.original_message}
            )
        return messages

    async def _call_llm(self, messages: List[Dict[str, str]]) -> str:
        """Call the LLM and return the text response."""
        if self.llm_client is None or not self.llm_client.is_configured():
            original = messages[-1].get("content", "") if messages else ""
            return (
                f"当前未配置 LLM，无法直接回答「{original}」。"
                "请配置 LLM 后重试，或将问题转换为具体的分析任务。"
            )
        try:
            return await self.llm_client.chat_completion(
                messages=messages,
                temperature=0.3,
            )
        except Exception as exc:
            return f"回答生成失败：{exc}"
