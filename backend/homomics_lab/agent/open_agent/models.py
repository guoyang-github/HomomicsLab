"""Data models for the Open Agent Planner.

All LLM-facing outputs are Pydantic-constrained to reduce hallucination and
make parsing deterministic.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from homomics_lab.skills.capability_index import CapabilityType


class OpenAgentStepType(str, Enum):
    """Abstract step types in an open agent plan."""

    EXPLORE = "explore"  # retrieve external information via tools
    REASON = "reason"  # internal reasoning / diagnosis
    CODE_ACT = "code_act"  # generate and execute code
    EXECUTE_SKILL = "execute_skill"  # run a registered skill
    VERIFY = "verify"  # validate intermediate outputs
    SUMMARIZE = "summarize"  # produce final answer


class ToolCallIntent(BaseModel):
    """A tool call intended by the open agent."""

    tool_name: str = Field(..., description="Name of a registered tool")
    inputs: Dict[str, Any] = Field(default_factory=dict)
    reason: str = Field(default="", description="Why this tool is needed")


class SkillCallIntent(BaseModel):
    """A skill call intended by the open agent."""

    skill_id: str = Field(..., description="ID of a registered skill")
    inputs: Dict[str, Any] = Field(default_factory=dict)
    reason: str = Field(default="", description="Why this skill is needed")


class OpenAgentPhase(BaseModel):
    """A single abstract phase in an open agent plan."""

    step_type: OpenAgentStepType
    description: str = Field(..., description="What this step does")
    required: bool = True
    tool_intents: List[ToolCallIntent] = Field(default_factory=list)
    skill_intents: List[SkillCallIntent] = Field(default_factory=list)
    code_task: Optional[str] = None
    code_language: str = "python"
    success_criteria: List[str] = Field(default_factory=list)
    estimated_duration_seconds: Optional[float] = None
    estimated_cost_usd: Optional[float] = None


class ReasoningStep(BaseModel):
    """A single step in the open agent's reasoning trace."""

    thought: str
    action: Optional[str] = None  # e.g. "call_tool:pubmed_search"
    observation: Optional[str] = None


class OpenAgentPlan(BaseModel):
    """Structured plan produced by the Open Agent reasoning engine."""

    goal: str
    reasoning_trace: List[ReasoningStep] = Field(default_factory=list)
    phases: List[OpenAgentPhase] = Field(default_factory=list)
    source_capabilities: List[str] = Field(default_factory=list)
    estimated_total_cost_usd: Optional[float] = None
    risk_level: str = "medium"  # low | medium | high
    needs_hitl: bool = False
    final_summary: Optional[str] = None


@dataclass
class CapabilityCandidate:
    """A capability retrieved for the open agent."""

    id: str
    type: CapabilityType
    name: str
    description: str
    category: str
    score: float
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OpenAgentBudget:
    """Budget for a single open agent run."""

    max_llm_calls: int = 8
    max_tool_calls: int = 12
    max_code_executions: int = 3
    max_cost_usd: Optional[float] = None
    max_total_duration_seconds: Optional[float] = 300.0

    def check_llm_call(self, current: int) -> bool:
        return current < self.max_llm_calls

    def check_tool_call(self, current: int) -> bool:
        return current < self.max_tool_calls

    def check_code_execution(self, current: int) -> bool:
        return current < self.max_code_executions

    def check_cost(self, current_cost: float) -> bool:
        if self.max_cost_usd is None:
            return True
        return current_cost < self.max_cost_usd
