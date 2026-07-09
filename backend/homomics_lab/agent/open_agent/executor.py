"""Open Agent Executor.

Executes a PlanResult produced by OpenAgentPlanner. It walks the abstract
phases and dispatches each to the appropriate runtime:
  - explore -> AgentLoop with registered tools
  - reason/code_act -> CodeAct / LLM direct call
  - execute_skill -> SkillRuntimeExecutor
  - verify/summarize -> LLM direct call
"""

import json
import logging
from typing import Any, Dict, List, Optional

from homomics_lab.agent.agent_loop import AgentLoop, TurnBudget
from homomics_lab.agent.open_agent.code_generation import CodeActPlanner
from homomics_lab.agent.open_agent.models import (
    OpenAgentBudget,
    OpenAgentStepType,
)
from homomics_lab.agent.open_agent.termination import TerminationPolicy, TerminationState
from dataclasses import dataclass, field

from homomics_lab.agent.plan.models import Phase, PlanResult
from homomics_lab.context.working_memory import WorkingMemory
from homomics_lab.execution.code_act import run_code_act
from homomics_lab.llm_client import LLMClient
from homomics_lab.models.common import ChatMessage, MessageType, Option
from homomics_lab.observability.trace_store import TraceStore
from homomics_lab.skills.registry import SkillRegistry, get_default_registry
from homomics_lab.skills.runtime import SkillRuntimeExecutor
from homomics_lab.tools.registry import ToolRegistry, get_default_tool_registry

logger = logging.getLogger(__name__)


@dataclass
class OpenAgentExecutionResult:
    """Result of executing an open agent plan."""

    mode: str
    response_text: str
    agent_message: ChatMessage
    hitl_checkpoint: Optional[Any] = None
    trace_id: Optional[str] = None
    phase_outputs: List[Dict[str, Any]] = field(default_factory=list)


