"""TurnState — state/context collaborator for the turn pipeline.

Merges the former ``turn_state_persistence``, ``turn_context_formatter`` and
``turn_file_resolver`` collaborators into one cognitively cohesive module:

- ``TurnStatePersistence`` — run the turn pipeline once (with retries) and
  persist turn state off the HTTP critical path.
- ``ContextFormatter`` — format MCP/science tool outputs and conversation
  context for prompts.
- ``FileReferenceResolver`` — resolve uploaded file mentions in user messages.

No runner back-reference: services that are never reassigned after
``TurnRunner`` construction are constructor-injected, the core pipeline is
injected as a callable, and the one piece of per-turn mutable state
(``extra_context``) is passed explicitly.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
    Union,
)

from homomics_lab.agent.errors import ExecutionError, TurnError
from homomics_lab.config import settings
from homomics_lab.context.relevance_filter import ContextItem
from homomics_lab.workspace.context import current_workspace
from homomics_lab.workspace.manager import WorkspaceManager

if TYPE_CHECKING:
    from homomics_lab.agent.turn_runner import TurnResult
    from homomics_lab.context.compressor import ContextCompressor
    from homomics_lab.context.memory_manager import MemoryManager
    from homomics_lab.context.project_state import ProjectStateManager
    from homomics_lab.context.working_memory import WorkingMemory
    from homomics_lab.plan.store import PlanStore
    from homomics_lab.tasks.task_tree import TaskTree

logger = logging.getLogger(__name__)


class TurnStatePersistence:
    """Run the turn pipeline once (with retries) and persist turn state.

    Persistence (long-term memory, project state, trace nodes) is best-effort
    and runs as a background task so it stays off the HTTP critical path.
    Tasks are chained per ``session_id`` so two turns of the same session can
    never write session state concurrently.
    """

    def __init__(
        self,
        *,
        run_turn_once: Callable[..., Awaitable["TurnResult"]],
        build_error_result: Callable[
            [Union[str, TurnError], "WorkingMemory"], "TurnResult"
        ],
        memory_manager: Optional["MemoryManager"] = None,
        project_state_manager: Optional["ProjectStateManager"] = None,
        trace_store: Optional[Any] = None,
    ):
        self._run_turn_once = run_turn_once
        self._build_error_result = build_error_result
        self._memory_manager = memory_manager
        self._project_state_manager = project_state_manager
        self._trace_store = trace_store
        # session_id -> latest scheduled persistence task (strong refs keep
        # fire-and-forget tasks alive; entries are removed on completion).
        self._background_tasks: Dict[str, asyncio.Task] = {}

    async def drain(self) -> None:
        """Await all currently scheduled background persistence tasks.

        Intended for tests and graceful shutdown; production request handling
        never waits on persistence.
        """
        tasks = list(self._background_tasks.values())
        if not tasks:
            return
        await asyncio.gather(*tasks, return_exceptions=True)

    async def run_with_state(
        self,
        session_id: str,
        user_message: str,
        working_memory: "WorkingMemory",
        project_id: str,
        task_tree: Optional["TaskTree"] = None,
        job_service=None,
        enqueue_skills: bool = False,
        plan_store: Optional["PlanStore"] = None,
        debate_response: Optional[Dict[str, Any]] = None,
        plan_mode: bool = False,
        trace_id: Optional[str] = None,
    ) -> "TurnResult":
        """Run the turn pipeline once and persist state."""
        turn_result: Optional[TurnResult] = None
        workspace_token = None
        if project_id:
            workspace = WorkspaceManager(settings.data_dir, project_id)
            workspace_token = current_workspace.set(workspace)
        try:
            turn_result = await self._run_turn_once(
                session_id=session_id,
                user_message=user_message,
                working_memory=working_memory,
                project_id=project_id,
                task_tree=task_tree,
                job_service=job_service,
                enqueue_skills=enqueue_skills,
                plan_store=plan_store,
                debate_response=debate_response,
                plan_mode=plan_mode,
            )
        except TurnError as exc:
            if exc.retryable:
                max_retries = 2
                for attempt in range(max_retries):
                    backoff = (2**attempt) * 0.5 + random.uniform(0, 0.25)
                    logger.warning(
                        "Retryable turn error, retrying in %.2fs: %s",
                        backoff,
                        exc,
                    )
                    await asyncio.sleep(backoff)
                    try:
                        turn_result = await self._run_turn_once(
                            session_id=session_id,
                            user_message=user_message,
                            working_memory=working_memory,
                            project_id=project_id,
                            task_tree=task_tree,
                            job_service=job_service,
                            enqueue_skills=enqueue_skills,
                            plan_store=plan_store,
                            debate_response=debate_response,
                            plan_mode=plan_mode,
                        )
                        break
                    except TurnError as exc2:
                        exc = exc2
                        if not exc2.retryable or attempt == max_retries - 1:
                            turn_result = self._build_error_result(
                                exc2, working_memory
                            )
                            break
                else:
                    turn_result = self._build_error_result(exc, working_memory)
            else:
                turn_result = self._build_error_result(exc, working_memory)
        except Exception as exc:
            # Wrap unexpected errors as ExecutionError for structured reporting.
            turn_result = self._build_error_result(
                ExecutionError(
                    str(exc), context={"exception_type": type(exc).__name__}
                ),
                working_memory,
            )
        finally:
            if workspace_token is not None:
                current_workspace.reset(workspace_token)

        turn_result = turn_result or self._build_error_result(
            ExecutionError("Turn produced no result"), working_memory
        )

        # Persist state off the critical path (fire-and-forget, best-effort).
        self._schedule_background_persistence(
            session_id=session_id,
            project_id=project_id,
            user_message=user_message,
            turn_result=turn_result,
            working_memory=working_memory,
            trace_id=trace_id,
        )

        return turn_result

    def _schedule_background_persistence(
        self,
        *,
        session_id: str,
        project_id: str,
        user_message: str,
        turn_result: "TurnResult",
        working_memory: "WorkingMemory",
        trace_id: Optional[str],
    ) -> None:
        """Schedule persistence as a background task chained per session.

        Chaining on the previous task for the same session guarantees
        in-order, non-concurrent writes of session state across turns.
        """
        prev = self._background_tasks.get(session_id)

        async def _chained() -> None:
            if prev is not None:
                try:
                    await prev
                except asyncio.CancelledError:
                    pass
                except Exception:
                    pass
            try:
                await self._persist_state(
                    session_id=session_id,
                    project_id=project_id,
                    user_message=user_message,
                    turn_result=turn_result,
                    working_memory=working_memory,
                    trace_id=trace_id,
                )
            except Exception:
                logger.warning("Background turn persistence failed", exc_info=True)

        task = asyncio.create_task(_chained())
        self._background_tasks[session_id] = task

        def _cleanup(done: asyncio.Task) -> None:
            # Only pop when this task is still the latest for the session.
            if self._background_tasks.get(session_id) is done:
                self._background_tasks.pop(session_id, None)

        task.add_done_callback(_cleanup)

    async def _persist_state(
        self,
        *,
        session_id: str,
        project_id: str,
        user_message: str,
        turn_result: "TurnResult",
        working_memory: "WorkingMemory",
        trace_id: Optional[str],
    ) -> None:
        """Persist turn state (memory, project state, trace). Best-effort."""

        # 5. Persist turn to long-term memory (best-effort)
        if self._memory_manager is not None and turn_result is not None:
            try:
                await self._memory_manager.persist_turn(
                    session_id=session_id,
                    project_id=project_id,
                    user_message=user_message,
                    turn_result=turn_result,
                    working_memory=working_memory,
                    task_tree=turn_result.task_tree,
                )
            except Exception:
                logger.warning(
                    "Failed to persist turn to memory", exc_info=True
                )

        # 6. Update structured project state (best-effort)
        if self._project_state_manager is not None and turn_result is not None:
            try:
                project_state = self._project_state_manager.load(project_id)
                project_state = self._project_state_manager.update_from_turn(
                    project_state,
                    task_tree=getattr(turn_result, "task_tree", None),
                    turn_result=turn_result,
                )
                self._project_state_manager.save(project_state)
            except Exception:
                logger.warning(
                    "Failed to update project state", exc_info=True
                )

        # Record a lightweight summary node in the execution trace.
        # add_node -> update_node has an ordering dependency, so both stay
        # sequential inside this single background task.
        if self._trace_store is not None and trace_id is not None:
            try:
                await self._trace_store.add_node(
                    trace_id=trace_id,
                    node_type="turn",
                    name="chat_turn",
                    metadata={
                        "mode": str(
                            turn_result.mode.value
                            if hasattr(turn_result.mode, "value")
                            else turn_result.mode
                        ),
                        "response_length": len(turn_result.response_text or ""),
                        "has_error": turn_result.error is not None,
                        "job_id": turn_result.job_id,
                        "plan_id": turn_result.plan_id,
                    },
                )
                await self._trace_store.update_node(
                    trace_id=trace_id,
                    node_id="root",
                    status="completed" if not turn_result.error else "failed",
                    outputs={
                        "response_preview": (turn_result.response_text or "")[:200]
                    },
                )
            except Exception:
                logger.warning("Failed to record turn trace node", exc_info=True)


class ContextFormatter:
    """Format tool outputs, extra context and working-memory history for prompts."""

    def __init__(self, compressor: Optional["ContextCompressor"] = None):
        self._compressor = compressor

    def working_memory_to_history(
        self, working_memory: "WorkingMemory"
    ) -> List[Dict[str, Any]]:
        """Convert recent working-memory messages to OpenAI-compatible history."""
        history: List[Dict[str, Any]] = []
        for msg in working_memory.get_recent_messages()[-10:]:
            if msg.sender == "user":
                role = "user"
            elif msg.sender == "agent":
                role = "assistant"
            else:
                continue
            content = msg.content
            if isinstance(content, dict):
                content = (
                    content.get("response_text") or content.get("text") or str(content)
                )
            if not isinstance(content, str):
                content = str(content)
            history.append({"role": role, "content": content})
        return history

    @staticmethod
    def summarize_mcp_result(
        tool_name: str,
        output: Any,
        tool_inputs: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Generate a useful text summary from an MCP tool output."""
        if not isinstance(output, dict):
            return f"{tool_name} 调用完成"

        error = output.get("error")
        if error:
            return f"工具返回错误：{error}"

        if tool_name == "pubmed_search":
            return ContextFormatter.format_pubmed_search(output, tool_inputs)
        if tool_name == "pubmed_fetch":
            return ContextFormatter.format_pubmed_fetch(output, tool_inputs)
        if tool_name == "science_search":
            return ContextFormatter.format_science_search(output, tool_inputs)
        if tool_name == "science_list_dbs":
            return ContextFormatter.format_science_dbs(output)

        count = output.get("count")
        if count is not None:
            return f"{tool_name} 返回 {count} 条结果"
        return f"{tool_name} 调用完成"

    @staticmethod
    def format_pubmed_search(
        output: Dict[str, Any],
        tool_inputs: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Format PubMed search results into a readable Markdown list."""
        from urllib.parse import quote

        query = ""
        if isinstance(tool_inputs, dict):
            query = tool_inputs.get("query", "") or ""
        count = output.get("count", "0")
        try:
            count_int = int(count)
        except (TypeError, ValueError):
            count_int = 0

        encoded_query = quote(query.encode("utf-8")) if query else ""
        pubmed_url = f"https://pubmed.ncbi.nlm.nih.gov/?term={encoded_query}"

        if count_int == 0:
            return (
                f"未找到与“{query}”相关的 PubMed 文献。\n\n"
                "建议：\n"
                "- 尝试用英文关键词或同义词；\n"
                "- 去掉过于具体的限定词，扩大检索范围；\n"
                "- 直接提供 PMID 或 DOI，我可以帮你解读。\n\n"
                f"[在 PubMed 中打开检索]({pubmed_url})"
            )

        articles = output.get("articles", []) or []
        lines = [f"找到 {count_int} 条相关文献，以下是前 {len(articles)} 条：\n"]
        for idx, article in enumerate(articles, start=1):
            if not isinstance(article, dict):
                continue
            title = article.get("title", "未知标题") or "未知标题"
            authors = article.get("authors", []) or []
            authors_str = ", ".join(authors[:3])
            if len(authors) > 3:
                authors_str += " et al."
            journal = article.get("journal", "") or ""
            pubdate = article.get("pubdate", "") or ""
            pmid = article.get("pmid", "") or ""
            doi = article.get("doi", "") or ""
            pmid_link = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""
            parts = [
                p
                for p in [authors_str, f"*{journal}*" if journal else "", pubdate]
                if p
            ]
            meta = " · ".join(parts)
            pmid_part = f" · PMID: [{pmid}]({pmid_link})" if pmid else ""
            doi_part = f" · DOI: {doi}" if doi else ""
            lines.append(f"{idx}. **{title}**  \n   {meta}{pmid_part}{doi_part}")

        lines.append(f"\n[在 PubMed 中查看全部结果]({pubmed_url})")
        return "\n".join(lines)

    @staticmethod
    def format_science_dbs(output: Dict[str, Any]) -> str:
        """Format the science database catalog into a readable list."""
        databases = output.get("databases", []) or []
        if not databases:
            return "当前没有可用的科学数据库连接器。"
        lines = ["可查询的科学数据库：\n"]
        for db in databases:
            if not isinstance(db, dict):
                continue
            name = db.get("name", "?")
            desc = db.get("description", "") or ""
            available = db.get("available", True)
            badge = "可用" if available else "不可用（缺少依赖或密钥）"
            suffix = f" — {desc}" if desc else ""
            lines.append(f"- **{name}** [{badge}]{suffix}")
        return "\n".join(lines)

    @staticmethod
    def format_science_search(
        output: Dict[str, Any],
        tool_inputs: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Format merged science_search results into a readable Markdown list."""
        query = ""
        if isinstance(tool_inputs, dict):
            query = tool_inputs.get("query", "") or ""
        results = output.get("results", []) or []
        databases = output.get("databases", []) or []
        errors = output.get("errors", {}) or {}

        if not results:
            hint = "、".join(databases) or "科学数据库"
            msg = f"在 {hint} 中未找到与“{query}”相关的结果。"
            if errors:
                msg += "\n\n部分来源返回错误：" + "; ".join(
                    f"{k}: {v}" for k, v in errors.items() if k != "_"
                )
            return msg

        lines = [
            f"检索到 {len(results)} 条结果（来源：{', '.join(databases) or '多库'}）：\n"
        ]
        for idx, hit in enumerate(results, start=1):
            if not isinstance(hit, dict):
                continue
            title = hit.get("title") or "Untitled"
            source = hit.get("source") or ""
            url = hit.get("url") or ""
            snippet = (hit.get("snippet") or "").strip().replace("\n", " ")
            if len(snippet) > 240:
                snippet = snippet[:240] + "…"
            published = hit.get("published") or ""
            meta = " · ".join(x for x in [source, published] if x)
            head = f"{idx}. **{title}**"
            if meta:
                head += f"  _{meta}_"
            lines.append(head)
            if snippet:
                lines.append(f"   {snippet}")
            if url:
                lines.append(f"   {url}")
        if errors:
            failed = [k for k in errors if k != "_"]
            if failed:
                lines.append("\n_部分来源失败： " + ", ".join(failed) + "_")
        return "\n".join(lines)

    @staticmethod
    def format_pubmed_fetch(
        output: Dict[str, Any],
        tool_inputs: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Format a fetched PubMed article into a readable summary."""
        # `pubmed_fetch` returns the article directly, not wrapped in an `articles` list.
        if isinstance(output, dict) and output.get("articles"):
            article = output["articles"][0]
        elif isinstance(output, dict) and output.get("pmid"):
            article = output
        else:
            return "未获取到 PubMed 文章详情。"
        if not isinstance(article, dict):
            return "PubMed 返回格式异常。"
        title = article.get("title", "未知标题") or "未知标题"
        abstract = article.get("abstract", "") or ""
        pmid = article.get("pmid", "") or ""
        pmid_link = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""
        lines = [f"**{title}**"]
        if pmid:
            lines.append(f"PMID: [{pmid}]({pmid_link})")
        if abstract:
            lines.append(f"\n{abstract}")
        return "\n".join(lines)

    def compress_working_memory(
        self, working_memory: "WorkingMemory", current_goal: str
    ) -> str:
        """Compress recent conversation history into a concise context string.

        Uses ContextCompressor to keep only the most relevant messages for the
        current user request. Falls back to the latest 6 raw messages if
        compression fails.
        """
        messages = working_memory.get_recent_messages()
        if not messages:
            return ""

        now = datetime.now(timezone.utc)
        items: List[ContextItem] = []
        for msg in messages:
            raw_content = msg.content
            if not isinstance(raw_content, str):
                try:
                    text = json.dumps(raw_content, ensure_ascii=False)
                except Exception:
                    text = str(raw_content)
            else:
                text = raw_content
            if not text.strip():
                continue
            hours = 0.0
            if msg.timestamp:
                try:
                    hours = (now - msg.timestamp).total_seconds() / 3600.0
                except Exception:
                    hours = 0.0
            items.append(
                ContextItem(
                    content=f"{msg.sender}: {text}",
                    type=msg.type.value,
                    is_pinned=msg.id in working_memory.pinned_items,
                    is_upstream_result=bool(msg.task_id),
                    agent_importance=0.7 if msg.sender == "agent" else 0.5,
                    hours_since_created=hours,
                )
            )

        try:
            compressed = self._compressor.compress(items, current_goal=current_goal)
        except Exception:
            compressed = items[-6:]

        return "\n".join(item.content for item in compressed)

    def format_extra_context(self, extra_context: Optional[Dict[str, Any]]) -> str:
        """Render CBKB/semantic-memory enrichment into a short project context string.

        ``extra_context`` is per-turn mutable state, so it is passed explicitly
        rather than read off the runner.
        """
        if not extra_context:
            return ""
        parts: List[str] = []
        snippets = extra_context.get("memory_snippets") or []
        if snippets:
            parts.append(
                "Relevant memory snippets:\n"
                + "\n".join(f"- {s}" for s in snippets[:3])
            )
        experiments = extra_context.get("recent_experiments") or []
        if experiments:
            parts.append(
                "Recent experiments:\n"
                + "\n".join(
                    f"- {e.get('bundle_id', '')}: {e.get('summary', '')}"
                    for e in experiments[:3]
                )
            )
        sops = extra_context.get("recent_sops") or []
        if sops:
            parts.append(
                "Relevant SOPs:\n"
                + "\n".join(
                    f"- {s.get('name', '')} ({s.get('category', '')})" for s in sops[:3]
                )
            )
        anomalies = extra_context.get("recent_anomalies") or []
        if anomalies:
            parts.append(
                "Recent anomalies:\n"
                + "\n".join(
                    f"- {a.get('phase_type', '')}: {a.get('summary', '')}"
                    for a in anomalies[:3]
                )
            )
        return "\n\n".join(parts)


class FileReferenceResolver:
    """Resolve bare filenames in user messages and attach them to task trees."""

    def resolve_uploaded_file_references(
        self,
        user_message: Optional[str],
        project_id: str,
    ) -> List[Tuple[str, str]]:
        """Find bare filenames in the message that exist as uploaded project files.

        Returns a list of ``(filename, resolved_path)`` tuples. Both the project
        raw directory and the workspace data directory are checked so files
        uploaded via the file API are discoverable without explicit ``@file:``
        references.
        """
        if not user_message:
            return []

        candidates = re.findall(r"[\w\-\.]+\.\w{2,8}", user_message)
        seen: set[str] = set()
        resolved: List[Tuple[str, str]] = []

        for candidate in candidates:
            filename = Path(candidate).name
            if filename in seen or not filename:
                continue
            seen.add(filename)

            for base in (
                settings.data_dir / "raw" / project_id,
                settings.data_dir / "workspaces" / project_id / "data",
            ):
                candidate_path = base / filename
                if candidate_path.is_file():
                    resolved.append((filename, str(candidate_path.resolve())))
                    break

        return resolved

    def attach_uploaded_files_to_tree(
        self,
        tree: "TaskTree",
        user_message: Optional[str],
        project_id: str,
    ) -> None:
        """Inject request context and uploaded file paths into task parameters.

        This lets skills/agents know the concrete user objective and which files
        it refers to, even when the message only mentions a filename without an
        ``@file:`` reference. For single-step skills the file is usually the
        primary input; for workflows it is added as a fallback when a task does
        not already specify an input file.
        """
        files = self.resolve_uploaded_file_references(user_message, project_id)
        primary_path = files[0][1] if files else None
        for task in tree.tasks:
            if task.parameters is None:
                task.parameters = {}
            if user_message and "user_request" not in task.parameters:
                task.parameters["user_request"] = user_message
            if primary_path and "input_file" not in task.parameters:
                task.parameters["input_file"] = primary_path
            # Also expose the full list for multi-file tasks.
            if files and "uploaded_files" not in task.parameters:
                task.parameters["uploaded_files"] = [
                    {"filename": name, "path": path} for name, path in files
                ]


class TurnState:
    """Facade over the state/context collaborators of the turn pipeline.

    Groups :class:`TurnStatePersistence`, :class:`ContextFormatter` and
    :class:`FileReferenceResolver` behind a single entry point so
    ``TurnRunner`` holds one state collaborator instead of three.
    """

    def __init__(
        self,
        *,
        run_turn_once: Callable[..., Awaitable["TurnResult"]],
        build_error_result: Callable[
            [Union[str, TurnError], "WorkingMemory"], "TurnResult"
        ],
        memory_manager: Optional["MemoryManager"] = None,
        project_state_manager: Optional["ProjectStateManager"] = None,
        trace_store: Optional[Any] = None,
        compressor: Optional["ContextCompressor"] = None,
    ):
        self._persistence = TurnStatePersistence(
            run_turn_once=run_turn_once,
            build_error_result=build_error_result,
            memory_manager=memory_manager,
            project_state_manager=project_state_manager,
            trace_store=trace_store,
        )
        self._formatter = ContextFormatter(compressor=compressor)
        self._file_resolver = FileReferenceResolver()

    # --- TurnStatePersistence --------------------------------------------

    async def drain(self) -> None:
        return await self._persistence.drain()

    async def run_with_state(
        self,
        session_id: str,
        user_message: str,
        working_memory: "WorkingMemory",
        project_id: str,
        task_tree: Optional["TaskTree"] = None,
        job_service=None,
        enqueue_skills: bool = False,
        plan_store: Optional["PlanStore"] = None,
        debate_response: Optional[Dict[str, Any]] = None,
        plan_mode: bool = False,
        trace_id: Optional[str] = None,
    ) -> "TurnResult":
        return await self._persistence.run_with_state(
            session_id=session_id,
            user_message=user_message,
            working_memory=working_memory,
            project_id=project_id,
            task_tree=task_tree,
            job_service=job_service,
            enqueue_skills=enqueue_skills,
            plan_store=plan_store,
            debate_response=debate_response,
            plan_mode=plan_mode,
            trace_id=trace_id,
        )

    # --- ContextFormatter -------------------------------------------------

    def working_memory_to_history(
        self, working_memory: "WorkingMemory"
    ) -> List[Dict[str, Any]]:
        return self._formatter.working_memory_to_history(working_memory)

    def summarize_mcp_result(
        self,
        tool_name: str,
        output: Any,
        tool_inputs: Optional[Dict[str, Any]] = None,
    ) -> str:
        return self._formatter.summarize_mcp_result(tool_name, output, tool_inputs)

    def format_pubmed_search(
        self,
        output: Dict[str, Any],
        tool_inputs: Optional[Dict[str, Any]] = None,
    ) -> str:
        return self._formatter.format_pubmed_search(output, tool_inputs)

    def format_science_dbs(self, output: Dict[str, Any]) -> str:
        return self._formatter.format_science_dbs(output)

    def format_science_search(
        self,
        output: Dict[str, Any],
        tool_inputs: Optional[Dict[str, Any]] = None,
    ) -> str:
        return self._formatter.format_science_search(output, tool_inputs)

    def format_pubmed_fetch(
        self,
        output: Dict[str, Any],
        tool_inputs: Optional[Dict[str, Any]] = None,
    ) -> str:
        return self._formatter.format_pubmed_fetch(output, tool_inputs)

    def compress_working_memory(
        self, working_memory: "WorkingMemory", current_goal: str
    ) -> str:
        return self._formatter.compress_working_memory(working_memory, current_goal)

    def format_extra_context(self, extra_context: Optional[Dict[str, Any]]) -> str:
        return self._formatter.format_extra_context(extra_context)

    # --- FileReferenceResolver ---------------------------------------------

    def resolve_uploaded_file_references(
        self,
        user_message: Optional[str],
        project_id: str,
    ) -> List[Tuple[str, str]]:
        return self._file_resolver.resolve_uploaded_file_references(
            user_message, project_id
        )

    def attach_uploaded_files_to_tree(
        self,
        tree: "TaskTree",
        user_message: Optional[str],
        project_id: str,
    ) -> None:
        return self._file_resolver.attach_uploaded_files_to_tree(
            tree, user_message, project_id
        )
