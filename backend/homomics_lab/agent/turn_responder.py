"""TurnResponder — response-generation collaborator for the turn pipeline.

Merges the former ``turn_response_generator``, ``turn_result_assembler``,
``turn_clarification`` and ``turn_viz_handler`` collaborators into one
cognitively cohesive module:

- ``ResponseGenerator`` — greeting, QA, help and information responses.
- ``ResultAssembler`` — TurnResult objects for workflow/HITL/fallback/error
  outcomes, artifact envelopes, plot chat messages.
- ``ClarificationHandler`` — clarification questions and debate resolution.
- ``VisualizationEditHandler`` — natural-language edits to the latest plot.

No runner back-reference: services that are never reassigned after
``TurnRunner`` construction are constructor-injected, the lazily-built LLM
client is injected as a provider callable, and per-turn mutable state arrives
via an explicit ``ctx`` dict with the keys ``session_id``, ``project_id``,
``request_id``, ``event_callback``, ``extra_context`` and ``context_bundle``.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Union,
)

from homomics_lab.agent.errors import TurnError
from homomics_lab.agent.intent.models import IntentMatch
from homomics_lab.agent.intent_analyzer import UserIntent
from homomics_lab.context.working_memory import WorkingMemory
from homomics_lab.llm_client import LLMClient
from homomics_lab.models.common import ChatMessage, MessageType
from homomics_lab.plots import extract_plot_attachments
from homomics_lab.prompts import render_prompt
from homomics_lab.viz.edit_engine import PlotlyEditEngine

if TYPE_CHECKING:
    from homomics_lab.agent.intent_analyzer import IntentAnalyzer
    from homomics_lab.agent.turn_runner import TurnResult
    from homomics_lab.agent.turn_state import TurnState
    from homomics_lab.context.project_state import ProjectStateManager
    from homomics_lab.context.prompter import Prompter
    from homomics_lab.tasks.task_tree import TaskTree
    from homomics_lab.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class ResponseGenerator:
    """Generate direct text responses for greeting, QA, help and information intents."""

    def __init__(
        self,
        *,
        state: "TurnState",
        llm_client_provider: Callable[[], Optional[LLMClient]],
        tool_registry: Optional["ToolRegistry"] = None,
        prompter: Optional["Prompter"] = None,
        project_state_manager: Optional["ProjectStateManager"] = None,
    ):
        self._state = state
        self._llm_client_provider = llm_client_provider
        self._tool_registry = tool_registry
        self._prompter = prompter
        self._project_state_manager = project_state_manager

    async def generate_general_help_response(
        self,
        user_message: str,
        working_memory: WorkingMemory,
        ctx: Dict[str, Any],
    ) -> str:
        """Generate a code/explanation response for general help requests.

        Uses Prompter with compressed conversation history and CBKB-enriched
        project context. Falls back to a safe template response if LLM is not
        configured or fails.
        """
        llm = LLMClient()
        if not llm.is_configured():
            return (
                "我可以帮您写代码或解释数据处理逻辑，但需要配置 LLM 才能生成具体代码。\n"
                "请设置 OPENAI_API_KEY，或告诉我您想处理什么数据，我会尽量给出建议。"
            )

        context_bundle = ctx.get("context_bundle")
        if context_bundle is not None:
            # Use the already assembled, token-safe context from ContextEngine.
            messages = context_bundle.to_prompt(user_message)
            # Keep only system/assistant messages; the user message will be appended below.
            prompt_messages = [m for m in messages if m.get("role") != "user"]
            prompt_messages.append({"role": "user", "content": user_message})
        else:
            compressed_history = self._state.compress_working_memory(
                working_memory, user_message
            )
            extra_context = self._state.format_extra_context(ctx.get("extra_context"))
            project_context = "\n\n".join(
                filter(None, [compressed_history, extra_context])
            )

            prompt = self._prompter.build_prompt(
                user_message=user_message,
                working_memory=WorkingMemory(max_messages=0),
                project_context=project_context,
                mode="analysis",
            )
            prompt_messages = [{"role": "user", "content": prompt}]

        try:
            return await llm.chat_completion(
                messages=prompt_messages,
                temperature=0.2,
                max_tokens=1500,
                session_id=ctx.get("session_id"),
                project_id=ctx.get("project_id"),
                request_id=f"{ctx.get('request_id') or 'code'}_code",
            )
        except Exception:
            return (
                "我目前无法调用 LLM 生成代码。请检查 OPENAI_API_KEY 配置，"
                "或把需求拆分成更具体的步骤。"
            )

    async def generate_direct_response_via_llm(
        self,
        response_type: str,
        user_message: str,
        intent: UserIntent,
        working_memory: WorkingMemory,
        project_id: Optional[str] = None,
        max_tokens: Optional[int] = None,
        ctx: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Generate a greeting/QA/information direct response via the configured LLM.

        Falls back to static templates when the LLM client is unavailable or fails.
        """
        ctx = ctx or {}
        llm_client = self._llm_client_provider()
        if llm_client is None:
            return None

        # Layered system prompt from the prompt registry (base + domain + mode).
        mode_map = {
            "greeting": "base",
            "qa": "qa",
            "information_request": "qa",
        }

        base_prompt = render_prompt("system.base", domain=intent.domain, combine=True)
        if base_prompt is None:
            base_prompt = (
                "You are HomomicsLab, an AI assistant specialized in bioinformatics and computational biology. "
                "You have access to project context, SOPs, CBKB knowledge, and executable skills/workflows."
            )

        mode_prompt = render_prompt(
            f"system.{mode_map.get(response_type, 'qa')}",
            domain=intent.domain,
            combine=True,
        )

        response_type_instructions = {
            "greeting": (
                "Greet the user warmly and briefly introduce HomomicsLab. "
                "Mention that you can help with bioinformatics analysis, "
                "experiment design, code snippets, and workflow building."
            ),
            "qa": (
                "Answer the user's question accurately in a bioinformatics context. "
                "When project context, SOPs, or skills are relevant, use them to give "
                "actionable HomomicsLab-specific guidance rather than a generic answer."
            ),
            "information_request": (
                "Explain what HomomicsLab can do for the requested domain. List relevant "
                "analysis steps, SOPs, and executable skills when known, and offer to run "
                "them for the user. Keep the response structured and actionable."
            ),
        }

        parts = [base_prompt]
        if mode_prompt:
            parts.append(mode_prompt)
        parts.append(
            f"Task type: {response_type}\n"
            f"Instructions: {response_type_instructions.get(response_type, response_type_instructions['qa'])}\n\n"
            "Use the provided context and intent, but do not mention internal fields or system internals."
        )
        system_prompt = "\n\n".join(parts)

        messages: List[Dict[str, str]] = []

        context_bundle = ctx.get("context_bundle")
        if context_bundle is not None:
            # The ContextEngine already assembles token-safe project state, CBKB
            # retrieval, semantic memory, and conversation history. Prepend our
            # direct-response system instruction so the model knows how to answer.
            messages = context_bundle.to_prompt(user_message)
            messages.insert(0, {"role": "system", "content": system_prompt})
        else:
            # Fallback minimal context when the context engine is not used.
            context_parts: List[str] = [
                f"Intent: type={intent.intent_type or 'general'}, domain={intent.domain or 'none'}, "
                f"mode={intent.interaction_mode}, confidence={intent.confidence:.2f}"
            ]
            recent_messages = working_memory.get_recent_messages()[-6:]
            if recent_messages:
                history_lines = []
                for msg in recent_messages:
                    content = msg.content
                    if not isinstance(content, str):
                        try:
                            content = json.dumps(content, ensure_ascii=False)
                        except Exception:
                            content = str(content)
                    history_lines.append(f"{msg.sender}: {content}")
                context_parts.append(
                    "Recent conversation:\n" + "\n".join(history_lines)
                )

            if self._project_state_manager is not None and project_id is not None:
                try:
                    project_state = self._project_state_manager.load(project_id)
                    context_parts.append(project_state.to_prompt_text())
                except Exception:
                    logger.debug(
                        "Failed to load project state for LLM direct response",
                        exc_info=True,
                    )

            context_text = "\n\n".join(context_parts)
            messages = [{"role": "system", "content": system_prompt}]
            if context_text:
                messages.append({"role": "system", "content": context_text})
            messages.append({"role": "user", "content": user_message})

        type_max_tokens = {"greeting": 800, "qa": 2000, "information_request": 2000}
        resolved_max_tokens = max_tokens or type_max_tokens.get(response_type, 2000)

        # Streaming branch: when the turn carries an event callback (frontend
        # listening on the session WebSocket), stream tokens live. The
        # accumulated text is the same string the one-shot call would return.
        event_callback = ctx.get("event_callback")
        if event_callback is not None:
            try:
                chunks: List[str] = []
                async for token in llm_client.chat_completion_stream(
                    messages=messages,
                    temperature=0.3,
                    max_tokens=resolved_max_tokens,
                ):
                    chunks.append(token)
                    await event_callback({"type": "answer_token", "token": token})
                await event_callback({"type": "answer_done"})
                return "".join(chunks)
            except Exception:
                logger.warning(
                    "LLM streaming direct response failed for type %s; "
                    "falling back to one-shot completion",
                    response_type,
                    exc_info=True,
                )
                try:
                    await event_callback({"type": "answer_reset"})
                except Exception:
                    pass

        try:
            return await llm_client.chat_completion(
                messages=messages,
                temperature=0.3,
                max_tokens=resolved_max_tokens,
                session_id=ctx.get("session_id"),
                project_id=ctx.get("project_id"),
                request_id=f"{ctx.get('request_id') or 'direct'}_direct",
            )
        except Exception:
            logger.warning(
                "LLM direct response failed for type %s; using fallback",
                response_type,
                exc_info=True,
            )
            return None

    async def generate_greeting_response(
        self,
        user_message: str,
        working_memory: WorkingMemory,
        project_id: Optional[str] = None,
        ctx: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Return a friendly self-introduction for greeting intents.

        Uses the configured LLM when available for a warmer, context-aware greeting;
        falls back to a static template if no LLM is configured or the call fails.
        """
        greeting_intent = UserIntent(
            intent_type="greeting",
            interaction_mode="answer",
            scope="single_step",
            original_message=user_message,
        )
        llm_response = await self.generate_direct_response_via_llm(
            response_type="greeting",
            user_message=user_message,
            intent=greeting_intent,
            working_memory=working_memory,
            project_id=project_id,
            ctx=ctx,
        )
        if llm_response:
            return llm_response

        return (
            "Hello! I'm **HomomicsLab**, your AI assistant specialized in bioinformatics "
            "and computational biology.\n\n"
            "I can help you with:\n"
            "- Bioinformatics analysis (genomics, transcriptomics, single-cell, proteomics, etc.)\n"
            "- Experimental design and statistical frameworks\n"
            "- Code snippets in Python, R, bash, SQL, Nextflow, Snakemake, and WDL\n"
            "- Workflow building, automation, reproducibility, and HPC/cloud optimization\n\n"
            "What project or analysis can I help you with today?"
        )

    async def generate_qa_response(
        self,
        intent: UserIntent,
        user_message: str,
        working_memory: WorkingMemory,
        project_id: Optional[str] = None,
        ctx: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Generate a direct text response for QA-style queries.

        Uses the configured LLM when available; falls back to domain-specific
        Chinese templates.
        """
        llm_response = await self.generate_direct_response_via_llm(
            response_type="qa",
            user_message=user_message,
            intent=intent,
            working_memory=working_memory,
            project_id=project_id,
            ctx=ctx,
        )
        if llm_response:
            return llm_response

        domain = intent.domain or intent.intent_type or "general"
        qa_responses = {
            "single-cell-transcriptomics": (
                "单细胞测序（scRNA-seq）是一种在单个细胞水平上分析基因表达的技术。"
                "它可以揭示细胞异质性，发现稀有细胞类型，并追踪细胞发育轨迹。"
            ),
            "spatial-transcriptomics": (
                "空间转录组学结合了基因表达分析和空间位置信息，"
                "可以在组织切片上绘制基因表达图谱。"
            ),
            "metagenomics": (
                "宏基因组学通过直接提取环境样本中全部微生物基因组 DNA，"
                "研究群落组成、功能和多样性，无需培养。"
            ),
            "genomics": (
                "基因组学是对生物体全部 DNA 的研究，包括变异检测、结构变异、"
                "功能注释等分析内容。"
            ),
            "transcriptomics": (
                "转录组学研究细胞或组织中全部 RNA 分子的表达情况，"
                "常用于差异表达、通路富集等分析。"
            ),
            "proteomics": (
                "蛋白质组学是对生物体全部蛋白质的研究，包括蛋白鉴定、定量、"
                "翻译后修饰等分析。"
            ),
            "epigenomics": (
                "表观基因组学研究不改变 DNA 序列的遗传调控机制，"
                "如 DNA 甲基化、组蛋白修饰、染色质可及性等。"
            ),
            "file_conversion": (
                "我可以帮您转换常见的生物信息学数据格式，"
                "如 CSV、h5ad、10x Genomics 格式等。"
            ),
            "general": (
                "我是一个生物信息学分析助手，可以帮您进行单细胞分析、"
                "空间转录组分析、实验设计等任务。请问有什么具体需求？"
            ),
        }
        if domain in qa_responses and domain != "general":
            return qa_responses[domain]

        # No domain-specific template: try a web search fallback when no LLM is
        # available, so general real-time questions (weather, news, etc.) still
        # get a useful answer.
        search_response = await self.try_web_search_response(user_message)
        if search_response:
            return search_response

        return qa_responses["general"]

    async def try_web_search_response(self, user_message: str) -> Optional[str]:
        """Fallback to a web search summary when no LLM or domain template is available.

        Only runs if the ``web_search`` builtin tool is registered and returns
        results. Network failures or missing dependencies are silently ignored so
        the caller can fall back to the generic template.
        """
        if not self._tool_registry:
            return None

        web_tools = [t for t in self._tool_registry.list_by_source("builtin") if t.name == "web_search"]
        if not web_tools:
            return None

        try:
            result = await self._tool_registry.invoke_async(
                "web_search", {"query": user_message, "num_results": 3}
            )
            if not result.success or not result.output:
                return None

            results = result.output
            if not isinstance(results, list) or not results:
                return None

            lines: List[str] = []
            for r in results[:3]:
                title = r.get("title", "").strip()
                href = r.get("href", "").strip()
                body = r.get("body", "").strip()
                if not title and not body:
                    continue
                snippet = body[:200] + "..." if len(body) > 200 else body
                lines.append(f"- **{title}**\n  {snippet}\n  {href}")

            if not lines:
                return None

            return "我查到了一些相关信息：\n\n" + "\n\n".join(lines)
        except Exception:
            return None

    async def generate_information_request_response(
        self,
        intent: UserIntent,
        working_memory: WorkingMemory,
        project_id: Optional[str] = None,
        ctx: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Respond to "what can you do / what are the steps" style queries.

        Uses the configured LLM when available; falls back to step-by-step
        Chinese templates.
        """
        llm_response = await self.generate_direct_response_via_llm(
            response_type="information_request",
            user_message=intent.original_message or "",
            intent=intent,
            working_memory=working_memory,
            project_id=project_id,
            ctx=ctx,
        )
        if llm_response:
            return llm_response

        domain = intent.domain
        if domain == "single-cell-transcriptomics":
            return (
                "单细胞转录组分析通常包括以下主要步骤：\n"
                "1. 数据质控（QC）：过滤低质量细胞和基因；\n"
                "2. 标准化与归一化；\n"
                "3. 高变基因选择；\n"
                "4. 降维（PCA、UMAP/t-SNE）；\n"
                "5. 聚类与细胞类型注释；\n"
                "6. 差异表达分析；\n"
                "7. 通路富集与可视化。\n\n"
                "您可以上传数据后，让我直接帮您跑完整流程或只做其中某一步。"
            )
        if domain == "spatial-transcriptomics":
            return (
                "空间转录组分析通常包括以下主要步骤：\n"
                "1. 数据加载与质控；\n"
                "2. 空间坐标与表达矩阵整合；\n"
                "3. 降维与聚类；\n"
                "4. 空间可变基因分析；\n"
                "5. 组织区域注释与细胞类型去卷积；\n"
                "6. 可视化（spot/细胞空间表达图）。\n\n"
                "请上传数据或告诉我您想重点关注的空间生物学问题。"
            )
        if domain == "metagenomics":
            return (
                "宏基因组分析通常包括以下主要步骤：\n"
                "1. 原始数据质控与去宿主；\n"
                "2. 序列拼接与基因预测；\n"
                "3. 物种注释与分类；\n"
                "4. 功能注释（KEGG/GO/CAZy 等）；\n"
                "5. Alpha/Beta 多样性分析；\n"
                "6. 差异物种/功能分析。\n\n"
                "您可以提供原始测序数据或 OTU/ASV 表，让我帮您分析。"
            )
        return (
            "HomomicsLab 支持多种生物信息学分析，包括：\n"
            "- 单细胞转录组分析（质控、聚类、差异表达、细胞注释等）\n"
            "- 空间转录组分析\n"
            "- 宏基因组/微生物组分析\n"
            "- 基因组、转录组、蛋白质组、表观组分析\n"
            "- 文献检索（PubMed）、蛋白查询（UniProt）、数据集查询（GEO）\n"
            "- 代码/脚本生成与数据处理帮助\n\n"
            "请告诉我您想进行哪类分析，或上传数据让我开始。"
        )


class ResultAssembler:
    """Assemble TurnResult instances for workflow, HITL, fallback and error outcomes."""

    @staticmethod
    def single_skill_id(tree: "TaskTree") -> Optional[str]:
        ids = [t.skills_required[0] for t in tree.tasks if t.skills_required]
        return ids[0] if len(ids) == 1 else None

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

    @staticmethod
    def extract_plot_messages(
        results: Dict[str, Any],
        tree: "TaskTree",
        working_memory: "WorkingMemory",
    ) -> List[ChatMessage]:
        """Scan execution results for plot outputs and build chat messages."""
        messages: List[ChatMessage] = []
        task_lookup = {t.id: t for t in tree.tasks}
        base_id = len(working_memory.messages)

        for task_id, result in results.items():
            if not isinstance(result, dict):
                continue

            skill_output = result.get("result", {})
            if not isinstance(skill_output, dict):
                continue

            task = task_lookup.get(task_id)
            skill_id = result.get("skill") or (
                task.skills_required[0] if task and task.skills_required else None
            )

            plot_type = skill_output.get("plot_type") or (
                task.name if task else "visualization"
            )
            attachments = extract_plot_attachments(
                skill_output,
                default_plot_type=plot_type,
                default_title=f"{plot_type} visualization",
            )

            for attachment in attachments:
                msg = ChatMessage(
                    id=f"msg_{base_id}",
                    type=MessageType.PLOT_DATA if attachment.data else MessageType.PLOT,
                    content=attachment.to_chat_content(),
                    sender="agent",
                    task_id=task_id,
                    skill_id=skill_id,
                )
                base_id += 1
                messages.append(msg)

        return messages

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
        summary_md = self.summarize(envelopes, user_message, self.single_skill_id(tree))
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


class ClarificationHandler:
    """Build clarification questions and resolve debate choices into intents."""

    def __init__(self, intent_analyzer: "IntentAnalyzer"):
        self._intent_analyzer = intent_analyzer

    def handle_clarification(
        self,
        intent: "UserIntent",
        working_memory: "WorkingMemory",
    ) -> "TurnResult":
        """Return a clarification question or debate request to the user.

        The DEBATE_REQUEST card is reserved for the case the debate is meant
        for: multiple candidate options *and* a grounded recommendation from
        the expert panel. When the debate ran but produced no recommendation
        (e.g. an empty or generalist panel that scores every option equally),
        the turn degrades to a plain-text question — the card would otherwise
        surface on every clarification with no actual guidance behind it.
        """
        from homomics_lab.agent.turn_runner import ExecutionMode, TurnResult

        debate_data = intent.metadata.get("debate")
        if (
            debate_data
            and debate_data.get("options")
            and debate_data.get("recommendation")
        ):
            agent_msg = ChatMessage(
                id=f"msg_{len(working_memory.messages)}",
                type=MessageType.DEBATE_REQUEST,
                content={
                    "debate_id": f"debate_{intent.original_message or 'clarify'}",
                    "topic": debate_data.get("topic", "请选择最符合您需求的选项"),
                    "options": debate_data.get("options", []),
                    "recommendation": debate_data.get("recommendation"),
                    "round_summaries": debate_data.get("round_summaries", []),
                },
                sender="agent",
            )
            working_memory.add_message(agent_msg)
            return TurnResult(
                mode=ExecutionMode.AWAITING_DEBATE,
                response_text=agent_msg.content["topic"],
                agent_message=agent_msg,
            )

        question = intent.metadata.get("clarification_question")
        if not question and debate_data and debate_data.get("options"):
            # No recommendation and no prepared question: still present the
            # candidate options as plain text so the user can pick one.
            option_lines = [
                f"- {opt.get('label') or opt.get('id')}"
                for opt in debate_data["options"]
            ]
            question = (
                "我不太确定您的需求，您是想要：\n"
                + "\n".join(option_lines)
                + "\n\n请告诉我更具体一些。"
            )
        if not question:
            question = "我不太确定您的需求，请再具体描述一下。"

        agent_msg = ChatMessage(
            id=f"msg_{len(working_memory.messages)}",
            type=MessageType.TEXT,
            content=question,
            sender="agent",
        )
        working_memory.add_message(agent_msg)

        return TurnResult(
            mode=ExecutionMode.DIRECT_RESPONSE,
            response_text=question,
            agent_message=agent_msg,
        )

    def build_debate_resolved_intent(
        self,
        debate_response: Dict[str, Any],
        user_message: str,
    ) -> "UserIntent":
        """Convert a user's debate choice into a concrete intent."""
        choice_id = debate_response.get("choice_id", "")
        return self._intent_analyzer._to_user_intent(
            IntentMatch(
                analysis_type=choice_id,
                confidence=1.0,
                source="debate",
                reason="user selected debate option",
            ),
            user_message,
        )


class VisualizationEditHandler:
    """Handle ``visualization_edit`` intents by editing the latest plot."""

    # Message types that may carry a renderable figure.
    _PLOT_MESSAGE_TYPES = (MessageType.PLOT_DATA, MessageType.PLOT)

    def __init__(self, _ignored: Any = None):
        # ``turn_intent_router`` (frozen by another task) still constructs this
        # handler with the runner as a positional argument; the argument is
        # accepted for compatibility and ignored — the handler needs no
        # runner state.
        pass

    async def handle(
        self,
        user_message: str,
        working_memory: "WorkingMemory",
        project_id: str,
        intent: Optional["UserIntent"] = None,
    ) -> "TurnResult":
        """Apply a natural-language edit to the most recent plot.

        Args:
            user_message: The raw user request (e.g. "把颜色改成蓝色").
            working_memory: Current session working memory.
            project_id: Active project identifier.
            intent: The classified ``visualization_edit`` intent (optional).

        Returns:
            ``TurnResult`` containing the edited plot as a ``PLOT_DATA`` message,
            or a text fallback when no recent plot exists or the edit cannot be
            applied deterministically.
        """
        from homomics_lab.agent.turn_runner import ExecutionMode, TurnResult

        latest_plot = self._find_latest_plot_message(working_memory)
        if latest_plot is None:
            return self._fallback_result(
                "我找不到最近的图，无法进行修改。请先生成一张图后再试试。",
                working_memory,
            )

        original_content = latest_plot.content
        if not isinstance(original_content, dict):
            return self._fallback_result(
                "当前图的消息格式不支持直接编辑。",
                working_memory,
            )

        # ``PLOT_DATA`` content is ``{plot_type, title, caption, data, layout}``,
        # which is already a valid Plotly figure with extra top-level metadata.
        figure = original_content

        if not figure.get("data"):
            return self._fallback_result(
                "我只支持编辑交互式 Plotly 图表，当前图无法直接修改。",
                working_memory,
            )

        edited_figure = PlotlyEditEngine.apply(user_message, figure)
        if edited_figure is None:
            return self._fallback_result(
                "我理解了您的改图意图，但暂时无法自动应用这个修改。",
                working_memory,
            )

        new_content: Dict[str, Any] = {
            **original_content,
            "data": edited_figure["data"],
            "layout": edited_figure["layout"],
        }
        # Preserve the plot_type if it was stored at the top level.
        if "plot_type" in original_content:
            new_content["plot_type"] = original_content["plot_type"]
        if "title" in original_content:
            new_content["title"] = edited_figure["layout"].get("title", original_content["title"])

        plot_msg = ChatMessage(
            id=f"msg_{len(working_memory.messages)}",
            type=MessageType.PLOT_DATA,
            content=new_content,
            sender="agent",
            task_id=latest_plot.task_id,
            skill_id=latest_plot.skill_id,
        )
        working_memory.add_message(plot_msg)

        return TurnResult(
            mode=ExecutionMode.DIRECT_RESPONSE,
            response_text="已按您的要求更新图表。",
            agent_message=plot_msg,
            attachments=[plot_msg],
        )

    def _find_latest_plot_message(
        self, working_memory: "WorkingMemory"
    ) -> Optional[ChatMessage]:
        """Return the most recent plot or plot_data message, if any."""
        for msg in reversed(list(working_memory.messages)):
            try:
                if MessageType(msg.type) in self._PLOT_MESSAGE_TYPES:
                    return msg
            except Exception:
                continue
        return None

    def _fallback_result(
        self, response_text: str, working_memory: "WorkingMemory"
    ) -> "TurnResult":
        """Return a text-only result when the edit cannot be applied."""
        from homomics_lab.agent.turn_runner import ExecutionMode, TurnResult

        msg = ChatMessage(
            id=f"msg_{len(working_memory.messages)}",
            type=MessageType.TEXT,
            content=response_text,
            sender="agent",
        )
        working_memory.add_message(msg)
        return TurnResult(
            mode=ExecutionMode.DIRECT_RESPONSE,
            response_text=response_text,
            agent_message=msg,
        )


class TurnResponder:
    """Facade over the response-generation collaborators of the turn pipeline.

    Groups :class:`ResponseGenerator`, :class:`ResultAssembler`,
    :class:`ClarificationHandler` and :class:`VisualizationEditHandler` behind
    a single entry point so ``TurnRunner`` holds one responder collaborator
    instead of four.
    """

    def __init__(
        self,
        *,
        state: "TurnState",
        intent_analyzer: "IntentAnalyzer",
        llm_client_provider: Callable[[], Optional[LLMClient]],
        tool_registry: Optional["ToolRegistry"] = None,
        prompter: Optional["Prompter"] = None,
        project_state_manager: Optional["ProjectStateManager"] = None,
    ):
        self._response_generator = ResponseGenerator(
            state=state,
            llm_client_provider=llm_client_provider,
            tool_registry=tool_registry,
            prompter=prompter,
            project_state_manager=project_state_manager,
        )
        self._result_assembler = ResultAssembler()
        self._clarification_handler = ClarificationHandler(
            intent_analyzer=intent_analyzer
        )

    # --- ResponseGenerator -------------------------------------------------

    async def generate_general_help_response(
        self,
        user_message: str,
        working_memory: WorkingMemory,
        ctx: Dict[str, Any],
    ) -> str:
        return await self._response_generator.generate_general_help_response(
            user_message, working_memory, ctx
        )

    async def generate_direct_response_via_llm(
        self,
        response_type: str,
        user_message: str,
        intent: UserIntent,
        working_memory: WorkingMemory,
        project_id: Optional[str] = None,
        max_tokens: Optional[int] = None,
        ctx: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        return await self._response_generator.generate_direct_response_via_llm(
            response_type=response_type,
            user_message=user_message,
            intent=intent,
            working_memory=working_memory,
            project_id=project_id,
            max_tokens=max_tokens,
            ctx=ctx,
        )

    async def generate_greeting_response(
        self,
        user_message: str,
        working_memory: WorkingMemory,
        project_id: Optional[str] = None,
        ctx: Optional[Dict[str, Any]] = None,
    ) -> str:
        return await self._response_generator.generate_greeting_response(
            user_message, working_memory, project_id, ctx
        )

    async def generate_qa_response(
        self,
        intent: UserIntent,
        user_message: str,
        working_memory: WorkingMemory,
        project_id: Optional[str] = None,
        ctx: Optional[Dict[str, Any]] = None,
    ) -> str:
        return await self._response_generator.generate_qa_response(
            intent, user_message, working_memory, project_id, ctx
        )

    async def try_web_search_response(self, user_message: str) -> Optional[str]:
        return await self._response_generator.try_web_search_response(user_message)

    async def generate_information_request_response(
        self,
        intent: UserIntent,
        working_memory: WorkingMemory,
        project_id: Optional[str] = None,
        ctx: Optional[Dict[str, Any]] = None,
    ) -> str:
        return await self._response_generator.generate_information_request_response(
            intent, working_memory, project_id, ctx
        )

    # --- ResultAssembler ----------------------------------------------------

    @staticmethod
    def single_skill_id(tree: "TaskTree") -> Optional[str]:
        return ResultAssembler.single_skill_id(tree)

    def envelopes_from_artifacts(
        self, artifacts: Optional[List[Any]]
    ) -> List[Dict[str, Any]]:
        return self._result_assembler.envelopes_from_artifacts(artifacts)

    def envelopes_from_results(
        self, results: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        return self._result_assembler.envelopes_from_results(results)

    def summarize(
        self,
        envelopes: List[Dict[str, Any]],
        user_message: str,
        skill_id: Optional[str],
    ) -> str:
        return self._result_assembler.summarize(envelopes, user_message, skill_id)

    def extract_plot_messages(
        self,
        results: Dict[str, Any],
        tree: "TaskTree",
        working_memory: "WorkingMemory",
    ) -> List[ChatMessage]:
        return self._result_assembler.extract_plot_messages(
            results, tree, working_memory
        )

    def build_workflow_result(
        self,
        tree: "TaskTree",
        working_memory: "WorkingMemory",
        backend: str,
        artifacts: Optional[List[Any]] = None,
        error: Optional[str] = None,
        user_message: str = "",
    ) -> "TurnResult":
        return self._result_assembler.build_workflow_result(
            tree=tree,
            working_memory=working_memory,
            backend=backend,
            artifacts=artifacts,
            error=error,
            user_message=user_message,
        )

    def build_fallback_result(
        self,
        tree: "TaskTree",
        working_memory: "WorkingMemory",
    ) -> "TurnResult":
        return self._result_assembler.build_fallback_result(tree, working_memory)

    def extract_hitl(self, results: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return self._result_assembler.extract_hitl(results)

    def build_hitl_result(
        self,
        tree: "TaskTree",
        hitl_info: Dict[str, Any],
        working_memory: "WorkingMemory",
    ) -> "TurnResult":
        return self._result_assembler.build_hitl_result(
            tree, hitl_info, working_memory
        )

    def build_error_result(
        self, error: Union[str, TurnError], working_memory: "WorkingMemory"
    ) -> "TurnResult":
        return self._result_assembler.build_error_result(error, working_memory)

    # --- ClarificationHandler -------------------------------------------------

    def handle_clarification(
        self,
        intent: UserIntent,
        working_memory: "WorkingMemory",
    ) -> "TurnResult":
        return self._clarification_handler.handle_clarification(
            intent, working_memory
        )

    def build_debate_resolved_intent(
        self,
        debate_response: Dict[str, Any],
        user_message: str,
    ) -> UserIntent:
        return self._clarification_handler.build_debate_resolved_intent(
            debate_response, user_message
        )
