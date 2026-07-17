"""ResultAssembler — builds TurnResult objects for turn outcomes.

Extracted from ``turn_runner.TurnRunner`` as a pure code move (no logic
changes). The assembler holds a back-reference to the runner for the helpers
that remain on ``TurnRunner`` (e.g. ``_single_skill_id``).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from homomics_lab.agent.errors import TurnError
from homomics_lab.models.common import ChatMessage, MessageType

if TYPE_CHECKING:
    from homomics_lab.agent.turn_runner import TurnResult, TurnRunner
    from homomics_lab.context.working_memory import WorkingMemory
    from homomics_lab.tasks.task_tree import TaskTree

logger = logging.getLogger(__name__)


class ResultAssembler:
    """Assemble TurnResult instances for workflow, HITL, fallback and error outcomes."""

    def __init__(self, runner: "TurnRunner"):
        self._runner = runner

    @staticmethod
    def envelopes_from_artifacts(artifacts: Optional[List[Any]]) -> List[Dict[str, Any]]:
        """Normalize any artifact collection into frontend-ready envelopes.

        Accepts rich envelopes (dicts with ``path``), ``Artifact`` model objects
        (``.path``/``.artifact_type``), or plain paths. Always returns full
        ``{kind, mime, name, path, size}`` envelopes so the frontend renderer
        registry can pick an inline renderer (image/table/...) instead of the
        generic file-link fallback.
        """
        from homomics_lab.artifacts import build_artifact

        envelopes: List[Dict[str, Any]] = []
        seen: set = set()
        for a in artifacts or []:
            path: Optional[str] = None
            extra: Dict[str, Any] = {}
            if isinstance(a, dict):
                path = a.get("path")
                extra = {
                    k: a[k]
                    for k in ("kind", "mime", "name", "size", "url", "preview_url")
                    if a.get(k) is not None
                }
            else:
                path = getattr(a, "path", None)
                if path is None and isinstance(a, (str, Path)):
                    # Plain path entry (documented in the docstring); strings
                    # and Paths have no ``.path`` attribute.
                    path = str(a)
                task_id = getattr(a, "task_id", None)
                atype = getattr(a, "artifact_type", None)
                if task_id is not None:
                    extra["task_id"] = task_id
                if atype is not None:
                    extra["type"] = atype
            if not path:
                continue
            key = str(path)
            if key in seen:
                continue
            seen.add(key)
            env = build_artifact(Path(key)) or {"kind": "file", "mime": "application/octet-stream", "name": Path(key).name, "path": key}
            env.update(extra)
            env.setdefault("path", key)
            envelopes.append(env)
        return envelopes

    @staticmethod
    def envelopes_from_results(results: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Harvest artifact envelopes from an orchestrator ``run_tree`` result map.

        The orchestrator returns a per-task wrapper like
        ``{task_id: {"result": <skill-output>, "skill": ..., "status": ...}}``.
        We look for artifact declarations both in the wrapper and inside the
        nested ``result`` so summaries work regardless of which layer produced
        the output keys.
        """
        if not results:
            return []

        def _collect_from(obj: Any) -> List[Dict[str, Any]]:
            if not isinstance(obj, dict):
                return []
            collected: List[Dict[str, Any]] = []
            arts = obj.get("artifacts")
            if isinstance(arts, list) and arts:
                collected.extend(ResultAssembler.envelopes_from_artifacts(arts))
            paths: List[Any] = []
            for key in ("output_files", "output_paths", "output_csv", "output_h5ad"):
                val = obj.get(key)
                if isinstance(val, (list, tuple)):
                    paths.extend(val)
                elif isinstance(val, (str, Path)):
                    paths.append(val)
            if paths:
                collected.extend(ResultAssembler.envelopes_from_artifacts(paths))
            # Propagate chart-critic annotations onto the chart envelopes so
            # the summary can surface them next to the affected figure.
            note = obj.get("chart_critique_note")
            if note:
                for env in collected:
                    if env.get("kind") == "image":
                        env.setdefault("chart_critique_note", note)
            return collected

        collected: List[Dict[str, Any]] = []
        for raw in results.values():
            if not isinstance(raw, dict):
                continue
            collected.extend(_collect_from(raw))
            nested = raw.get("result")
            if isinstance(nested, dict):
                collected.extend(_collect_from(nested))
        # de-dup by path
        seen: set = set()
        out: List[Dict[str, Any]] = []
        for env in collected:
            p = env.get("path")
            if p and p not in seen:
                seen.add(p)
                out.append(env)
        return out

    @staticmethod
    def summarize(envelopes: List[Dict[str, Any]], user_message: str, skill_id: Optional[str]) -> str:
        """Return a sourced markdown summary, or '' when there is nothing to say."""
        if not envelopes:
            return ""
        try:
            from homomics_lab.result_summary import summarize_artifacts

            summary = summarize_artifacts(
                envelopes, skill_id=skill_id, user_message=user_message or ""
            )
            md = summary.to_markdown()
        except Exception:  # never let summarization break the turn
            logger.debug("result summarization failed", exc_info=True)
            md = ""
        # Surface chart-critic annotations (e.g. a repair that did not
        # converge) so the user sees the caveat next to the affected figure.
        notes: List[str] = []
        for env in envelopes:
            note = env.get("chart_critique_note")
            if note and note not in notes:
                notes.append(note)
        if notes:
            md = (md + "\n\n" if md else "") + "\n".join(f"> {n}" for n in notes)
        return md if md else ""

    @staticmethod
    def tree_progress(tree: "TaskTree") -> Dict[str, Any]:
        """Compute a simple progress summary from a TaskTree."""
        total = len(tree.tasks)
        if total == 0:
            return {
                "total": 0,
                "pending": 0,
                "running": 0,
                "completed": 0,
                "failed": 0,
                "awaiting_human": 0,
                "percent": 0,
            }

        counts = {
            "pending": 0,
            "running": 0,
            "completed": 0,
            "failed": 0,
            "awaiting_human": 0,
        }
        for task in tree.tasks:
            status = (
                task.status.value if hasattr(task.status, "value") else str(task.status)
            )
            if status in counts:
                counts[status] += 1
        counts["total"] = total
        counts["percent"] = int((counts["completed"] / total) * 100)
        return counts

    def build_workflow_result(
        self,
        tree: "TaskTree",
        working_memory: "WorkingMemory",
        backend: str,
        artifacts: Optional[List[Any]] = None,
        error: Optional[str] = None,
        user_message: str = "",
    ) -> "TurnResult":
        """Build a TurnResult from a WorkflowResult."""
        from homomics_lab.agent.turn_runner import ExecutionMode, TurnResult

        envelopes = self.envelopes_from_artifacts(artifacts)
        if error:
            response_text = f"工作流执行失败（{backend}）：{error}"
        else:
            response_text = (
                f"已完成 {len(tree.tasks)} 个分析步骤（执行后端：{backend}）。"
            )
        summary_md = self.summarize(envelopes, user_message, self._runner._single_skill_id(tree))
        if summary_md:
            response_text = f"{response_text}\n\n{summary_md}"

        agent_msg = ChatMessage(
            id=f"msg_{len(working_memory.messages)}",
            type=MessageType.TODO_LIST,
            content={
                "text": response_text,
                "tasks": [t.model_dump() for t in tree.tasks],
                "progress": self.tree_progress(tree),
                "backend": backend,
                "artifacts": envelopes,
            },
            sender="agent",
        )
        working_memory.add_message(agent_msg)

        return TurnResult(
            mode=ExecutionMode.WORKFLOW,
            response_text=response_text,
            task_tree=tree,
            progress=self.tree_progress(tree),
            agent_message=agent_msg,
            error=error,
        )

    def build_fallback_result(
        self,
        tree: "TaskTree",
        working_memory: "WorkingMemory",
    ) -> "TurnResult":
        """Build a TurnResult for a non-executable fallback suggestion."""
        from homomics_lab.agent.turn_runner import ExecutionMode, TurnResult

        suggestion = tree.tasks[0].description
        agent_msg = ChatMessage(
            id=f"msg_{len(working_memory.messages)}",
            type=MessageType.TODO_LIST,
            content={
                "text": suggestion,
                "is_fallback": True,
                "tasks": [],
            },
            sender="agent",
        )
        working_memory.add_message(agent_msg)

        return TurnResult(
            mode=ExecutionMode.WORKFLOW,
            response_text=suggestion,
            task_tree=tree,
            agent_message=agent_msg,
        )

    def extract_hitl(self, results: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Scan execution results for HITL checkpoints."""
        for task_id, result in results.items():
            if isinstance(result, dict) and "hitl" in result:
                return {"checkpoint": result["hitl"], "task_id": task_id}
        return None

    def build_hitl_result(
        self,
        tree: "TaskTree",
        hitl_info: Dict[str, Any],
        working_memory: "WorkingMemory",
    ) -> "TurnResult":
        """Build a TurnResult when execution pauses for HITL."""
        from homomics_lab.agent.turn_runner import ExecutionMode, TurnResult

        response_text = "部分步骤需要您确认参数。"
        agent_msg = ChatMessage(
            id=f"msg_{len(working_memory.messages)}",
            type=MessageType.HITL_REQUEST,
            content=hitl_info,
            sender="agent",
        )
        working_memory.add_message(agent_msg)

        return TurnResult(
            mode=ExecutionMode.AWAITING_HITL,
            response_text=response_text,
            task_tree=tree,
            hitl_task_id=hitl_info["task_id"],
            hitl_checkpoint=hitl_info["checkpoint"],
            agent_message=agent_msg,
        )

    def build_error_result(
        self, error: Union[str, TurnError], working_memory: "WorkingMemory"
    ) -> "TurnResult":
        """Build a TurnResult when an error occurs."""
        from homomics_lab.agent.turn_runner import ExecutionMode, TurnResult

        if isinstance(error, TurnError):
            payload = error.to_payload()
            recovery = payload["recovery_action"]
            response_text = f"抱歉，处理您的请求时出现了问题：{payload['message']}"
            if recovery == "retry":
                response_text += " 已自动重试一次仍未成功，请稍后再试或换一种方式描述。"
            elif recovery == "clarify":
                response_text += " 能否补充说明一下您的具体需求？"
            elif recovery == "approve":
                response_text += " 该操作需要您确认授权。"
        else:
            payload = {
                "error_type": "ExecutionError",
                "message": str(error),
                "recovery_action": "escalate",
                "retryable": False,
                "context": {},
            }
            response_text = f"抱歉，处理您的请求时出现了问题：{error}"

        agent_msg = ChatMessage(
            id=f"msg_{len(working_memory.messages)}",
            type=MessageType.ERROR,
            content={"error": payload, "message": response_text},
            sender="agent",
        )
        working_memory.add_message(agent_msg)

        return TurnResult(
            mode=ExecutionMode.ERROR,
            response_text=response_text,
            error=payload["message"],
            agent_message=agent_msg,
        )
