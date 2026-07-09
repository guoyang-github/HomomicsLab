"""CodeAct planning for the Open Agent Executor.

Decides when to generate code and prepares the inputs for ``run_code_act``.
"""

from typing import Any, Dict, Optional

from homomics_lab.agent.open_agent.models import OpenAgentPhase
from homomics_lab.execution.code_act import run_code_act
from homomics_lab.llm_client import LLMClient
from homomics_lab.skills.registry import SkillRegistry
from homomics_lab.tools.registry import ToolRegistry


class CodeActPlanner:
    """Generate and execute code for an open agent phase."""

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        skill_registry: Optional[SkillRegistry] = None,
        tool_registry: Optional[ToolRegistry] = None,
    ):
        self.llm_client = llm_client
        self.skill_registry = skill_registry
        self.tool_registry = tool_registry

    async def execute_phase(
        self,
        phase: OpenAgentPhase,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute a code_act phase.

        Args:
            phase: The phase containing ``code_task`` and ``code_language``.
            context: Execution context including project_path, inputs, etc.

        Returns:
            Result dict from ``run_code_act``.
        """
        task = phase.code_task or phase.description
        language = phase.code_language or "python"
        working_dir = context.get("project_path")

        return await run_code_act(
            task=task,
            language=language,
            context=context.get("inputs", {}),
            working_dir=working_dir,
            llm_client=self.llm_client,
            skill_registry=self.skill_registry,
            tool_registry=self.tool_registry,
        )
