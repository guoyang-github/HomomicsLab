"""TaskExecutors — CodeAct/supervisor execution strategies for Orchestrator.

Extracted from ``orchestrator.Orchestrator`` as a pure code move (no logic
changes). The executor holds a back-reference to the orchestrator for the
shared services that remain on ``Orchestrator`` (``state_machine``,
``skill_registry``, ``supervisor``, ``_emit_progress``, ``_execution_mode``,
``_resolve_skill_definition``).
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Dict, List, Optional, Set, Tuple

from homomics_lab.agent.progress_events import build_agent_event
from homomics_lab.agent.workflow_markers import (
    build_marker_convention,
    extract_domain_pipeline,
    parse_marker_line,
    scan_marker_lines,
)
from homomics_lab.config import settings
from homomics_lab.execution.code_act import run_code_act
from homomics_lab.hpc.state import ExecutionState
from homomics_lab.llm_client import LLMClient
from homomics_lab.models.common import TaskStatus
from homomics_lab.observability.trace_store import TraceStore
from homomics_lab.tasks.models import TaskNode
from homomics_lab.viz.chart_critic import ChartCritic, ChartCritique, collect_chart_paths

if TYPE_CHECKING:
    from homomics_lab.agent.orchestrator import Orchestrator

logger = logging.getLogger(__name__)


class TaskExecutors:
    """Execute tasks via CodeAct, skill-as-reference, or supervisor delegation."""

    def __init__(self, orchestrator: "Orchestrator"):
        self._orch = orchestrator
        # Task-level dedupe sets recording already-emitted (phase, status)
        # workflow events: the streaming line callback records what it reports
        # in real time, and the post-execution batch scan skips those entries.
        # Reset by ``_emit_workflow_skeleton`` at each task execution start.
        self._phase_events_sent: Dict[str, Set[Tuple[str, str]]] = {}
        # Fire-and-forget trace mirroring tasks scheduled from the (sync)
        # streaming callback; strong refs are kept until they complete.
        self._pending_trace_tasks: Set[asyncio.Task] = set()

    @staticmethod
    def _new_llm_client() -> Optional[LLMClient]:
        """Best-effort LLM client construction; None when unavailable."""
        try:
            return LLMClient()
        except Exception:
            return None

    def _fallback_task_prompt(
        self,
        task: TaskNode,
        original_error: Optional[str] = None,
    ) -> str:
        """Build a concise CodeAct prompt from the failed task metadata."""
        parts = [
            f"Task: {task.name}",
            f"Description: {task.description or task.name}",
        ]
        if task.skills_required:
            parts.append(f"Skills that failed: {', '.join(task.skills_required)}")
        if task.parameters:
            # Keep the prompt focused; avoid dumping huge nested structures.
            params = {
                k: v for k, v in task.parameters.items()
                if isinstance(v, (str, int, float, bool)) or v is None
            }
            if params:
                parts.append(f"Parameters: {params}")
        if original_error:
            parts.append(f"Original error: {original_error}")
        convention = self._marker_convention_for(task)
        if convention:
            parts.append(convention)
        return "\n".join(parts)

    def _fallback_working_dir(self, context: Dict[str, Any]) -> Optional[Path]:
        """Resolve a working directory for CodeAct fallback."""
        project_id = context.get("project_id") if context else None
        if project_id:
            return settings.data_dir / "workspaces" / project_id
        return None

    # ------------------------------------------------------------------
    # Domain workflow DAG events (CodeAct single-script path).
    #
    # For domain-owned tasks the generated script is asked to print
    # ``__homomics_phase__`` marker lines (see ``agent/workflow_markers.py``).
    # A ``workflow_skeleton`` event is emitted once when execution starts;
    # each parsed marker becomes a ``phase`` event.  Both travel as
    # ``ExecutionState.extra`` top-level payload keys (job_id/session_id are
    # stamped by the job runner) and are mirrored into the trace store so the
    # DAG state can be recovered after a session switch.  Everything here is
    # best effort: no domain or no markers means zero events and zero errors.
    # ------------------------------------------------------------------

    @staticmethod
    def _marker_convention_for(task: TaskNode) -> Optional[str]:
        """Return the marker convention prompt snippet, or None to inject nothing."""
        pipeline = extract_domain_pipeline(task)
        if pipeline is None:
            return None
        _, phases = pipeline
        return build_marker_convention(phases)

    def _emit_workflow_event(
        self,
        task: TaskNode,
        payload: Dict[str, Any],
        progress_pct: float = 0.0,
    ) -> None:
        """Emit one workflow progress event as top-level payload keys.

        Top-level execution: no ``actor``/``parent_id`` (progress_events
        contract).  ``type: "progress"`` is included so consumers can route
        the event without a side channel.
        """
        try:
            self._orch._report_progress(
                ExecutionState(
                    job_id="",
                    status="RUNNING",
                    current_phase=task.name,
                    progress_pct=progress_pct,
                    scheduler_type="agent",
                    extra={"type": "progress", **payload},
                )
            )
        except Exception:
            pass

    async def _trace_workflow_event(
        self,
        task: TaskNode,
        context: Dict[str, Any],
        *,
        node_type: str,
        name: str,
        metadata: Dict[str, Any],
    ) -> None:
        """Mirror a workflow event into the trace store (best effort)."""
        trace_id = context.get("trace_id") if context else None
        if not trace_id:
            return
        try:
            store = TraceStore()
            await store.add_node(
                trace_id=trace_id,
                node_type=node_type,
                name=name,
                parent_id="root",
                inputs={},
                metadata={**metadata, "task_id": task.id},
            )
        except Exception:
            # Trace recording must not break execution.
            pass

    async def _emit_workflow_skeleton(
        self, task: TaskNode, context: Dict[str, Any]
    ) -> None:
        """Emit the one-shot ``workflow_skeleton`` event for a domain task.

        The skeleton is the task's domain pipeline phases (already trimmed by
        ``preflight.skip_phases`` at plan time), or the degraded
        display_subtasks / own-phase list when no full pipeline is available.
        """
        pipeline = extract_domain_pipeline(task)
        if pipeline is None:
            return
        # A fresh task execution may re-report phases: reset the dedupe set so
        # re-executions are not silenced by events from a previous attempt.
        self._phase_events_sent[task.id] = set()
        domain, phases = pipeline
        skeleton = [
            {
                "phase_type": p["phase_type"],
                "name": p.get("name") or p["phase_type"],
                "skipped": False,
            }
            for p in phases
        ]
        self._emit_workflow_event(
            task,
            {"event": "workflow_skeleton", "domain": domain, "phases": skeleton},
            progress_pct=5.0,
        )
        await self._trace_workflow_event(
            task,
            context,
            node_type="plan",
            name=f"workflow_skeleton:{domain}",
            metadata={
                "event": "workflow_skeleton",
                "domain": domain,
                "phases": skeleton,
            },
        )

    # ------------------------------------------------------------------
    # Fixed-pipeline (curated skill runtime) workflow DAG events.
    #
    # In fixed_pipeline mode the task tree carries one task per domain phase
    # and no CodeAct script runs, so there are no stdout markers to scan.
    # Instead the orchestrator's per-task dispatch maps directly onto phase
    # events: task start/finish/failure -> phase start/done/failed. The
    # skeleton is the same one the CodeAct path emits (idempotent on the
    # frontend, which overwrites on repeats).
    # ------------------------------------------------------------------

    async def _emit_fixed_pipeline_task_start(
        self, task: TaskNode, context: Dict[str, Any]
    ) -> None:
        """Emit skeleton + ``phase:start`` for a fixed_pipeline domain task."""
        pipeline = extract_domain_pipeline(task)
        if pipeline is None:
            return
        await self._emit_workflow_skeleton(task, context)
        await self._emit_fixed_pipeline_phase(task, context, "start")

    async def _emit_fixed_pipeline_task_done(
        self, task: TaskNode, context: Dict[str, Any]
    ) -> None:
        """Emit ``phase:done`` for a finished fixed_pipeline domain task."""
        await self._emit_fixed_pipeline_phase(task, context, "done")

    async def _emit_fixed_pipeline_task_failed(
        self, task: TaskNode, context: Dict[str, Any], error: Optional[str] = None
    ) -> None:
        """Emit ``phase:failed`` for a failed fixed_pipeline domain task."""
        await self._emit_fixed_pipeline_phase(task, context, "failed", error=error)

    async def _emit_fixed_pipeline_phase(
        self,
        task: TaskNode,
        context: Dict[str, Any],
        status: str,
        error: Optional[str] = None,
    ) -> None:
        """Map one curated-runtime task state onto a ``phase`` workflow event."""
        pipeline = extract_domain_pipeline(task)
        if pipeline is None:
            return
        phase_id = getattr(task, "phase", "") or ""
        if not phase_id or phase_id == "execution":
            return
        _, phases = pipeline
        order = {p["phase_type"]: idx for idx, p in enumerate(phases)}
        total = max(1, len(phases))
        params: Dict[str, Any] = {}
        if task.skills_required:
            params["skill"] = task.skills_required[0]
        if error:
            params["error"] = error
        self._emit_workflow_event(
            task,
            {
                "event": "phase",
                "phase": phase_id,
                "status": status,
                "params": params,
            },
            progress_pct=self._phase_progress_pct(order, total, phase_id, status),
        )
        await self._trace_workflow_event(
            task,
            context,
            node_type="phase",
            name=f"phase:{phase_id}:{status}",
            metadata={
                "event": "phase",
                "phase": phase_id,
                "status": status,
                "params": params,
            },
        )

    @staticmethod
    def _phase_progress_pct(
        order: Dict[str, int], total: int, phase: str, status: str
    ) -> float:
        """Map a phase event onto the 10-95% execution progress band."""
        idx = order.get(phase)
        if idx is None:
            return 50.0
        # start advances half a step, done/failed a full step.
        step = idx + (0.5 if status == "start" else 1.0)
        return min(95.0, 10.0 + 80.0 * step / total)

    async def _flush_trace_tasks(self) -> None:
        """Await fire-and-forget trace mirroring tasks (best effort)."""
        pending = list(self._pending_trace_tasks)
        if not pending:
            return
        await asyncio.gather(*pending, return_exceptions=True)
        self._pending_trace_tasks.difference_update(pending)

    def _emit_phase_event(
        self,
        task: TaskNode,
        context: Dict[str, Any],
        order: Dict[str, int],
        total: int,
        phase: str,
        status: str,
        params: Dict[str, Any],
    ) -> None:
        """Emit one ``phase`` workflow event and mirror it to the trace store.

        The progress event goes out synchronously (real-time); the trace
        mirror is scheduled as a fire-and-forget task because this method is
        also called from the sync streaming line callback. Trace tasks are
        awaited by ``_flush_trace_tasks`` after execution settles.
        """
        self._emit_workflow_event(
            task,
            {"event": "phase", "phase": phase, "status": status, "params": params},
            progress_pct=self._phase_progress_pct(order, total, phase, status),
        )
        trace_coro = self._trace_workflow_event(
            task,
            context,
            node_type="phase",
            name=f"phase:{phase}:{status}",
            metadata={
                "event": "phase",
                "phase": phase,
                "status": status,
                "params": params,
            },
        )
        try:
            trace_task = asyncio.create_task(trace_coro)
        except RuntimeError:
            # No running event loop (defensive; callbacks fire inside the loop).
            trace_coro.close()
            return
        self._pending_trace_tasks.add(trace_task)
        trace_task.add_done_callback(self._pending_trace_tasks.discard)

    def _make_phase_line_callback(
        self, task: TaskNode, context: Dict[str, Any]
    ) -> Optional[Callable[[str, str], None]]:
        """Build a real-time marker callback for streaming CodeAct output.

        Returns ``None`` for non-domain tasks (no markers injected, nothing
        to report — output is then collected in one batch as before). Each
        parsed marker becomes an immediate ``phase`` event; the shared
        per-task dedupe set keeps the post-execution batch scan from
        re-emitting what was already reported.
        """
        pipeline = extract_domain_pipeline(task)
        if pipeline is None:
            return None
        _, phases = pipeline
        order = {p["phase_type"]: idx for idx, p in enumerate(phases)}
        total = max(1, len(phases))
        emitted = self._phase_events_sent.setdefault(task.id, set())

        def _on_output_line(line: str, stream: str) -> None:
            marker = parse_marker_line(line)
            if marker is None:
                return
            phase, status, params = marker
            key = (phase, status)
            if key in emitted:
                return
            emitted.add(key)
            self._emit_phase_event(task, context, order, total, phase, status, params)

        return _on_output_line

    async def _emit_phase_markers(
        self,
        task: TaskNode,
        context: Dict[str, Any],
        codeact_result: Dict[str, Any],
    ) -> None:
        """Scan captured CodeAct output for phase markers and emit ``phase`` events.

        Successful runs carry markers in ``stdout``; failed runs surface the
        merged stream as ``stderr`` (see ``execution/code_act.execute_code``),
        so both are scanned.  No markers -> no events (phases stay pending).

        This is the batch fallback behind the real-time streaming callback
        (``_make_phase_line_callback``): markers already reported live are
        skipped via the task-level dedupe set.
        """
        pipeline = extract_domain_pipeline(task)
        if pipeline is None:
            return
        _, phases = pipeline
        order = {p["phase_type"]: idx for idx, p in enumerate(phases)}
        total = max(1, len(phases))
        emitted = self._phase_events_sent.setdefault(task.id, set())
        text = "\n".join(
            part
            for part in (codeact_result.get("stdout"), codeact_result.get("stderr"))
            if part
        )
        for phase, status, params in scan_marker_lines(text):
            key = (phase, status)
            if key in emitted:
                continue
            emitted.add(key)
            self._emit_phase_event(task, context, order, total, phase, status, params)
        # Drain trace mirrors scheduled from the streaming callback so trace
        # state is settled before the task moves on.
        await self._flush_trace_tasks()

    async def _try_codeact_fallback(
        self,
        task: TaskNode,
        context: Dict[str, Any],
        original_error: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Try to recover a failed task by generating and executing code.

        Returns a skill-style result dict on success, or None when fallback
        is disabled, unavailable, or also fails.
        """
        # Fixed-pipeline mode means curated skills must succeed or fail cleanly;
        # do not silently generate code.
        if self._orch._execution_mode(context) == "fixed_pipeline":
            return None

        await self._emit_workflow_skeleton(task, context)
        codeact_result = await self._run_codeact_for_task(
            task, context, original_error=original_error
        )
        if not codeact_result.get("success"):
            return None
        return self._normalize_codeact_result(
            task, codeact_result, original_error=original_error, fallback=True
        )

    async def _execute_task_codeact(
        self,
        task: TaskNode,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute a task directly with CodeAct (foundation-first path).

        This is the primary execution strategy when ``execution_mode`` is
        ``codeact``. Curated skills are treated as references, not as rigid
        entrypoints, so the agent can generate bridging code as needed.
        """
        self._orch.state_machine.transition(task, TaskStatus.RUNNING)
        await self._emit_workflow_skeleton(task, context)
        codeact_result = await self._run_codeact_for_task(task, context)
        return self._normalize_codeact_result(
            task, codeact_result, skill_name="codeact"
        )

    async def _run_codeact_for_task(
        self,
        task: TaskNode,
        context: Dict[str, Any],
        original_error: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate and run CodeAct for a task."""
        if not getattr(settings, "codeact_fallback_enabled", True):
            return {"success": False, "error": "CodeAct execution disabled"}

        working_dir = self._fallback_working_dir(context)
        if working_dir is None:
            return {"success": False, "error": "No project working directory available"}

        outputs_dir = working_dir / "outputs"
        outputs_dir.mkdir(parents=True, exist_ok=True)

        prompt = self._fallback_task_prompt(task, original_error)
        prompt += (
            "\n\nImportant: write all output files (CSV, TXT, JSON, PNG, PDF, etc.) "
            f"to the directory '{outputs_dir}'. Do not scatter outputs in the working directory."
        )
        code_context: Dict[str, Any] = {
            "task_name": task.name,
            "task_description": task.description or task.name,
            "project_id": context.get("project_id"),
            "output_dir": str(outputs_dir),
            "working_dir": str(working_dir),
        }
        for key, value in task.parameters.items():
            if isinstance(value, (str, Path)):
                path = Path(value)
                if path.is_file() or path.is_dir():
                    code_context[key] = str(value)
            elif isinstance(value, dict) and "path" in value:
                code_context[key] = value["path"]
            elif isinstance(value, (int, float, bool)) or value is None:
                code_context[key] = value

        llm_client = self._new_llm_client()

        # Real-time phase reporting: domain phase markers printed by the
        # generated script are turned into ``phase`` events as they arrive;
        # the post-execution batch scan (``_emit_phase_markers``) stays as
        # the deduplicated fallback.
        on_output_line = self._make_phase_line_callback(task, context)

        max_attempts = max(1, task.retry_policy.max_attempts)
        backoff = task.retry_policy.backoff_seconds
        last_error: Optional[str] = original_error
        for attempt in range(1, max_attempts + 1):
            attempt_prompt = self._fallback_task_prompt(task, last_error)
            attempt_prompt += (
                "\n\nImportant: write all output files (CSV, TXT, JSON, PNG, PDF, etc.) "
                f"to the directory '{outputs_dir}'. Do not scatter outputs in the working directory."
            )
            self._orch._emit_progress(
                status="RUNNING",
                current_phase=f"正在生成分析脚本… (尝试 {attempt}/{max_attempts})",
                progress_pct=10.0 + (attempt - 1) * 20.0,
            )
            try:
                codeact_result = await run_code_act(
                    task=attempt_prompt,
                    language="python",
                    context=code_context,
                    working_dir=working_dir,
                    llm_client=llm_client,
                    skill_registry=self._orch.skill_registry,
                    tool_registry=None,
                    on_output_line=on_output_line,
                )
                if codeact_result.get("success"):
                    self._orch._emit_progress(
                        status="RUNNING",
                        current_phase="脚本执行完成，正在整理结果…",
                        progress_pct=80.0,
                    )

                    async def _rerun(new_prompt: str) -> Dict[str, Any]:
                        return await run_code_act(
                            task=new_prompt,
                            language="python",
                            context=code_context,
                            working_dir=working_dir,
                            llm_client=llm_client,
                            skill_registry=self._orch.skill_registry,
                            tool_registry=None,
                            on_output_line=on_output_line,
                        )

                    final_result = await self._critique_charts_and_repair(
                        task,
                        context,
                        codeact_result,
                        attempt_prompt,
                        llm_client,
                        _rerun,
                    )
                    await self._emit_phase_markers(task, context, final_result)
                    return final_result
                last_error = (
                    codeact_result.get("stderr")
                    or codeact_result.get("error")
                    or "unknown error"
                )
                # A failed script may still have reported phase start/failed
                # markers before crashing; surface them as phase events.
                await self._emit_phase_markers(task, context, codeact_result)
            except Exception as exc:
                last_error = str(exc)
                logger.warning(
                    "CodeAct execution failed for task %s (attempt %d): %s",
                    task.name,
                    attempt,
                    exc,
                )

            if attempt < max_attempts:
                self._orch._emit_progress(
                    status="RETRYING",
                    current_phase=f"检测到错误，正在自动修复并重试… (attempt {attempt + 1}/{max_attempts})",
                    progress_pct=30.0 + attempt * 20.0,
                    error_message=last_error[:500],
                )
                await asyncio.sleep(backoff * (2 ** (attempt - 1)))

        return {
            "success": False,
            "error": last_error or "CodeAct execution failed after retries",
        }

    @staticmethod
    def _normalize_codeact_result(
        task: TaskNode,
        codeact_result: Dict[str, Any],
        original_error: Optional[str] = None,
        fallback: bool = False,
        skill_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Normalize a CodeAct result into a skill-style result dict."""
        if skill_name is None:
            skill_name = task.skills_required[0] if task.skills_required else "codeact"
        normalized: Dict[str, Any] = {
            "status": "success" if codeact_result.get("success") else "error",
            "skill": skill_name,
            "fallback": fallback,
            "original_error": original_error,
            "result": codeact_result.get("result") or {},
            "stdout": codeact_result.get("stdout", ""),
            "stderr": codeact_result.get("stderr", ""),
            "code": codeact_result.get("code", ""),
            # Self-correction provenance: SkillGenesis uses a non-empty
            # fix_history as the "validated robustness" candidacy signal.
            "attempts": codeact_result.get("attempts", 1),
            "fix_history": codeact_result.get("fix_history", []),
        }
        result_data = normalized["result"]
        if isinstance(result_data, dict):
            for key in ("output_path", "output_file", "plot_path"):
                if key in result_data and "output_files" not in normalized:
                    normalized["output_files"] = [result_data[key]]
                    break
        return normalized

    async def _critique_charts_and_repair(
        self,
        task: TaskNode,
        context: Dict[str, Any],
        codeact_result: Dict[str, Any],
        prompt: str,
        llm_client: Optional[LLMClient],
        rerun: Callable[[str], Awaitable[Dict[str, Any]]],
    ) -> Dict[str, Any]:
        """VLM chart feedback loop: critique produced charts, repair at most N times.

        Opt-in via ``settings.chart_critic_enabled`` (default off). Each
        produced chart is assessed by :class:`ChartCritic` (cheap rule
        pre-checks first, vision LLM second). When a high-severity problem is
        found, the critique suggestion is fed back into one bounded repair run
        (``settings.chart_critic_max_retries``, default 1). If the repair does
        not converge, the original charts are kept and a note is attached to
        the result. Every failure inside this loop degrades to returning the
        original result unchanged — it must never break the main flow.
        """
        if not getattr(settings, "chart_critic_enabled", False):
            return codeact_result
        try:
            charts = collect_chart_paths(codeact_result.get("result") or {})
            if not charts:
                return codeact_result

            critic = ChartCritic(llm_client=llm_client)
            intent = task.description or task.name
            critiques = await self._critique_all(critic, charts, intent, task)
            codeact_result["chart_critiques"] = critiques
            bad = [c for c in critiques if not c["ok"] and c["severity"] == "high"]
            if not bad:
                return codeact_result

            max_retries = max(0, int(getattr(settings, "chart_critic_max_retries", 1)))
            suggestions = "; ".join(
                f"[{', '.join(c['issues'])}] {c['suggestion']}".strip() for c in bad
            )
            for attempt in range(1, max_retries + 1):
                self._orch._emit_progress(
                    status="RETRYING",
                    current_phase=f"图表质检发现问题，正在自动修正… (尝试 {attempt}/{max_retries})",
                    progress_pct=85.0,
                )
                repair_prompt = (
                    f"{prompt}\n\nChart quality feedback from automated visual review: "
                    f"{suggestions}\nRegenerate the analysis so the produced charts fix "
                    "these issues (non-empty data, labeled axes, readable labels, no "
                    "legend occlusion), keeping all other outputs intact."
                )
                try:
                    repaired = await rerun(repair_prompt)
                except Exception as exc:
                    logger.warning(
                        "chart repair run failed for task %s: %s", task.name, exc
                    )
                    break
                if not repaired.get("success"):
                    break
                repaired_charts = collect_chart_paths(repaired.get("result") or {})
                repaired_critiques = await self._critique_all(
                    critic, repaired_charts, intent, task
                )
                repaired["chart_critiques"] = critiques + repaired_critiques
                if not [
                    c
                    for c in repaired_critiques
                    if not c["ok"] and c["severity"] == "high"
                ]:
                    return repaired

            # Repair did not converge: keep the original charts and annotate.
            codeact_result["chart_critique_note"] = (
                "图表自动质检发现问题（自动修正后仍未完全解决）："
                f"{suggestions}。已保留原始图表，请人工确认。"
            )
            return codeact_result
        except Exception:
            logger.debug(
                "chart critique loop failed; keeping original result", exc_info=True
            )
            return codeact_result

    async def _critique_all(
        self,
        critic: ChartCritic,
        charts: List[Path],
        intent: str,
        task: TaskNode,
    ) -> List[Dict[str, Any]]:
        """Critique every chart and emit one ``chart_critique`` event per chart."""
        critiques: List[Dict[str, Any]] = []
        for chart in charts:
            critique = await critic.critique(
                chart, intent=intent, context={"task_name": task.name}
            )
            critiques.append({"path": str(chart), **critique.to_dict()})
            self._emit_chart_critique_event(task, str(chart), critique)
        return critiques

    def _emit_chart_critique_event(
        self, task: TaskNode, chart_path: str, critique: ChartCritique
    ) -> None:
        """Emit a structured ``chart_critique`` progress event for Execution Logs.

        Uses the same ``resource_usage["agent_events"]`` channel as the agent
        skill loop (see ``homomics_lab.agent.progress_events``); top-level
        executions carry no ``actor``/``parent_id``.
        """
        event = build_agent_event(
            "chart_critique",
            tool="chart_critic",
            success=critique.ok,
            output=(
                f"{Path(chart_path).name}: ok={critique.ok} "
                f"severity={critique.severity} issues={critique.issues} "
                f"suggestion={critique.suggestion} source={critique.source}"
            ),
            artifacts=[chart_path],
        )
        try:
            self._orch._report_progress(
                ExecutionState(
                    job_id="",
                    status="RUNNING",
                    current_phase=task.name,
                    progress_pct=85.0,
                    scheduler_type="agent",
                    resource_usage={"agent_events": [event]},
                )
            )
        except Exception:
            pass

    def _load_skill_reference(self, skill: Any) -> str:
        """Load SKILL.md and reference scripts for use as prompt context.

        The text is aggressively size-capped so it can be fed into the LLM
        prompt without crowding out the user's specific request.  SKILL.md
        gets the largest budget; each reference script is limited to a small
        chunk so only the most relevant scripts are included.
        """
        parts: List[str] = []
        if skill.body_path and skill.body_path.is_file():
            try:
                text = skill.body_path.read_text(encoding="utf-8", errors="ignore")
                parts.append(
                    f"=== SKILL DOCUMENTATION ({skill.id}) ===\n{text[:12000]}"
                )
            except Exception as exc:
                logger.warning("Failed to read skill body for %s: %s", skill.id, exc)

        if skill.has_scripts and skill.source_dir:
            scripts_dir = skill.source_dir / "scripts"
            if scripts_dir.is_dir():
                parts.append(f"=== REFERENCE SCRIPTS ({skill.id}) ===")
                total_chars = 0
                max_total = 30000
                per_file_max = 5000
                for path in sorted(scripts_dir.rglob("*")):
                    if not path.is_file():
                        continue
                    suffix = path.suffix.lower()
                    if suffix in (".pyc", ".pyo", ".so", ".dll", ".exe", ".bin"):
                        continue
                    if "__pycache__" in path.parts:
                        continue
                    if path.stat().st_size > 200_000:
                        continue
                    try:
                        snippet = path.read_text(encoding="utf-8", errors="ignore")
                    except Exception:
                        continue
                    if not snippet.strip():
                        continue
                    header = f"--- {path.relative_to(scripts_dir)} ---"
                    chunk = f"{header}\n{snippet[:per_file_max]}"
                    if total_chars + len(chunk) > max_total:
                        break
                    parts.append(chunk)
                    total_chars += len(chunk)
        return "\n\n".join(parts)

    def _build_skill_reference_prompt(
        self,
        task: TaskNode,
        context: Dict[str, Any],
        reference_text: str,
    ) -> str:
        """Build a CodeAct prompt that treats a skill as reference material."""
        user_request = (
            task.parameters.get("user_request") or task.description or task.name
        )
        preflight = task.parameters.get("preflight") or {}

        # Resolve input files from task parameters and context.
        input_files: List[str] = []
        for key, value in task.parameters.items():
            if isinstance(value, (str, Path)):
                path = Path(value)
                if path.is_file() and str(path) not in input_files:
                    input_files.append(str(path))
            elif isinstance(value, dict) and "path" in value:
                p = value["path"]
                if p not in input_files:
                    input_files.append(p)

        ctx_inputs = context.get("workspace_inputs") or {}
        for value in ctx_inputs.values():
            if isinstance(value, (str, Path)):
                path = Path(value)
                if path.is_file() and str(path) not in input_files:
                    input_files.append(str(path))

        working_dir = self._fallback_working_dir(context)
        outputs_dir = (working_dir / "outputs") if working_dir else Path(".")

        parts = [
            f"User request: {user_request}",
            f"Task: {task.name}",
            f"Skill reference: {task.skills_required[0] if task.skills_required else 'unknown'}",
        ]
        if input_files:
            parts.append(f"Input files: {', '.join(input_files)}")
        if preflight:
            parts.append(
                "Data preflight (use this to decide the minimal workflow): "
                f"{json.dumps(preflight, ensure_ascii=False, default=str)}"
            )
        if reference_text:
            parts.append(reference_text)
        parts.append(
            "\nGenerate a compact, self-contained Python script (ideally ≤60 lines) that fulfills "
            "the user request. Use the skill documentation and reference scripts above as "
            "implementation guidance, but adapt the code to the user's specific data and request. "
            f"Read data from the Input files listed above, and write all output files "
            f"(CSV, TXT, JSON, PNG, PDF, etc.) to '{outputs_dir}'. Do not scatter outputs. "
            "If the user asked to compare results with an existing label column (e.g. all_celltype), "
            "include the comparison and report agreement metrics (ARI, NMI, confusion matrix). "
            "Print a brief summary of results at the end and assign it to the `result` variable."
        )
        convention = self._marker_convention_for(task)
        if convention:
            parts.append(convention)
        return "\n\n".join(parts)

    async def _run_codeact_with_prompt(
        self,
        task: TaskNode,
        context: Dict[str, Any],
        prompt: str,
    ) -> Dict[str, Any]:
        """Run CodeAct with a fully custom prompt."""
        if not getattr(settings, "codeact_fallback_enabled", True):
            return {"success": False, "error": "CodeAct execution disabled"}

        working_dir = self._fallback_working_dir(context)
        if working_dir is None:
            return {"success": False, "error": "No project working directory available"}

        outputs_dir = working_dir / "outputs"
        outputs_dir.mkdir(parents=True, exist_ok=True)

        code_context: Dict[str, Any] = {
            "task_name": task.name,
            "task_description": task.description or task.name,
            "project_id": context.get("project_id"),
            "output_dir": str(outputs_dir),
            "working_dir": str(working_dir),
            "skills_required": task.skills_required,
        }
        first_input_path: Optional[str] = None
        for key, value in task.parameters.items():
            if isinstance(value, (str, Path)):
                path = Path(value)
                if path.is_file() or path.is_dir():
                    code_context[key] = str(path)
                    if first_input_path is None and path.is_file():
                        first_input_path = str(path)
            elif isinstance(value, dict) and "path" in value:
                code_context[key] = value["path"]
                if first_input_path is None:
                    first_input_path = value["path"]
            elif isinstance(value, (int, float, bool)) or value is None:
                code_context[key] = value

        if first_input_path is not None:
            code_context["input_path"] = first_input_path
            code_context["adata_path"] = first_input_path

        llm_client = self._new_llm_client()

        try:
            result = await run_code_act(
                task=prompt,
                language="python",
                context=code_context,
                working_dir=working_dir,
                llm_client=llm_client,
                skill_registry=self._orch.skill_registry,
                tool_registry=None,
                max_tokens=8000,
                on_output_line=self._make_phase_line_callback(task, context),
            )
            await self._emit_phase_markers(task, context, result)
            return result
        except Exception as exc:
            logger.warning("CodeAct execution failed for task %s: %s", task.name, exc)
            return {"success": False, "error": str(exc)}

    async def _execute_task_with_skill_reference(
        self,
        task: TaskNode,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute a task by asking the LLM to write a compact script using a skill as reference.

        This is the default path for concrete skill requests: instead of invoking
        the skill's own entrypoint, the LLM reads the skill documentation and
        reference scripts and produces an end-to-end script tailored to the
        user's data and question.
        """
        skill = self._orch._resolve_skill_definition(task)
        if skill is None:
            return {
                "success": False,
                "error": f"Skill not found: {task.skills_required}",
            }

        reference_text = self._load_skill_reference(skill)
        prompt = self._build_skill_reference_prompt(task, context, reference_text)

        self._orch.state_machine.transition(task, TaskStatus.RUNNING)
        await self._emit_workflow_skeleton(task, context)
        max_attempts = max(1, task.retry_policy.max_attempts)
        backoff = task.retry_policy.backoff_seconds
        last_error: Optional[str] = None
        for attempt in range(1, max_attempts + 1):
            self._orch._emit_progress(
                status="RUNNING",
                current_phase=f"正在生成分析脚本… (尝试 {attempt}/{max_attempts})",
                progress_pct=10.0 + (attempt - 1) * 20.0,
            )
            codeact_result = await self._run_codeact_with_prompt(task, context, prompt)
            if codeact_result.get("success"):
                self._orch._emit_progress(
                    status="RUNNING",
                    current_phase="脚本执行完成，正在整理结果…",
                    progress_pct=80.0,
                )
                codeact_result = await self._critique_charts_and_repair(
                    task,
                    context,
                    codeact_result,
                    prompt,
                    self._new_llm_client(),
                    lambda p: self._run_codeact_with_prompt(task, context, p),
                )
                return self._normalize_codeact_result(
                    task, codeact_result, skill_name=skill.id
                )
            last_error = (
                codeact_result.get("stderr")
                or codeact_result.get("error")
                or "unknown error"
            )
            if attempt < max_attempts:
                prompt = self._build_skill_reference_prompt(
                    task, context, reference_text
                )
                prompt += (
                    f"\n\nThe previous attempt failed with the following error. "
                    f"Please fix the script and try again.\nError: {last_error[:2000]}"
                )
                self._orch._emit_progress(
                    status="RETRYING",
                    current_phase=f"检测到错误，正在自动修复并重试… (attempt {attempt + 1}/{max_attempts})",
                    progress_pct=30.0 + attempt * 20.0,
                    error_message=last_error[:500],
                )
                await asyncio.sleep(backoff * (2 ** (attempt - 1)))
        return {
            "success": False,
            "error": last_error or "Skill-as-reference execution failed after retries",
            "skill": skill.id,
        }

    async def _execute_task_with_supervisor(
        self,
        task: TaskNode,
        context: Dict[str, Any],
        results: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute a task under Supervisor delegation.

        Returns a WorkerResult-style dict on failure instead of raising, so
        the Orchestrator can decide retry/replan/HITL.
        """
        max_attempts = task.retry_policy.max_attempts
        backoff = task.retry_policy.backoff_seconds

        for attempt in range(1, max_attempts + 1):
            if task.status != TaskStatus.RUNNING:
                self._orch.state_machine.transition(task, TaskStatus.RUNNING)

            try:
                worker = await self._orch.supervisor.delegate(task, context)
                if worker is None:
                    raise RuntimeError(
                        f"Supervisor could not delegate task {task.name}"
                    )

                raw_result = await worker.run(task, context)
            except Exception as e:
                task.error_message = str(e)
                task.attempt_count = attempt
                if attempt < max_attempts:
                    self._orch.state_machine.transition(task, TaskStatus.FAILED)
                    await asyncio.sleep(backoff * (2 ** (attempt - 1)))
                    continue
                raw_result = {
                    "task_id": task.id,
                    "status": "failure",
                    "output": {},
                    "error": str(e),
                    "execution_time_seconds": 0.0,
                    "metadata": {},
                }

            task.attempt_count = attempt
            task.error_message = (
                raw_result.get("error") if isinstance(raw_result, dict) else None
            )

            # If the worker returned a structured failure, retry internally.
            if isinstance(raw_result, dict) and raw_result.get("status") == "failure":
                if attempt < max_attempts:
                    self._orch.state_machine.transition(task, TaskStatus.FAILED)
                    await asyncio.sleep(backoff * (2 ** (attempt - 1)))
                    continue

            results[task.id] = raw_result
            task.result = raw_result
            return raw_result
