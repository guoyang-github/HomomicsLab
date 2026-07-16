"""IntentRouter — routes analyzed intents to the appropriate execution path.

Extracted from ``turn_runner.TurnRunner`` as a pure code move (no logic
changes).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from homomics_lab.agent.approval_policy import resolve_strategy, should_require_approval
from homomics_lab.agent.subagents import SpecialistCriticOrchestrator
from homomics_lab.config import settings
from homomics_lab.context.project_state import ProjectStateManager
from homomics_lab.domain.registry import get_domain_registry
from homomics_lab.knowledge.cbkb import CBKB
from homomics_lab.jobs.constants import JobMode
from homomics_lab.metrics import record_plan_created
from homomics_lab.models.common import ChatMessage, MessageType
from homomics_lab.plan.models import Plan, PlanStatus
from homomics_lab.plan.presenter import PlanPresenter
from homomics_lab.plan.store import PlanStore, _new_plan_id

if TYPE_CHECKING:
    from homomics_lab.agent.intent_analyzer import UserIntent
    from homomics_lab.agent.turn_runner import TurnResult, TurnRunner
    from homomics_lab.context.working_memory import WorkingMemory
    from homomics_lab.tasks.task_tree import TaskTree

logger = logging.getLogger(__name__)

# Domain values used by the domain registry for real analysis workflows.
# Builtin intent definitions use placeholder domains such as "builtin" or
# "general"; those should not trigger the domain canvas / approval path.
REAL_DOMAIN_VALUES = {
    "single-cell-transcriptomics",
    "spatial-transcriptomics",
    "metagenomics",
    "genomics",
    "transcriptomics",
    "proteomics",
    "epigenomics",
}


class IntentRouter:
    """Route a structured user intent to clarify, answer, execute or queue."""

    def __init__(self, runner: "TurnRunner"):
        self._runner = runner

    async def route(
        self,
        intent: "UserIntent",
        user_message: str,
        working_memory: "WorkingMemory",
        project_id: str,
        session_id: str,
        plan_store: Optional[PlanStore],
        job_service: Optional[Any],
        enqueue_skills: bool,
        plan_mode: bool = False,
    ) -> "TurnResult":
        """Route a user intent to the right execution path.

        Uses the structured ``interaction_mode`` and ``scope`` fields when
        available, with backward-compatible fallbacks to ``analysis_type`` and
        ``complexity``.
        """
        from homomics_lab.agent.turn_runner import ExecutionMode, TurnResult

        interaction_mode = intent.interaction_mode
        scope = intent.scope

        # Backward compatibility for legacy intents that don't set the new fields.
        if not interaction_mode:
            if intent.analysis_type == "clarification":
                interaction_mode = "clarify"
            elif intent.interaction_mode == "answer" or intent.complexity == "direct_response":
                interaction_mode = "answer"

        if interaction_mode == "clarify":
            return self._runner._handle_clarification(intent, working_memory)

        if interaction_mode == "answer":
            return await self._runner._handle_direct_response(
                intent, user_message, working_memory, project_id
            )

        # Fast-path natural-language figure editing.
        if intent.analysis_type == "visualization_edit":
            from homomics_lab.agent.turn_viz_handler import VisualizationEditHandler

            handler = VisualizationEditHandler(self._runner)
            return await handler.handle(
                user_message=user_message,
                working_memory=working_memory,
                project_id=project_id,
                intent=intent,
            )

        # MCP tool agent loop.
        mcp_tool_name = intent.metadata.get("tool_name")
        if mcp_tool_name and self._runner._tool_registry is not None:
            try:
                return await self._runner._handle_agent_loop(
                    user_message=user_message,
                    working_memory=working_memory,
                    allowed_tools=[
                        t.name for t in self._runner._tool_registry.list_by_source("mcp")
                    ],
                    intent=intent,
                )
            except Exception as exc:
                logger.warning(
                    "AgentLoop failed, falling back to direct MCP tool: %s",
                    exc,
                    exc_info=True,
                )
                return await self._runner._handle_mcp_tool(
                    mcp_tool_name,
                    intent.metadata.get("tool_inputs", {}),
                    working_memory,
                )

        # Everything else is some form of execution.
        plan_context = {"project_id": project_id}
        plan_result, tree = await self._runner.task_decomposer.decompose_with_plan(
            intent, context=plan_context
        )

        # If the domain planner only produced a fallback (no concrete skill match),
        # let the open agent try before presenting an approval-gated fallback plan.
        if (
            plan_result.is_fallback
            and not self._runner._is_fallback_suggestion(tree)
            and getattr(settings, "open_agent_fallback_enabled", True)
        ):
            open_plan = await self._runner.task_decomposer._get_open_agent_planner().plan(
                intent
            )
            if open_plan is not None and not open_plan.is_fallback:
                plan_result = open_plan
                tree = self._runner.task_decomposer._plan_result_to_task_tree(open_plan)

        # Open agent plans are executed by the open agent executor.
        if plan_result.derivation == "open-agent":
            executor = self._runner._get_open_agent_executor()
            exec_context = {
                "session_id": session_id,
                "project_id": project_id,
                "project_path": str(settings.data_dir / "workspaces" / project_id)
                if project_id
                else None,
                "trace_id": getattr(self._runner, "_trace_id", None),
            }
            exec_result = await executor.execute(
                plan_result=plan_result,
                user_message=user_message,
                working_memory=working_memory,
                context=exec_context,
            )
            # Convert OpenAgentExecutionResult to TurnResult.
            from homomics_lab.models.common import HITLCheckpoint

            hitl_checkpoint = None
            if exec_result.hitl_checkpoint is not None and isinstance(
                exec_result.hitl_checkpoint, HITLCheckpoint
            ):
                hitl_checkpoint = exec_result.hitl_checkpoint
            return TurnResult(
                mode=ExecutionMode(exec_result.mode),
                response_text=exec_result.response_text,
                agent_message=exec_result.agent_message,
                hitl_checkpoint=hitl_checkpoint,
            )

        plan: Optional[Plan] = None
        if plan_store is not None:
            plan = Plan(
                plan_id=_new_plan_id(),
                session_id=session_id,
                project_id=project_id,
                status=PlanStatus.PENDING_APPROVAL,
                is_fallback=plan_result.is_fallback,
                intent_analysis_type=intent.analysis_type,
                intent_complexity=intent.complexity,
                original_intent={
                    "analysis_type": intent.analysis_type,
                    "complexity": intent.complexity,
                    "confidence": intent.confidence,
                    "original_message": intent.original_message,
                    "domain": intent.domain,
                    "target": intent.target,
                    "scope": intent.scope,
                    "interaction_mode": intent.interaction_mode,
                    "metadata": dict(intent.metadata) if isinstance(intent.metadata, dict) else {"_raw": intent.metadata},
                },
                plan_result=plan_result,
                task_tree=tree,
                working_memory=working_memory,
            )
            await plan_store.create(plan)
            record_plan_created(
                strategy=plan_result.strategy_name,
                is_fallback=plan_result.is_fallback,
            )

        if enqueue_skills and job_service is not None:
            return await self.enqueue_execution(
                intent=intent,
                user_message=user_message,
                tree=tree,
                plan=plan,
                working_memory=working_memory,
                session_id=session_id,
                project_id=project_id,
                job_service=job_service,
                plan_store=plan_store,
                plan_mode=plan_mode,
            )

        if scope == "single_step":
            return await self._runner._handle_single_step(
                tree,
                working_memory,
                project_id,
                intent=intent,
                user_message=user_message,
            )

        return await self._runner._handle_workflow(
            tree,
            working_memory,
            project_id,
            intent=intent,
            user_message=user_message,
            plan=plan,
        )

    @staticmethod
    def is_domain_template_analysis(intent: "UserIntent") -> bool:
        """Return True for real domain-specific analysis workflows."""
        return intent.domain in REAL_DOMAIN_VALUES

    def plan_is_auto_approved(
        self,
        tree: "TaskTree",
        domain: Optional[str],
        role_id: Optional[str] = None,
    ) -> bool:
        """Return True when every task skill is auto-approved for the domain/role."""
        if not tree.tasks:
            return False
        registry = self._runner._permission_registry
        for task in tree.tasks:
            skills = task.skills_required or []
            if not skills:
                return False
            for skill_id in skills:
                if registry.is_denied_skill(role_id, domain, skill_id):
                    return False
                if not registry.can_auto_approve_skill(
                    role_id, domain, skill_id, risk_level=task.risk_level
                ):
                    return False
        return True

    async def enqueue_execution(
        self,
        intent: "UserIntent",
        user_message: str,
        tree: "TaskTree",
        plan: Optional[Plan],
        working_memory: "WorkingMemory",
        session_id: str,
        project_id: str,
        job_service: Any,
        plan_store: Optional[PlanStore],
        plan_mode: bool = False,
    ) -> "TurnResult":
        """Submit a task tree to the background job queue or request approval."""
        from homomics_lab.agent.turn_runner import ExecutionMode, TurnResult

        is_domain = self.is_domain_template_analysis(intent)
        plan_result = plan.plan_result if plan is not None else None
        is_high_risk = (
            plan_result is not None
            and (plan_result.is_fallback or plan_result.risk_level == "high")
        )
        # A concrete single-task execution (e.g. "use CellTypist on sample.h5ad")
        # should execute immediately even when the LLM labelled the overall intent
        # as complex.  We trust the decomposed task tree over the noisy structured
        # complexity score when there is exactly one low-risk, dependency-free task.
        is_single_task_tree = (
            tree is not None
            and len(tree.tasks) == 1
            and not tree.tasks[0].dependencies
            and tree.tasks[0].risk_level != "high"
        )
        # Plan approval is governed by a configurable strategy resolved as
        # role -> domain -> global (default: risky_only). Explicit plan_mode and
        # fallback/high-risk plans always gate; a single concrete low-risk task
        # runs directly under every strategy.
        domain_def = get_domain_registry().get(intent.domain) if intent.domain else None
        strategy = resolve_strategy(domain_def=domain_def, role_id=None, settings=settings)
        # Load persisted approved plan signatures for first_time strategy.
        project_state_manager = ProjectStateManager(CBKB(settings.data_dir))
        project_state = project_state_manager.load(project_id or "default")
        seen_signatures = project_state.approved_plan_signatures
        needs_approval, updated_signatures = should_require_approval(
            strategy=strategy,
            plan=plan,
            tree=tree,
            is_high_risk=is_high_risk,
            is_single_task_tree=is_single_task_tree,
            plan_mode=plan_mode,
            seen_signatures=seen_signatures,
        )

        # Permission rulesets can auto-approve plans that only use allowed
        # tools/skills for the current role/domain.  Invariants (plan_mode,
        # high-risk, fallback) still gate regardless of rules.
        if (
            needs_approval
            and not plan_mode
            and not is_high_risk
            and tree is not None
            and self.plan_is_auto_approved(tree, domain=intent.domain)
        ):
            needs_approval = False

        # Optional specialist + critic review for complex / high-risk plans.
        review: Optional[Dict[str, Any]] = None
        if (
            settings.subagent_review_enabled
            and plan is not None
            and self._runner._llm_client is not None
            and self._runner._tool_registry is not None
            and (is_high_risk or len(tree.tasks) > 1 or intent.complexity in ("complex", "multi_step"))
        ):
            try:
                review = await self.review_plan_with_subagents(
                    request=user_message,
                    plan=plan,
                    intent=intent,
                    domain_def=domain_def,
                    working_memory=working_memory,
                )
                plan.metadata["critic_review"] = review
                if plan_store is not None:
                    await plan_store.update(plan)
            except Exception:
                logger.warning("Sub-agent review failed; continuing without it", exc_info=True)

        if plan is not None and needs_approval:
            review_note = ""
            if review:
                summary = review.get("summary", "")
                concerns = review.get("concerns", [])
                suggestions = review.get("suggestions", [])
                parts = []
                if summary:
                    parts.append(f"复核结论：{summary}")
                if concerns:
                    parts.append(f"关注点：{'; '.join(concerns)}")
                if suggestions:
                    parts.append(f"建议：{'; '.join(suggestions)}")
                if parts:
                    review_note = "\n\n" + "\n".join(parts)

            if is_domain:
                response_text = "我为您生成了一个分析计划，请确认后再执行。" + review_note
                plan_payload = PlanPresenter.to_user_payload(plan)
                agent_msg = ChatMessage(
                    id=f"msg_{len(working_memory.messages)}",
                    type=MessageType.PLAN_REQUEST,
                    content={
                        "plan_id": plan.plan_id,
                        "plan": plan_payload,
                        "response_text": response_text,
                        "critic_review": review,
                    },
                    sender="agent",
                )
            else:
                response_text = "我为您规划了以下执行步骤，请确认后再执行。" + review_note
                estimates = {}
                if plan is not None:
                    estimates = {
                        "total_estimated_cost_usd": plan.plan_result.total_estimated_cost_usd,
                        "total_estimated_duration_seconds": plan.plan_result.total_estimated_duration_seconds,
                    }
                progress, progress_tasks = self.build_initial_progress(tree)
                agent_msg = ChatMessage(
                    id=f"msg_{len(working_memory.messages)}",
                    type=MessageType.EXECUTION_PLAN,
                    content={
                        "plan_id": plan.plan_id,
                        "response_text": response_text,
                        "tasks": progress_tasks,
                        "progress": progress,
                        "estimates": estimates,
                        "critic_review": review,
                    },
                    sender="agent",
                )
            working_memory.add_message(agent_msg)
            return TurnResult(
                mode=ExecutionMode.AWAITING_PLAN_APPROVAL,
                response_text=response_text,
                task_tree=tree,
                agent_message=agent_msg,
                plan_id=plan.plan_id,
            )

        self._runner._attach_uploaded_files_to_tree(tree, user_message, project_id)
        mode = (
            JobMode.SINGLE_STEP
            if intent.scope == "single_step"
            or is_single_task_tree
            else JobMode.WORKFLOW
        )
        job = await job_service.create_job(
            session_id=session_id,
            project_id=project_id,
            working_memory=working_memory,
            task_tree=tree,
            mode=mode,
            plan_id=plan.plan_id if plan is not None else None,
        )
        if plan is not None and plan_store is not None:
            plan.status = PlanStatus.APPROVED
            plan.approved_by = "system"
            await plan_store.update(plan)

        # Persist the plan signature now that it has been approved/executed.
        # This makes the first_time approval strategy survive restarts.
        if (
            strategy == "first_time"
            and plan is not None
            and updated_signatures is not None
            and len(updated_signatures) > len(seen_signatures)
        ):
            try:
                project_state.approved_plan_signatures = updated_signatures
                project_state_manager.save(project_state)
            except Exception:
                logger.warning("Failed to persist approved plan signatures", exc_info=True)

        response_text = "已提交后台执行，完成后会通知您。"
        progress, progress_tasks = self.build_initial_progress(tree)
        agent_msg = ChatMessage(
            id=f"msg_{len(working_memory.messages)}",
            type=MessageType.TODO_LIST,
            content={
                "text": response_text,
                "tasks": progress_tasks,
                "progress": progress,
                "job_id": job.job_id,
                "project_id": project_id,
            },
            sender="agent",
        )
        working_memory.add_message(agent_msg)
        return TurnResult(
            mode=ExecutionMode.QUEUED,
            response_text=response_text,
            task_tree=tree,
            agent_message=agent_msg,
            job_id=job.job_id,
            plan_id=plan.plan_id if plan is not None else None,
        )

    async def review_plan_with_subagents(
        self,
        request: str,
        plan: Plan,
        intent: "UserIntent",
        domain_def: Any,
        working_memory: "WorkingMemory",
    ) -> Dict[str, Any]:
        """Run a domain specialist + critic review on a plan before approval.

        The review is best-effort: failures are logged and do not block execution.
        """
        role = None
        if domain_def is not None and getattr(domain_def, "roles", None):
            role = domain_def.roles[0]

        orchestrator = SpecialistCriticOrchestrator(
            llm_client=self._runner._llm_client,
            tool_registry=self._runner._tool_registry,
            role=role,
            domain=intent.domain,
        )
        history = self._runner._working_memory_to_history(working_memory)
        review = await orchestrator.review(request, plan, history=history)
        return review.to_dict()

    @staticmethod
    def build_initial_progress(tree: "TaskTree") -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Build a zero-progress dict and a task list for a freshly created plan/job.

        When the task tree carries finer-grained ``display_steps`` (e.g. a single
        skill that performs annotation + label comparison), those steps are
        surfaced to the user instead of the coarse executable tasks.
        """
        display_steps = getattr(tree, "display_steps", None) or []
        if display_steps:
            progress_tasks = [
                {
                    "id": getattr(step, "id", f"step_{idx}"),
                    "name": getattr(step, "description", "") or getattr(step, "phase_type", ""),
                    "description": getattr(step, "description", ""),
                    "phase_type": getattr(step, "phase_type", None),
                    "analysis_type": getattr(step, "analysis_type", None),
                    "status": "pending",
                }
                for idx, step in enumerate(display_steps, start=1)
            ]
        else:
            progress_tasks = [
                {
                    "id": task.id,
                    "name": task.name,
                    "description": task.description,
                    "phase_type": task.phase,
                    "status": "pending",
                }
                for task in tree.tasks
            ]
        total = len(progress_tasks)
        progress = {
            "total": total,
            "pending": total,
            "running": 0,
            "completed": 0,
            "failed": 0,
            "awaiting_human": 0,
            "percent": 0,
        }
        return progress, progress_tasks