class OpenAgentExecutor:
    """Execute open agent plans."""

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        tool_registry: Optional[ToolRegistry] = None,
        skill_registry: Optional[SkillRegistry] = None,
        skill_executor: Optional[SkillRuntimeExecutor] = None,
        code_act_planner: Optional[CodeActPlanner] = None,
        trace_store: Optional[TraceStore] = None,
        budget: Optional[OpenAgentBudget] = None,
    ):
        self.llm_client = llm_client
        self.tool_registry = tool_registry or get_default_tool_registry()
        self.skill_registry = skill_registry or get_default_registry()
        self.skill_executor = skill_executor
        self.code_act_planner = code_act_planner or CodeActPlanner(
            llm_client=llm_client,
            skill_registry=self.skill_registry,
            tool_registry=self.tool_registry,
        )
        self.trace_store = trace_store
        self.budget = budget or OpenAgentBudget()
        self.termination = TerminationPolicy(budget=self.budget)

    async def execute(
        self,
        plan_result: PlanResult,
        user_message: str,
        working_memory: WorkingMemory,
        context: Optional[Dict[str, Any]] = None,
    ) -> OpenAgentExecutionResult:
        """Execute an open agent plan and return a TurnResult.

        Args:
            plan_result: The plan produced by OpenAgentPlanner.
            user_message: The original user message.
            working_memory: Current conversation memory.
            context: Execution context (project_id, project_path, etc.).

        Returns:
            TurnResult with response text, trace, and optional HITL checkpoint.
        """
        context = context or {}
        state = TerminationState()
        trace_id: Optional[str] = None
        if self.trace_store is not None:
            trace = await self.trace_store.start_trace(
                trace_id=context.get("trace_id"),
                session_id=context.get("session_id"),
                project_id=context.get("project_id"),
                root_name="open_agent_execution",
            )
            trace_id = trace.trace_id

        phase_outputs: List[Dict[str, Any]] = []
        final_text = ""
        hitl_reason: Optional[str] = None

        for phase in plan_result.phases:
            step_type_str = phase.parameters.get("open_agent_step_type", phase.phase_type)
            try:
                step_type = OpenAgentStepType(step_type_str)
            except ValueError:
                step_type = OpenAgentStepType.SUMMARIZE

            decision = self.termination.check(state, current_phase_step_type=step_type)
            if decision["should_stop"]:
                final_text = f"执行已停止：{decision['reason']}"
                if decision["needs_hitl"]:
                    hitl_reason = decision["hitl_reason"]
                break

            if trace_id is not None:
                await self.trace_store.add_node(
                    trace_id=trace_id,
                    node_type="phase",
                    name=f"{step_type.value}: {phase.description}",
                    parent_id="root",
                    inputs={"parameters": phase.parameters},
                )

            try:
                output = await self._execute_phase(
                    phase=phase,
                    step_type=step_type,
                    user_message=user_message,
                    working_memory=working_memory,
                    context=context,
                    state=state,
                    trace_id=trace_id,
                )
                phase_outputs.append({"phase": phase.phase_type, "output": output})
                if isinstance(output, str):
                    final_text = output
            except Exception as exc:
                logger.warning("Open agent phase failed: %s", exc, exc_info=True)
                state.errors.append(str(exc))
                phase_outputs.append({"phase": phase.phase_type, "error": str(exc)})

            # After potentially costly operations, re-check budget.
            decision = self.termination.check(state)
            if decision["should_stop"]:
                final_text = f"执行已停止：{decision['reason']}"
                if decision["needs_hitl"]:
                    hitl_reason = decision["hitl_reason"]
                break

        if not final_text:
            final_text = self._compose_summary(user_message, phase_outputs)

        agent_msg = ChatMessage(
            id=f"msg_{len(working_memory.messages)}",
            type=MessageType.TEXT,
            content=final_text,
            sender="agent",
        )
        working_memory.add_message(agent_msg)

        if hitl_reason is not None:
            # Build HITL checkpoint.
            from homomics_lab.models.common import HITLCheckpoint, HITLTrigger

            checkpoint = HITLCheckpoint(
                task_id=context.get("task_id", "open_agent"),
                trigger_reason=HITLTrigger.HIGH_RISK,
                context_summary=hitl_reason,
                options=[
                    Option(id="approve", label="继续执行", description="Approve and continue"),
                    Option(id="replan", label="重新规划", description="Replan the task"),
                    Option(id="cancel", label="取消", description="Cancel the task"),
                ],
            )
            return OpenAgentExecutionResult(
                mode="awaiting_hitl",
                response_text=final_text,
                agent_message=agent_msg,
                hitl_checkpoint=checkpoint,
                trace_id=trace_id,
                phase_outputs=phase_outputs,
            )

        return OpenAgentExecutionResult(
            mode="direct_response",
            response_text=final_text,
            agent_message=agent_msg,
            trace_id=trace_id,
            phase_outputs=phase_outputs,
        )

    async def _execute_phase(
        self,
        phase: Phase,
        step_type: OpenAgentStepType,
        user_message: str,
        working_memory: WorkingMemory,
        context: Dict[str, Any],
        state: TerminationState,
        trace_id: Optional[str],
    ) -> Any:
        """Dispatch a single open agent phase."""
        if step_type == OpenAgentStepType.EXPLORE:
            return await self._execute_explore(
                phase, user_message, working_memory, context, state, trace_id
            )
        if step_type == OpenAgentStepType.REASON:
            return await self._execute_reason(phase, user_message, context, state, trace_id)
        if step_type == OpenAgentStepType.CODE_ACT:
            state.code_executions += 1
            return await self._execute_code_act(phase, context, trace_id)
        if step_type == OpenAgentStepType.EXECUTE_SKILL:
            return await self._execute_skill(phase, context, state, trace_id)
        if step_type == OpenAgentStepType.VERIFY:
            return await self._execute_verify(phase, context, state, trace_id)
        if step_type == OpenAgentStepType.SUMMARIZE:
            return await self._execute_summarize(phase, user_message, context, state, trace_id)
        return f"Unknown step type: {step_type.value}"

    async def _execute_explore(
        self,
        phase: Phase,
        user_message: str,
        working_memory: WorkingMemory,
        context: Dict[str, Any],
        state: TerminationState,
        trace_id: Optional[str],
    ) -> str:
        """Run an explore phase using AgentLoop over allowed tools."""
        tool_intents = phase.parameters.get("tool_intents", [])
        allowed_tools = [ti["tool_name"] for ti in tool_intents if "tool_name" in ti]
        if not allowed_tools:
            allowed_tools = [t.name for t in self.tool_registry.list_all()]

        if self.llm_client is None or not self.llm_client.is_configured():
            return "当前未配置 LLM，无法执行探索性查询。"

        loop = AgentLoop(
            llm_client=self.llm_client,
            tool_registry=self.tool_registry,
            session_id=context.get("session_id"),
            project_id=context.get("project_id"),
            max_rounds=3,
            budget=TurnBudget(
                max_llm_calls=self.budget.max_llm_calls,
                max_tool_calls=self.budget.max_tool_calls,
            ),
            system_prompt=self._explore_system_prompt(),
        )
        history = self._working_memory_to_history(working_memory)
        result = await loop.run(
            user_message=user_message,
            history=history,
            allowed_tools=allowed_tools,
        )
        state.llm_calls += result.llm_calls
        state.tool_calls += result.tool_calls_count
        state.total_cost_usd += result.cost_usd

        if trace_id is not None:
            for record in result.tool_calls:
                await self.trace_store.add_node(
                    trace_id=trace_id,
                    node_type="tool",
                    name=record.tool_name,
                    parent_id="root",
                    inputs=record.inputs,
                    outputs={"success": record.success, "summary": record.output_summary},
                )

        return result.response_text

    async def _execute_reason(
        self,
        phase: Phase,
        user_message: str,
        context: Dict[str, Any],
        state: TerminationState,
        trace_id: Optional[str],
    ) -> str:
        """Run a reason phase via direct LLM call."""
        if self.llm_client is None or not self.llm_client.is_configured():
            return "当前未配置 LLM，无法执行推理步骤。"

        state.llm_calls += 1
        prompt = (
            f"User request: {user_message}\n\n"
            f"Reasoning task: {phase.description}\n\n"
            "Provide a concise, evidence-based reasoning summary. "
            "If you lack information, state that clearly."
        )
        return await self.llm_client.chat_completion(
            messages=[
                {"role": "system", "content": self._reason_system_prompt()},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=1500,
        )

    async def _execute_code_act(
        self,
        phase: Phase,
        context: Dict[str, Any],
        trace_id: Optional[str],
    ) -> str:
        """Run a code_act phase."""
        code_task = phase.parameters.get("code_task") or phase.description
        language = phase.parameters.get("code_language", "python")
        result = await run_code_act(
            task=code_task,
            language=language,
            context=context.get("inputs", {}),
            working_dir=context.get("project_path"),
            llm_client=self.llm_client,
            skill_registry=self.skill_registry,
            tool_registry=self.tool_registry,
        )
        if trace_id is not None:
            await self.trace_store.add_node(
                trace_id=trace_id,
                node_type="code_act",
                name="code_act",
                parent_id="root",
                inputs={"task": code_task, "language": language},
                outputs={
                    "success": result.get("success"),
                    "exit_code": result.get("exit_code"),
                    "stderr": result.get("stderr"),
                },
            )
        if result.get("success"):
            return result.get("result") or "代码执行成功。"
        return f"代码执行失败：{result.get('stderr', result.get('error', 'unknown error'))}"

    async def _execute_skill(
        self,
        phase: Phase,
        context: Dict[str, Any],
        state: TerminationState,
        trace_id: Optional[str],
    ) -> str:
        """Run an execute_skill phase."""
        skill_intents = phase.parameters.get("skill_intents", [])
        if not skill_intents:
            return "未指定要执行的 skill。"

        skill_id = skill_intents[0]["skill_id"]
        inputs = skill_intents[0].get("inputs", {})

        executor = self.skill_executor
        if executor is None:
            from homomics_lab.bootstrap import get_skill_executor

            executor = get_skill_executor()

        result = await executor.execute(skill_id, inputs)
        if trace_id is not None:
            await self.trace_store.add_node(
                trace_id=trace_id,
                node_type="skill",
                name=skill_id,
                parent_id="root",
                inputs=inputs,
                outputs={"success": result.get("success", True)},
            )
        return json.dumps(result, ensure_ascii=False, default=str)[:2000]

    async def _execute_verify(
        self,
        phase: Phase,
        context: Dict[str, Any],
        state: TerminationState,
        trace_id: Optional[str],
    ) -> str:
        """Run a verify phase."""
        criteria = phase.parameters.get("success_criteria", [])
        if not criteria:
            return "无明确校验标准。"
        return f"校验标准：{'; '.join(criteria)}。请人工确认输出是否满足。"

    async def _execute_summarize(
        self,
        phase: Phase,
        user_message: str,
        context: Dict[str, Any],
        state: TerminationState,
        trace_id: Optional[str],
    ) -> str:
        """Run a summarize phase."""
        if self.llm_client is None or not self.llm_client.is_configured():
            return "当前未配置 LLM，无法生成最终总结。"

        state.llm_calls += 1
        prompt = (
            f"User request: {user_message}\n\n"
            f"Task: {phase.description}\n\n"
            "Provide a concise final answer. Cite sources when available. "
            "If anything is uncertain, say so."
        )
        return await self.llm_client.chat_completion(
            messages=[
                {"role": "system", "content": self._summarize_system_prompt()},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=2000,
        )

    @staticmethod
    def _working_memory_to_history(working_memory: WorkingMemory) -> List[Dict[str, str]]:
        """Convert recent working memory messages to OpenAI chat history."""
        history: List[Dict[str, str]] = []
        for msg in working_memory.get_recent_messages(6):
            if msg.sender == "user":
                history.append({"role": "user", "content": str(msg.content)})
            elif msg.sender == "agent":
                history.append({"role": "assistant", "content": str(msg.content)})
        return history

    @staticmethod
    def _explore_system_prompt() -> str:
        return (
            "You are HomomicsLab Open Agent in explore mode. "
            "Use the available tools to gather accurate, up-to-date information. "
            "Do not invent facts. Summarize tool outputs clearly and cite the source tool."
        )

    @staticmethod
    def _reason_system_prompt() -> str:
        return (
            "You are HomomicsLab Open Agent in reasoning mode. "
            "Analyze the user's request carefully. State assumptions, caveats, and uncertainty. "
            "Do not propose actions that require tools unless they are clearly justified."
        )

    @staticmethod
    def _summarize_system_prompt() -> str:
        return (
            "You are HomomicsLab Open Agent. Provide a clear, concise final answer. "
            "Mention tool/skill sources when relevant. Be explicit about uncertainty."
        )

    @staticmethod
    def _compose_summary(user_message: str, phase_outputs: List[Dict[str, Any]]) -> str:
        """Compose a fallback summary when no explicit summarize phase ran."""
        lines = ["已按以下步骤处理您的请求："]
        for po in phase_outputs:
            phase = po.get("phase", "unknown")
            output = po.get("output")
            error = po.get("error")
            if error:
                lines.append(f"- {phase}：失败（{error}）")
            elif isinstance(output, str):
                summary = output[:200].replace("\n", " ")
                lines.append(f"- {phase}：{summary}")
            else:
                lines.append(f"- {phase}：完成")
        return "\n".join(lines)
