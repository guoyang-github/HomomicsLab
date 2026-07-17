"""ResponseGenerator — builds greeting, QA, help and information responses.

Extracted from ``turn_runner.TurnRunner`` as a pure code move (no logic
changes).
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Dict, List, Optional

from homomics_lab.agent.intent_analyzer import UserIntent
from homomics_lab.context.working_memory import WorkingMemory
from homomics_lab.llm_client import LLMClient
from homomics_lab.prompts import render_prompt

if TYPE_CHECKING:
    from homomics_lab.agent.turn_runner import TurnRunner

logger = logging.getLogger(__name__)


class ResponseGenerator:
    """Generate direct text responses for greeting, QA, help and information intents."""

    def __init__(self, runner: "TurnRunner"):
        self._runner = runner

    async def generate_general_help_response(
        self, user_message: str, working_memory: WorkingMemory
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

        if self._runner._context_bundle is not None:
            # Use the already assembled, token-safe context from ContextEngine.
            messages = self._runner._context_bundle.to_prompt(user_message)
            # Keep only system/assistant messages; the user message will be appended below.
            prompt_messages = [m for m in messages if m.get("role") != "user"]
            prompt_messages.append({"role": "user", "content": user_message})
        else:
            compressed_history = self._runner._compress_working_memory(
                working_memory, user_message
            )
            extra_context = self._runner._format_extra_context()
            project_context = "\n\n".join(
                filter(None, [compressed_history, extra_context])
            )

            prompt = self._runner.prompter.build_prompt(
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
                session_id=getattr(self._runner, "_session_id", None),
                project_id=getattr(self._runner, "_project_id", None),
                request_id=f"{getattr(self._runner, '_turn_request_id', 'code')}_code",
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
    ) -> Optional[str]:
        """Generate a greeting/QA/information direct response via the configured LLM.

        Falls back to static templates when the LLM client is unavailable or fails.
        """
        if self._runner._llm_client is None:
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

        if self._runner._context_bundle is not None:
            # The ContextEngine already assembles token-safe project state, CBKB
            # retrieval, semantic memory, and conversation history. Prepend our
            # direct-response system instruction so the model knows how to answer.
            messages = self._runner._context_bundle.to_prompt(user_message)
            messages.insert(0, {"role": "system", "content": system_prompt})
        else:
            # Fallback minimal context when the context engine is not used.
            context_parts: List[str] = [
                f"Intent: type={intent.analysis_type}, domain={intent.domain or 'none'}, "
                f"analysis_type={intent.analysis_type or 'none'}, confidence={intent.confidence:.2f}"
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

            if self._runner.project_state_manager is not None and project_id is not None:
                try:
                    project_state = self._runner.project_state_manager.load(project_id)
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
        event_callback = getattr(self._runner, "_event_callback", None)
        if event_callback is not None:
            try:
                chunks: List[str] = []
                async for token in self._runner._llm_client.chat_completion_stream(
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
            return await self._runner._llm_client.chat_completion(
                messages=messages,
                temperature=0.3,
                max_tokens=resolved_max_tokens,
                session_id=getattr(self._runner, "_session_id", None),
                project_id=getattr(self._runner, "_project_id", None),
                request_id=f"{getattr(self._runner, '_turn_request_id', 'direct')}_direct",
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
    ) -> str:
        """Return a friendly self-introduction for greeting intents.

        Uses the configured LLM when available for a warmer, context-aware greeting;
        falls back to a static template if no LLM is configured or the call fails.
        """
        greeting_intent = UserIntent(
            analysis_type="greeting",
            domain="general",
            complexity="direct_response",
            original_message=user_message,
        )
        llm_response = await self.generate_direct_response_via_llm(
            response_type="greeting",
            user_message=user_message,
            intent=greeting_intent,
            working_memory=working_memory,
            project_id=project_id,
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
        )
        if llm_response:
            return llm_response

        domain = intent.domain or intent.analysis_type
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
        if not self._runner._tool_registry:
            return None

        web_tools = [t for t in self._runner._tool_registry.list_by_source("builtin") if t.name == "web_search"]
        if not web_tools:
            return None

        try:
            result = await self._runner._tool_registry.invoke_async(
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
