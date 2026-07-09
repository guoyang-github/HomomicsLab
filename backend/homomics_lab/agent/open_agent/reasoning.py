"""Reasoning engine for the Open Agent Planner.

Generates a reasoning trace and an abstract phase plan based on retrieved
capabilities. Uses structured LLM output to keep parsing deterministic.
"""

import json
from typing import Any, List, Optional

from pydantic import ValidationError

from homomics_lab.agent.intent import UserIntent
from homomics_lab.agent.open_agent.models import (
    OpenAgentPhase,
    OpenAgentPlan,
    OpenAgentStepType,
    ReasoningStep,
    SkillCallIntent,
    ToolCallIntent,
)
from homomics_lab.agent.plan.models import DataState
from homomics_lab.llm_client import LLMClient
from homomics_lab.skills.models import SkillDefinition
from homomics_lab.tools.models import ToolDefinition


class ReasoningEngine:
    """Generate an open agent plan from intent and capabilities."""

    DEFAULT_MAX_TOKENS = 2500

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client

    async def plan_steps(
        self,
        intent: UserIntent,
        capabilities: List[Any],
        data_state: Optional[DataState] = None,
    ) -> OpenAgentPlan:
        """Generate an abstract open agent plan.

        Args:
            intent: The analyzed user intent.
            capabilities: Retrieved CapabilityCandidate objects.
            data_state: Optional current data state.

        Returns:
            An OpenAgentPlan with reasoning trace and abstract phases.
        """
        if self.llm_client is None or not self.llm_client.is_configured():
            return self._offline_plan(intent, capabilities)

        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(intent, capabilities, data_state)

        try:
            raw = await self.llm_client.chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=self.DEFAULT_MAX_TOKENS,
                response_format={"type": "json_object"},
            )
            parsed = json.loads(raw)
            plan = OpenAgentPlan.model_validate(parsed)
            # Ensure source capabilities are recorded.
            plan.source_capabilities = [c.id for c in capabilities]
            return plan
        except (json.JSONDecodeError, ValidationError) as exc:
            # Structured output failed: fall back to a conservative offline plan.
            return self._offline_plan(intent, capabilities, reason=str(exc))
        except Exception as exc:
            return self._offline_plan(intent, capabilities, reason=str(exc))

    @staticmethod
    def _build_system_prompt() -> str:
        return """You are HomomicsLab Open Agent, a scientific assistant for bioinformatics and computational biology.

Your job is to plan how to fulfill the user's request using ONLY the capabilities listed below. You must NOT invent tools, skills, databases, or functions that are not in the provided list.

For each plan you produce:
1. Write a short reasoning trace (2-5 steps) explaining your thinking.
2. Break the work into abstract phases. Valid step types are:
   - explore: retrieve external information using one or more tools
   - reason: internal analysis/diagnosis based on gathered information
   - code_act: generate and run code to process data or combine tools
   - execute_skill: run a registered skill
   - verify: check that an intermediate output meets expectations
   - summarize: produce the final answer
3. For each phase, list intended tool calls and/or skill calls from the provided list, with reasons.
4. Estimate risk level (low/medium/high). Use "high" if the plan involves writing files, executing shell commands, or running untrusted skills.
5. Set needs_hitl=true if user approval should be required before execution.

Output a single JSON object matching this schema (no markdown fences):
{
  "goal": "concise restatement of the user's request",
  "reasoning_trace": [
    {"thought": "...", "action": "...", "observation": "..."}
  ],
  "phases": [
    {
      "step_type": "explore",
      "description": "...",
      "required": true,
      "tool_intents": [{"tool_name": "registered_tool_name", "inputs": {}, "reason": "..."}],
      "skill_intents": [{"skill_id": "registered_skill_id", "inputs": {}, "reason": "..."}],
      "code_task": null,
      "code_language": "python",
      "success_criteria": ["..."],
      "estimated_duration_seconds": 60,
      "estimated_cost_usd": 0.01
    }
  ],
  "risk_level": "medium",
  "needs_hitl": false,
  "final_summary": "one-sentence summary of the planned approach"
}
"""

    @staticmethod
    def _build_user_prompt(
        intent: UserIntent,
        capabilities: List[Any],
        data_state: Optional[DataState],
    ) -> str:
        tools: List[ToolDefinition] = []
        skills: List[SkillDefinition] = []
        for c in capabilities:
            if c.type.value == "tool":
                tool = c.payload.get("tool")
                if tool is not None:
                    tools.append(tool)
            elif c.type.value == "skill":
                skill = c.payload.get("skill")
                if skill is not None:
                    skills.append(skill)

        tool_lines = []
        for t in tools:
            tool_lines.append(
                f"- tool '{t.name}': {t.description} (risk: {getattr(t, 'risk_level', 'low')})"
            )

        skill_lines = []
        for s in skills:
            skill_lines.append(
                f"- skill '{s.id}': {s.description} (category: {s.category})"
            )

        data_state_text = data_state.to_context() if data_state else "unknown"

        parts = [
            f"User request: {intent.original_message or intent.analysis_type}",
            f"Analysis type: {intent.analysis_type}",
            f"Target: {intent.target or 'none'}",
            f"Domain: {intent.domain or 'none'}",
            f"Data state: {data_state_text}",
            "",
            "Available tools:",
            *(tool_lines if tool_lines else ["(none)"]),
            "",
            "Available skills:",
            *(skill_lines if skill_lines else ["(none)"]),
            "",
            "Generate the JSON plan now. Prefer fewer phases when possible.",
        ]
        return "\n".join(parts)

    @staticmethod
    def _offline_plan(
        intent: UserIntent,
        capabilities: List[Any],
        reason: Optional[str] = None,
    ) -> OpenAgentPlan:
        """Fallback plan when LLM is unavailable.

        Produces a minimal explore + summarize plan using the top tool or skill.
        """
        top_tool: Optional[ToolDefinition] = None
        top_skill: Optional[SkillDefinition] = None
        for c in capabilities:
            if c.type.value == "tool" and top_tool is None:
                top_tool = c.payload.get("tool")
            elif c.type.value == "skill" and top_skill is None:
                top_skill = c.payload.get("skill")

        phases: List[OpenAgentPhase] = []
        if top_tool is not None:
            phases.append(
                OpenAgentPhase(
                    step_type=OpenAgentStepType.EXPLORE,
                    description=f"Use tool '{top_tool.name}' to gather information",
                    tool_intents=[
                        ToolCallIntent(
                            tool_name=top_tool.name,
                            reason="Best available tool for the request",
                        )
                    ],
                )
            )
        elif top_skill is not None:
            phases.append(
                OpenAgentPhase(
                    step_type=OpenAgentStepType.EXECUTE_SKILL,
                    description=f"Execute skill '{top_skill.id}'",
                    skill_intents=[
                        SkillCallIntent(
                            skill_id=top_skill.id,
                            reason="Best available skill for the request",
                        )
                    ],
                )
            )

        phases.append(
            OpenAgentPhase(
                step_type=OpenAgentStepType.SUMMARIZE,
                description="Summarize findings and respond to the user",
            )
        )

        trace = [
            ReasoningStep(
                thought="LLM unavailable or plan parsing failed; falling back to conservative plan.",
                observation=reason,
            )
        ]
        return OpenAgentPlan(
            goal=intent.original_message or intent.analysis_type,
            reasoning_trace=trace,
            phases=phases,
            source_capabilities=[c.id for c in capabilities],
            risk_level="medium",
            needs_hitl=False,
            final_summary="Conservative plan generated because LLM planner is unavailable.",
        )
