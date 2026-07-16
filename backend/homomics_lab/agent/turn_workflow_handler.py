"""WorkflowHandler — executes multi-step task trees.

Extracted from ``turn_runner.TurnRunner`` as a pure code move (no logic
changes).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from homomics_lab.agent.errors import ExecutionError
from homomics_lab.models.common import ChatMessage, MessageType

if TYPE_CHECKING:
    from homomics_lab.agent.intent_analyzer import UserIntent
    from homomics_lab.agent.turn_runner import TurnResult, TurnRunner
    from homomics_lab.context.working_memory import WorkingMemory
    from homomics_lab.plan.models import Plan
    from homomics_lab.tasks.task_tree import TaskTree

logger = logging.getLogger(__name__)


class WorkflowHandler:
    """Run complex multi-step workflows through the orchestrator or Nextflow backend."""

    def __init__(self, runner: "TurnRunner"):
        self._runner = runner

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
        if self._runner._is_fallback_suggestion(tree):
            return self._runner._build_fallback_result(tree, working_memory)

        # Multi-step workflows may be offloaded to Nextflow when appropriate.
        if plan is not None and len(tree.tasks) > 1:
            service = self._runner._get_workflow_execution_service()
            if service is not None:
                try:
                    context = await self._runner._build_orchestrator_context(
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
                    return self._runner._build_workflow_result(
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

        orchestrator = self._runner._get_orchestrator()
        self._runner._attach_uploaded_files_to_tree(tree, user_message, project_id)
        context = await self._runner._build_orchestrator_context(
            project_id,
            intent=intent,
            user_message=user_message,
            working_memory=working_memory,
            execution_mode=getattr(tree, "execution_mode", None),
        )
        try:
            results = await orchestrator.run_tree(tree, context=context)
        except ExecutionError as exc:
            corrected = await self._runner._apply_self_correction(
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
        hitl_info = self._runner._extract_hitl(results)
        if hitl_info:
            return self._runner._build_hitl_result(tree, hitl_info, working_memory)

        await self._runner._record_execution_feedback(tree, results, project_id)

        response_text = f"已为您规划 {len(tree.tasks)} 个分析步骤。"

        # Collect rich artifact envelopes + a data-driven findings summary so the
        # chat renders tables/figures inline (not just file links) and explains
        # what the numbers mean with provenance.
        envelopes = self._runner._envelopes_from_results(results)
        summary_md = self._runner._summarize(
            envelopes, user_message or "", self._runner._single_skill_id(tree)
        )
        if summary_md:
            response_text = f"{response_text}\n\n{summary_md}"

        # Extract any plots produced during the workflow
        plot_messages = self._runner._extract_plot_messages(results, tree, working_memory)
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
