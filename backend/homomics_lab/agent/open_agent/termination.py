"""Termination policy for the Open Agent Executor.

Decides when an open agent run should stop and whether it should escalate to
HITL.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from homomics_lab.agent.open_agent.models import OpenAgentBudget, OpenAgentStepType


@dataclass
class TerminationState:
    """Mutable state tracked during open agent execution."""

    llm_calls: int = 0
    tool_calls: int = 0
    code_executions: int = 0
    total_cost_usd: float = 0.0
    errors: List[str] = field(default_factory=list)
    high_risk_actions: List[str] = field(default_factory=list)


class TerminationPolicy:
    """Decide termination and HITL escalation for open agent runs."""

    def __init__(self, budget: Optional[OpenAgentBudget] = None):
        self.budget = budget or OpenAgentBudget()

    def check(
        self,
        state: TerminationState,
        current_phase_step_type: Optional[OpenAgentStepType] = None,
    ) -> Dict[str, Any]:
        """Return termination decision.

        Returns a dict with:
          - should_stop: bool
          - reason: Optional[str]
          - needs_hitl: bool
          - hitl_reason: Optional[str]
        """
        if not self.budget.check_llm_call(state.llm_calls):
            return {
                "should_stop": True,
                "reason": "LLM call budget exhausted",
                "needs_hitl": False,
                "hitl_reason": None,
            }

        if not self.budget.check_tool_call(state.tool_calls):
            return {
                "should_stop": True,
                "reason": "Tool call budget exhausted",
                "needs_hitl": False,
                "hitl_reason": None,
            }

        if not self.budget.check_code_execution(state.code_executions):
            return {
                "should_stop": True,
                "reason": "Code execution budget exhausted",
                "needs_hitl": False,
                "hitl_reason": None,
            }

        if not self.budget.check_cost(state.total_cost_usd):
            return {
                "should_stop": True,
                "reason": "Cost budget exhausted",
                "needs_hitl": False,
                "hitl_reason": None,
            }

        if state.errors:
            # If multiple consecutive errors, escalate to HITL.
            if len(state.errors) >= 2:
                return {
                    "should_stop": True,
                    "reason": "Repeated execution errors",
                    "needs_hitl": True,
                    "hitl_reason": "Open agent encountered repeated errors: "
                    + "; ".join(state.errors[-3:]),
                }

        if state.high_risk_actions and current_phase_step_type == OpenAgentStepType.SUMMARIZE:
            return {
                "should_stop": False,
                "reason": None,
                "needs_hitl": True,
                "hitl_reason": "High-risk actions require approval before finalizing: "
                + "; ".join(state.high_risk_actions),
            }

        return {
            "should_stop": False,
            "reason": None,
            "needs_hitl": False,
            "hitl_reason": None,
        }
