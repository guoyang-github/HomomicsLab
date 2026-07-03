"""Cascade intent analyzer — LLM-first classification with keyword guardrails."""

import json
import re
import weakref
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from homomics_lab.context.compressor import ContextCompressor
from homomics_lab.context.context_engine.models import ContextBundle
from homomics_lab.context.relevance_filter import ContextItem
from homomics_lab.agent.intent.classifiers import (
    EmbeddingIntentClassifier,
    IntentClassifier,
    IntentDefinition,
    KeywordIntentClassifier,
    LLMIntentClassifier,
)
from homomics_lab.agent.intent.calibration import (
    ConfidenceCalibrator,
    IntentDecisionLogger,
    IntentDecisionRecord,
)
from homomics_lab.agent.intent.models import (
    IntentClassificationResult,
    IntentMatch,
    StructuredIntent,
    UserIntent,
)
from homomics_lab.agent.debate import LightweightDebate
from homomics_lab.context.working_memory import WorkingMemory


# Optional CBKB import; avoid hard dependency at module load.
try:
    from homomics_lab.knowledge.cbkb import CBKB
except Exception:  # pragma: no cover
    CBKB = None  # type: ignore


# Track live analyzer instances so domain hot-reload can refresh intent definitions.
_analyzer_instances: weakref.WeakSet = weakref.WeakSet()


class CascadeIntentAnalyzer:
    """LLM-first intent analyzer with keyword guardrails and active clarification.

    The analyzer now treats the LLM classifier as the primary decision maker.
    Keyword and embedding classifiers provide:

    1. Fast-path guardrails for unambiguous domain-agnostic intents.
    2. Safety overrides when the LLM misclassifies an information request as an
       execution workflow.
    3. Alternative candidates and sub-intent signals for ambiguous messages.

    Decision flow:
      1. Keyword guardrail fast path (only for very strong direct-response signals).
      2. LLM structured classification.
      3. Embedding semantic alternatives.
      4. Fusion with guardrail override.
      5. Clarification if confidence is low and alternatives are close.
    """

    def __init__(
        self,
        definitions: Optional[List[IntentDefinition]] = None,
        use_domain_registry: bool = True,
        keyword_classifier: Optional[IntentClassifier] = None,
        embedding_classifier: Optional[IntentClassifier] = None,
        llm_classifier: Optional[IntentClassifier] = None,
        clarification_threshold: float = 0.35,
        high_confidence_threshold: float = 0.75,
        debate: Optional[LightweightDebate] = None,
        cbkb: Optional[Any] = None,
        decision_logger: Optional[IntentDecisionLogger] = None,
        calibrator: Optional[ConfidenceCalibrator] = None,
    ):
        self._definitions = list(definitions or [])
        self.use_domain_registry = use_domain_registry
        self.clarification_threshold = clarification_threshold
        self.high_confidence_threshold = high_confidence_threshold

        # Keyword matches are treated as strong direct signals by default; the
        # weight is used only when fusing multiple sources or when a test passes
        # an intentionally low weight to simulate weak keyword evidence.
        self.keyword_classifier = keyword_classifier or KeywordIntentClassifier(weight=1.0)
        self.embedding_classifier = embedding_classifier or EmbeddingIntentClassifier(weight=0.25)
        self.llm_classifier = llm_classifier or LLMIntentClassifier(weight=0.60)
        self.debate = debate
        self.cbkb = cbkb
        self.decision_logger = decision_logger if decision_logger is not None else IntentDecisionLogger()
        self.calibrator = calibrator if calibrator is not None else ConfidenceCalibrator(self.decision_logger)

        # Always load built-in intents (qa, general_help, file_conversion) so
        # domain-agnostic requests work even without domain registry.
        self._load_builtin_definitions()

        if use_domain_registry:
            self._load_domain_definitions()

        _analyzer_instances.add(self)

    @classmethod
    def reload_all(cls) -> None:
        """Reload intent definitions in all live analyzer instances."""
        for analyzer in list(_analyzer_instances):
            try:
                analyzer.reload()
            except Exception:
                # Hot-reload errors should not break the caller.
                pass

    def _load_builtin_definitions(self) -> None:
        """Load built-in domain-agnostic intent definitions."""
        from homomics_lab.agent.intent.examples import get_builtin_examples

        builtins = [
            ("qa", "builtin"),
            ("information_request", "builtin"),
            ("general_help", "builtin"),
            ("greeting", "builtin"),
            ("file_conversion", "builtin"),
            ("single_cell_analysis", "builtin"),
            ("spatial_analysis", "builtin"),
            ("metagenomics_analysis", "builtin"),
            ("pubmed_search", "builtin"),
            ("pubmed_fetch", "builtin"),
            ("uniprot_search", "builtin"),
            ("geo_search", "builtin"),
        ]
        existing = {d.analysis_type for d in self._definitions}
        for analysis_type, domain in builtins:
            if analysis_type in existing:
                continue
            examples = get_builtin_examples(analysis_type)
            keywords = []
            complexity_indicators = []
            if analysis_type == "qa":
                keywords = [
                    "什么是", "what is", "怎么", "如何", "how to", "how do",
                    "explain", "告诉我", "介绍", "概述", "overview",
                ]
            elif analysis_type == "information_request":
                keywords = [
                    "有哪些", "what are", "包括哪些", "what can you do",
                    "你会什么", "你能做什么", "what do you support",
                    "有哪些分析内容", "有哪些步骤", "how do i get started",
                ]
            elif analysis_type == "general_help":
                keywords = [
                    "写一段", "写个脚本", "写代码", "生成代码", "generate code",
                    "code snippet", "python脚本", "脚本", "shell脚本",
                    "示例", "example", "怎么用",
                    "处理csv", "处理文件", "filter", "parse", "rename",
                ]
            elif analysis_type == "greeting":
                keywords = [
                    "who are you", "what can you do", "introduce yourself",
                    "hello", "hi", "hey", "你好", "您好", "哈喽",
                    "你是谁", "你会什么", "介绍一下你自己", "自我介绍一下",
                ]
            elif analysis_type == "file_conversion":
                keywords = [
                    "转换", "convert", "格式", "format", "变成", "转成",
                    "改为", "change to",
                ]
            elif analysis_type == "single_cell_analysis":
                keywords = [
                    "单细胞", "single cell", "scRNA", "10x", "scanpy", "seurat",
                    "PBMC", "细胞", "cell", "umap", "pca", "聚类", "cluster",
                    "差异表达", "marker gene",
                ]
                complexity_indicators = [
                    "流程", "pipeline", "全流程", "完整",
                ]
            elif analysis_type == "spatial_analysis":
                keywords = [
                    "空间", "spatial", "visium", "xenium", "merfish", "空间转录组",
                ]
                complexity_indicators = ["流程", "pipeline"]
            elif analysis_type == "metagenomics_analysis":
                keywords = [
                    "宏基因组", "16S", "amplicon", "microbiome", "肠道菌群",
                    "qiime", "dada2", "otu", "asv", "taxonomy", "物种注释",
                    "多样性", "alpha diversity", "beta diversity",
                ]
                complexity_indicators = ["全流程", "完整分析", "pipeline"]
            elif analysis_type == "pubmed_search":
                keywords = [
                    "pubmed", "文献", "文章", "论文", "查文献", "搜索文献",
                    "paper", "article", "literature",
                ]
            elif analysis_type == "pubmed_fetch":
                keywords = [
                    "pmid", "pubmed id", "pubmed摘要", "文章摘要", "abstract",
                ]
            elif analysis_type == "uniprot_search":
                keywords = [
                    "uniprot", "蛋白", "蛋白质", "protein", "基因蛋白",
                ]
            elif analysis_type == "geo_search":
                keywords = [
                    "geo", "数据集", "表达谱", "gene expression omnibus",
                    "dataset", "microarray", "rna-seq data",
                ]
            self._definitions.append(
                IntentDefinition(
                    analysis_type=analysis_type,
                    keywords=keywords,
                    examples=examples,
                    complexity_indicators=complexity_indicators,
                    domain=domain,
                )
            )

    def _load_domain_definitions(self) -> None:
        """Load intent definitions from DomainRegistry."""
        from homomics_lab.domain.registry import get_domain_registry

        registry = get_domain_registry()
        existing = {d.analysis_type for d in self._definitions}
        for domain in registry.list_all():
            for intent in domain.intents:
                if intent.analysis_type in existing:
                    continue
                self._definitions.append(
                    IntentDefinition(
                        analysis_type=intent.analysis_type,
                        keywords=intent.keywords,
                        examples=getattr(intent, "examples", []) or [],
                        complexity_indicators=intent.complexity_indicators,
                        data_scale_patterns=intent.data_scale_patterns,
                        domain=domain.domain,
                    )
                )

    def register_intent(self, analysis_type: str, config: Dict[str, Any]) -> None:
        """Register or override an intent configuration at runtime."""
        new_def = IntentDefinition(
            analysis_type=analysis_type,
            keywords=config.get("keywords", []),
            examples=config.get("examples", []),
            complexity_indicators=config.get("complexity_indicators", []),
            data_scale_patterns=config.get("data_scale_patterns", []),
            domain=config.get("domain"),
        )
        for i, existing in enumerate(self._definitions):
            if existing.analysis_type == analysis_type:
                self._definitions[i] = new_def
                return
        self._definitions.append(new_def)

    def reload(self) -> None:
        """Reload intent definitions from domain registry."""
        self._definitions.clear()
        if self.use_domain_registry:
            self._load_domain_definitions()

    def list_registered_intents(self) -> Dict[str, Dict[str, Any]]:
        """Return all registered intent configurations."""
        return {
            d.analysis_type: {
                "domain": d.domain,
                "keywords": d.keywords,
                "examples": d.examples,
                "complexity_indicators": d.complexity_indicators,
                "data_scale_patterns": d.data_scale_patterns,
            }
            for d in self._definitions
        }

    async def analyze(
        self,
        message: str,
        working_memory: Optional[WorkingMemory] = None,
        extra_context: Optional[Dict[str, Any]] = None,
        cbkb: Optional[Any] = None,
        context_bundle: Optional[ContextBundle] = None,
    ) -> UserIntent:
        """Analyze user message and return structured intent."""
        context = self._build_context(
            working_memory,
            extra_context,
            message,
            context_bundle=context_bundle,
        )

        # Layer 1: keyword guardrail fast path for unambiguous direct-response signals.
        keyword_matches = await self.keyword_classifier.classify(
            message, self._definitions, context
        )
        top_keyword = keyword_matches[0] if keyword_matches else None
        if top_keyword and top_keyword.confidence >= self.high_confidence_threshold:
            # Only direct-response intents (qa, greeting, information_request,
            # general_help) are allowed to bypass the LLM. Tool intents such as
            # pubmed_search are intentionally left for the LLM-first classifier so
            # that nuanced utterances like "是从 pubmed 查的？" are not mis-routed.
            if top_keyword.structured and top_keyword.structured.interaction_mode == "answer":
                intent = self._to_user_intent(
                    top_keyword, message, alternatives=keyword_matches[1:]
                )
                self._enrich_with_cbkb(intent, cbkb)
                return intent

        # Layer 2: LLM-first structured classification.
        llm_matches = []
        if isinstance(self.llm_classifier, LLMIntentClassifier) and self.llm_classifier.is_available():
            llm_matches = await self.llm_classifier.classify(
                message, self._definitions, context
            )

        # Layer 3: embedding semantic alternatives.
        embedding_matches = await self.embedding_classifier.classify(
            message, self._definitions, context
        )

        # Layer 4: fusion with keyword guardrail override.
        fused = self._fuse_matches(keyword_matches, embedding_matches, llm_matches, message)

        # Layer 5: clarification only when the ensemble signals genuine ambiguity.
        if fused.needs_clarification:
            intent = await self._build_clarification_intent(fused, message)
            self._enrich_with_cbkb(intent, cbkb)
            return intent

        primary = self._apply_mcp_override(fused.primary, message, fused.alternatives)

        # Lightweight safety net: if the fused intent still routes to an MCP tool
        # but the user is asking about the source of information or we cannot
        # extract a usable query, fall back to a direct answer. This protects
        # against LLM misclassification and keyword-only fallback without
        # bypassing the LLM-first decision path.
        if primary.analysis_type in (
            "pubmed_search",
            "pubmed_fetch",
            "uniprot_search",
            "geo_search",
        ):
            tool_inputs = self._extract_mcp_inputs(primary.analysis_type, message)
            if primary.analysis_type == "pubmed_fetch":
                lacks_usable_input = not tool_inputs.get("pmid")
            else:
                lacks_usable_input = self._is_meaningless_query(tool_inputs.get("query", ""))
            if self._is_meta_source_question(message) or lacks_usable_input:
                primary = IntentMatch(
                    analysis_type="qa",
                    confidence=0.9,
                    source="keyword_guardrail",
                    reason="fused tool intent lacks usable query or asks about source",
                    weight=1.0,
                    structured=StructuredIntent(
                        intent_type="qa",
                        interaction_mode="answer",
                        target="answer_question",
                        scope="single_step",
                        confidence=0.9,
                        reason="fused tool intent lacks usable query or asks about source",
                    ),
                )
                fused.alternatives.insert(0, fused.primary)

        intent = self._to_user_intent(
            primary, message, sub_intents=fused.sub_intents, alternatives=fused.alternatives
        )
        self._enrich_with_cbkb(intent, cbkb)
        self._record_decision(
            message=message,
            fused=fused,
            keyword_matches=keyword_matches,
            embedding_matches=embedding_matches,
            llm_matches=llm_matches,
        )
        return intent

    def _record_decision(
        self,
        message: str,
        fused: IntentClassificationResult,
        keyword_matches: List[IntentMatch],
        embedding_matches: List[IntentMatch],
        llm_matches: List[IntentMatch],
    ) -> None:
        """Record the classification decision for observability and calibration."""
        try:
            from homomics_lab.metrics import (
                record_intent_clarification,
                record_intent_decision,
                record_intent_low_confidence,
            )

            primary = fused.primary
            record_intent_decision(primary.analysis_type, primary.confidence)
            if fused.needs_clarification:
                record_intent_clarification(primary.analysis_type)
            elif primary.confidence < self.high_confidence_threshold:
                record_intent_low_confidence(primary.analysis_type)

            if self.decision_logger is None:
                return
            self.decision_logger.record(
                IntentDecisionRecord(
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    message=message,
                    primary_intent=primary.analysis_type,
                    confidence=primary.confidence,
                    needs_clarification=fused.needs_clarification,
                    keyword_scores={m.analysis_type: m.confidence for m in keyword_matches},
                    embedding_scores={m.analysis_type: m.confidence for m in embedding_matches},
                    llm_scores={m.analysis_type: m.confidence for m in llm_matches},
                )
            )
        except Exception:
            # Decision logging must not break intent analysis.
            pass

    def _build_context(
        self,
        working_memory: Optional[WorkingMemory],
        extra_context: Optional[Dict[str, Any]] = None,
        message: str = "",
        context_bundle: Optional[ContextBundle] = None,
    ) -> Dict[str, Any]:
        """Build context dict from working memory or a pre-built ContextBundle.

        Recent conversation history is compressed with ContextCompressor so the
        downstream LLM prompt stays within budget while keeping the messages
        most relevant to the current user message.
        """
        if context_bundle is not None:
            # Use the already assembled, token-safe context from ContextEngine.
            recent_messages = []
            for msg in context_bundle.messages:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                if role in ("system", "developer"):
                    # Surface system/project/CBKB context as a single system message.
                    recent_messages.append({"role": "system", "content": content})
                else:
                    recent_messages.append({"role": role, "content": content})
            context = {
                "recent_messages": recent_messages,
                "current_task_id": working_memory.current_task_id if working_memory else None,
                "pinned_items": working_memory.pinned_items if working_memory else [],
            }
        elif working_memory is None:
            context = {}
        else:
            recent = working_memory.get_recent_messages(10)
            context_items = self._messages_to_context_items(
                recent, working_memory.pinned_items
            )
            compressed = self._compress_context_items(context_items, current_goal=message)
            context = {
                "recent_messages": [
                    {"role": msg.get("role", "unknown"), "content": msg.get("content", "")}
                    for msg in compressed
                ],
                "current_task_id": working_memory.current_task_id,
                "pinned_items": working_memory.pinned_items,
            }
        if extra_context is not None:
            context["extra_context"] = extra_context
        return context

    @staticmethod
    def _messages_to_context_items(
        messages: List[Any], pinned_items: List[str]
    ) -> List[ContextItem]:
        """Convert ChatMessage objects to ContextItems for compression."""
        items: List[ContextItem] = []
        now = datetime.now(timezone.utc)
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
            # Preserve the original speaker so downstream prompts still know who said what.
            content = f"{msg.sender}: {text}"
            hours = 0.0
            if msg.timestamp:
                try:
                    hours = (now - msg.timestamp).total_seconds() / 3600.0
                except Exception:
                    hours = 0.0
            importance = 0.5
            if msg.sender == "agent" and msg.type.value in {
                "result_preview", "todo_list", "plot", "hitl_request"
            }:
                importance = 0.7
            items.append(
                ContextItem(
                    content=content,
                    type=msg.type.value,
                    is_pinned=msg.id in pinned_items,
                    is_upstream_result=bool(msg.task_id),
                    agent_importance=importance,
                    hours_since_created=hours,
                )
            )
        return items

    @staticmethod
    def _compress_context_items(
        items: List[ContextItem], current_goal: str
    ) -> List[Dict[str, str]]:
        """Run ContextCompressor and return role/content dicts."""
        if not items:
            return []
        try:
            compressor = ContextCompressor(max_items=6, max_chars_per_item=1000)
            compressed = compressor.compress(items, current_goal=current_goal)
        except Exception:
            # Compression is best-effort; fall back to the latest items.
            compressed = items[-6:]

        result: List[Dict[str, str]] = []
        for item in compressed:
            # Content already prefixed with the sender in _messages_to_context_items.
            # Extract a role for backwards compatibility with the prompt formatter.
            parts = item.content.split(": ", 1)
            if len(parts) == 2 and parts[0] in {"user", "agent", "system"}:
                role, content = parts[0], parts[1]
            else:
                role, content = "agent" if item.type in {
                    "result_preview", "todo_list", "plot", "hitl_request"
                } else "user", item.content
            result.append({"role": role, "content": content})
        return result

    def _fuse_matches(
        self,
        keyword: List[IntentMatch],
        embedding: List[IntentMatch],
        llm: List[IntentMatch],
        message: str,
    ) -> IntentClassificationResult:
        """Fuse scores from all classifiers into a single result.

        LLM-first: the primary intent comes from the highest-confidence LLM
        match unless a keyword guardrail strongly disagrees and the keyword
        signal corresponds to a direct-response intent (qa, information_request,
        general_help, greeting).
        """
        # If no strong keyword signal, ignore weak embedding noise.
        min_embedding_confidence = 0.25
        if not keyword and embedding:
            max_emb = max(m.confidence for m in embedding)
            if max_emb < min_embedding_confidence:
                embedding = []

        # --- LLM-first primary selection ---
        primary: Optional[IntentMatch] = None
        llm_primary = llm[0] if llm else None
        keyword_primary = keyword[0] if keyword else None

        if llm_primary:
            primary = llm_primary

        # Keyword guardrail override: if the keyword classifier is very confident
        # that this is a direct-response intent, prefer it over a conflicting LLM
        # execution intent. This protects against LLM hallucinations such as
        # classifying "有哪些分析内容" as an analysis workflow.
        if keyword_primary and keyword_primary.confidence >= self.high_confidence_threshold:
            if keyword_primary.structured and keyword_primary.structured.interaction_mode == "answer":
                if primary is None or primary.structured is None or primary.structured.interaction_mode != "answer":
                    primary = keyword_primary

        # If LLM is unavailable and keyword has a moderate signal, use keyword.
        if primary is None and keyword_primary and keyword_primary.confidence >= self.clarification_threshold:
            primary = keyword_primary

        # If still nothing, use the best embedding match.
        if primary is None and embedding:
            primary = embedding[0]

        if primary is None:
            return IntentClassificationResult(
                primary=IntentMatch(
                    analysis_type="general",
                    confidence=0.0,
                    source="fallback",
                    reason="no classifier produced a match",
                    structured=StructuredIntent(
                        intent_type="general",
                        interaction_mode="answer",
                        confidence=0.0,
                        reason="no classifier produced a match",
                    ),
                ),
                needs_clarification=False,
            )

        # --- Build alternatives from the union of non-primary signals ---
        seen = {primary.analysis_type}
        alternatives: List[IntentMatch] = []
        for m in keyword + embedding + llm:
            if m.analysis_type == primary.analysis_type:
                continue
            if m.analysis_type in seen:
                continue
            seen.add(m.analysis_type)
            alternatives.append(m)
        alternatives.sort(key=lambda m: m.confidence, reverse=True)

        # --- Sub-intent detection ---
        sub_intents: List[IntentMatch] = []
        # Use explicit sub_intents from the LLM output first.
        for m in llm:
            if m.reason == "sub_intent" and m.analysis_type != primary.analysis_type:
                sub_intents.append(m)
        # If top-2 are close and both are analysis intents, treat runner-up as sub-intent.
        if len(alternatives) >= 2:
            second = alternatives[0]
            if primary.confidence > 0 and (second.confidence / primary.confidence) > 0.5:
                if second.confidence > 0.2 and second.analysis_type not in {s.analysis_type for s in sub_intents}:
                    sub_intents.append(second)
        # If primary is a broad analysis type and we have strong specific signals,
        # treat the specific ones as sub_intents.
        broad_types = {"single_cell_analysis", "spatial_analysis", "metagenomics_analysis"}
        if primary.analysis_type in broad_types:
            for alt in alternatives[:2]:
                if alt.confidence > 0.4 and alt.analysis_type not in broad_types:
                    if alt.analysis_type not in {s.analysis_type for s in sub_intents}:
                        sub_intents.append(alt)

        # Explicit sequential markers ("先...再...") indicate a multi-step workflow.
        # Surface all strong, specific step intents as sub-intents.
        sequential_markers = ["然后", "再", "接着", "and then", "followed by", "first", "先"]
        text = message.lower()
        has_sequential_markers = any(m in text for m in sequential_markers)
        if has_sequential_markers:
            min_step_score = 0.05
            direct_response_types = {"qa", "information_request", "general_help", "greeting", "clarification"}
            step_signals = [
                m for m in keyword + embedding + llm
                if (m.confidence * m.weight) >= min_step_score
                and m.analysis_type not in broad_types
                and m.analysis_type not in direct_response_types
            ]
            distinct_steps = {m.analysis_type for m in step_signals}
            if len(distinct_steps) >= 2:
                sub_intents = []
                seen_steps: set = set()
                for m in sorted(step_signals, key=lambda x: x.confidence * x.weight, reverse=True):
                    if m.analysis_type in seen_steps:
                        continue
                    seen_steps.add(m.analysis_type)
                    sub_intents.append(m)

        # --- Clarification logic ---
        needs_clarification = False
        clarification_question = None

        # If the LLM itself asked for clarification, respect it.
        if llm_primary and llm_primary.structured and llm_primary.structured.intent_type == "clarification":
            needs_clarification = True
            clarification_question = (
                llm_primary.structured.entities.get("clarification_question")
                or "我不太确定您的需求，请再具体描述一下。"
            )
        elif not has_sequential_markers and alternatives:
            # Use classifier-weighted scores to decide whether the ensemble is
            # genuinely ambiguous. Sequential markers are treated as workflow
            # intent, not as ambiguity.
            primary_weighted = primary.confidence * primary.weight
            top_alt = alternatives[0]
            top_alt_weighted = top_alt.confidence * top_alt.weight
            gap = primary_weighted - top_alt_weighted
            if (
                primary_weighted < self.clarification_threshold
                and top_alt_weighted > 0
                and gap < 0.3 * primary_weighted
            ):
                needs_clarification = True
                option_lines = [f"- {primary.analysis_type}？"]
                for alt in alternatives[:2]:
                    option_lines.append(f"- {alt.analysis_type}？")
                clarification_question = (
                    "我不太确定您的需求，您是想要：\n"
                    + "\n".join(option_lines)
                    + "\n\n请告诉我更具体一些。"
                )

        return IntentClassificationResult(
            primary=primary,
            alternatives=alternatives,
            sub_intents=sub_intents,
            needs_clarification=needs_clarification,
            clarification_question=clarification_question,
        )

    def _apply_mcp_override(
        self,
        primary: IntentMatch,
        message: str,
        alternatives: List[IntentMatch],
    ) -> IntentMatch:
        """If the user explicitly mentions an MCP tool, override broad analysis intents."""
        broad_types = {"single_cell_analysis", "spatial_analysis", "metagenomics_analysis"}
        if primary.analysis_type not in broad_types:
            return primary

        lower = message.lower()
        mcp_keywords = {
            "pubmed_search": ["pubmed", "文献", "论文", "paper", "article", "literature"],
            "pubmed_fetch": ["pmid", "pubmed摘要", "abstract"],
            "uniprot_search": ["uniprot", "蛋白", "蛋白质", "protein"],
            "geo_search": ["geo", "数据集", "表达谱", "dataset", "microarray"],
        }

        for analysis_type, keywords in mcp_keywords.items():
            if any(kw in lower for kw in keywords):
                # Prefer an existing alternative match if present.
                for alt in alternatives:
                    if alt.analysis_type == analysis_type:
                        return alt
                return IntentMatch(
                    analysis_type=analysis_type,
                    confidence=0.8,
                    source="mcp_override",
                    reason=f"explicit mcp keyword detected while primary was {primary.analysis_type}",
                    structured=StructuredIntent(
                        intent_type="tool_call",
                        interaction_mode="explore",
                        target=analysis_type,
                        scope="single_step",
                        confidence=0.8,
                        reason=f"explicit mcp keyword detected while primary was {primary.analysis_type}",
                    ),
                )
        return primary

    def _extract_data_scale(
        self,
        message: str,
        definition: Optional[IntentDefinition],
    ) -> Optional[str]:
        """Extract data scale hints using configured patterns plus universal patterns."""
        patterns = []
        if definition:
            patterns.extend(definition.data_scale_patterns)
        patterns.extend([
            r'(\d+)\s*个细胞',
            r'(\d+)\s*cells',
            r'(\d+)k\s*cells',
            r'(\d+)\s*个样本',
            r'(\d+)\s*samples',
            r'(\d+)\s*个基因',
            r'(\d+)\s*genes',
        ])
        for pattern in patterns:
            match = re.search(pattern, message)
            if match:
                return match.group(0)
        return None

    def _determine_complexity(
        self,
        match: IntentMatch,
        message: str,
        definition: Optional[IntentDefinition],
        has_sub_intents: bool = False,
    ) -> str:
        """Determine complexity from indicators and message."""
        # Tool-only intents are always direct responses regardless of how the
        # LLM structured classifier labelled scope/complexity.
        if match.analysis_type in (
            "pubmed_search",
            "pubmed_fetch",
            "uniprot_search",
            "geo_search",
        ):
            return "direct_response"

        # Honor structured intent first.
        if match.structured is not None:
            return match.structured.to_legacy_complexity()

        text = message.lower()

        # Direct-response intents
        if match.analysis_type in (
            "qa",
            "information_request",
            "general_help",
            "greeting",
            "clarification",
        ):
            return "direct_response"

        # Sequential markers (e.g. "先...再...") strongly imply a multi-step workflow.
        sequential_markers = ["然后", "再", "接着", "and then", "followed by", "first", "先"]
        if any(m in text for m in sequential_markers):
            if match.structured is None or match.structured.intent_type == "analysis":
                return "complex"

        # Multiple explicit sub-intents always imply a complex workflow.
        if has_sub_intents:
            return "complex"

        if definition:
            indicators = definition.complexity_indicators
            if any(kw.lower() in text for kw in indicators):
                return "complex"

        # Heuristic: multiple analysis keywords or long message
        if len(text.split()) > 15:
            return "complex"

        # Multi-intent implies complex workflow
        if match.analysis_type in ("single_cell_analysis", "spatial_analysis", "metagenomics_analysis"):
            # Check for sequential markers
            sequential_markers = ["然后", "再", "接着", "and then", "followed by", "first", "先"]
            if any(m in text for m in sequential_markers):
                return "complex"

        return "single_step"

    def _find_definition(self, analysis_type: str) -> Optional[IntentDefinition]:
        for d in self._definitions:
            if d.analysis_type == analysis_type:
                return d
        return None

    @staticmethod
    def _extract_mcp_inputs(analysis_type: str, message: str) -> Dict[str, Any]:
        """Extract parameters for MCP tool intents from free-form text."""
        text = message.strip()
        lower = text.lower()

        # Numeric limit / retmax
        limit_match = re.search(r"(?:limit|retmax|前)\s*[:=]?\s*(\d+)", lower)
        limit_match_alt = re.search(r"(\d+)\s*(?:个|条|篇|results?|entries?)", lower)
        limit = 5
        if limit_match:
            limit = int(limit_match.group(1))
        elif limit_match_alt:
            limit = int(limit_match_alt.group(1))

        if analysis_type == "pubmed_fetch":
            pmid_match = re.search(r"\b(\d{5,})\b", text)
            return {"pmid": pmid_match.group(1) if pmid_match else ""}

        # For search tools, try to capture the query phrase.
        query = ""
        patterns = [
            r"(?:搜索|查找|查|search|find|query)\s*[:=]?\s*[\"']?([^\"'\n，。]{2,})",
            r"(?:关于|for|about)\s*[:=]?\s*[\"']?([^\"'\n，。]{2,})",
        ]
        for pattern in patterns:
            m = re.search(pattern, lower)
            if m:
                query = m.group(1).strip()
                break
        if not query:
            # Fallback: remove tool keywords and known prompt words.
            removals = [
                "pubmed", "文献", "文章", "论文", "查文献", "搜索文献",
                "paper", "article", "literature",
                "uniprot", "蛋白", "蛋白质", "protein", "基因蛋白",
                "geo", "数据集", "表达谱", "dataset", "microarray",
                "rna-seq data", "gene expression omnibus",
                "帮我", "请", "搜索", "查找", "查一下", "查询",
            ]
            q = text
            for r in removals:
                q = re.sub(re.escape(r), "", q, flags=re.IGNORECASE)
            query = q.strip(" ，。!?\n")

        if analysis_type in ("pubmed_search", "geo_search"):
            return {"query": query, "retmax": limit}
        if analysis_type == "uniprot_search":
            return {"query": query, "limit": limit}
        return {"query": query}

    @staticmethod
    def _is_meta_source_question(message: str) -> bool:
        """Return True when the user is asking about the source of an answer.

        Examples:
            - "你这个信息是从 pubmed 查的？"
            - "Is this from PubMed?"
            - "数据来源于 GEO 吗？"
        """
        lower = message.lower()
        patterns = [
            r"是\s*从\s*\S+\s*查的",
            r"是\s*在\s*\S+\s*查的",
            r"从\s*\S+\s*(?:查|来|找|搜索)",
            r"(?:来源|来自|based\s+on|from)\s*(?:pubmed|uniprot|geo|文献|数据库)",
            r"(?:pubmed|uniprot|geo|文献|数据库)\s*(?:来源|来自|from)",
            r"你[这那].*?(?:从|在).*?(?:查|来|找)",
        ]
        return any(re.search(p, lower) for p in patterns)

    @staticmethod
    def _is_meaningless_query(query: str) -> bool:
        """Return True if the extracted search query has no real content."""
        if not isinstance(query, str):
            return True
        cleaned = re.sub(r"[^\w\s]", "", query.strip())
        cleaned = re.sub(r"\s+", "", cleaned)
        if len(cleaned) < 2:
            return True
        particles = {
            "的", "了", "吗", "呢", "吧", "啊", "嗯", "哦",
            "是", "在", "从", "查", "找", "搜索", "的查",
        }
        return cleaned in particles

    def _to_user_intent(
        self,
        match: IntentMatch,
        message: str,
        sub_intents: Optional[List[IntentMatch]] = None,
        alternatives: Optional[List[IntentMatch]] = None,
    ) -> UserIntent:
        """Convert an IntentMatch to the public UserIntent object."""
        definition = self._find_definition(match.analysis_type)
        has_sub_intents = bool(sub_intents)
        complexity = self._determine_complexity(match, message, definition, has_sub_intents)
        data_scale = self._extract_data_scale(message, definition)
        domain_knowledge = [definition.domain] if definition and definition.domain else []

        sub_user_intents = []
        if sub_intents:
            for sub in sub_intents:
                sub_user_intents.append(self._to_user_intent(sub, message))

        metadata: Dict[str, Any] = {"reason": match.reason, "source": match.source}
        if alternatives:
            metadata["alternatives"] = [
                {"analysis_type": m.analysis_type, "confidence": m.confidence, "source": m.source}
                for m in alternatives
            ]
        if match.analysis_type in (
            "pubmed_search",
            "pubmed_fetch",
            "uniprot_search",
            "geo_search",
        ):
            metadata["tool_name"] = match.analysis_type
            metadata["tool_inputs"] = self._extract_mcp_inputs(match.analysis_type, message)

        # Structured intent decomposition (best-practice v2).
        structured = match.structured
        if structured is None:
            # Synthesize a StructuredIntent from the legacy match for consistency.
            structured = StructuredIntent(
                intent_type=self._legacy_to_intent_type(match.analysis_type, complexity, metadata),
                interaction_mode=self._determine_interaction_mode(match, complexity, metadata),
                domain=self._determine_domain(match, definition),
                target=self._determine_target(match, definition),
                scope=self._determine_scope(complexity, has_sub_intents),
                confidence=match.confidence,
                reason=match.reason,
            )
        else:
            # Definition-level metadata is authoritative over the LLM's guess.
            if definition and definition.domain:
                structured.domain = definition.domain
            canonical_target = self._determine_target(match, definition)
            if canonical_target:
                structured.target = canonical_target
            # Ensure the structured scope matches the complexity heuristic when
            # the LLM returns an inconsistent scope.
            if metadata.get("tool_name"):
                structured.interaction_mode = "execute"
                structured.intent_type = "tool_call"
            elif complexity == "direct_response":
                structured.scope = "single_step"
                structured.interaction_mode = "answer"
            elif complexity == "complex" and structured.scope == "single_step":
                structured.scope = "full"

        return UserIntent(
            analysis_type=match.analysis_type,
            complexity=complexity,
            confidence=match.confidence,
            original_message=message,
            data_scale=data_scale,
            domain_knowledge=domain_knowledge,
            sub_intents=sub_user_intents,
            metadata=metadata,
            interaction_mode=structured.interaction_mode,
            domain=structured.domain,
            target=structured.target,
            scope=structured.scope,
            structured_intent=structured,
        )

    def _enrich_with_cbkb(
        self,
        intent: UserIntent,
        cbkb: Optional[Any],
    ) -> None:
        """Attach CBKB-derived SOPs, anomalies, and parameter lore to the intent.

        The CBKB instance passed to analyze() overrides the one configured at
        construction time. If neither is available, enrichment is a no-op.
        """
        cbkb = cbkb or self.cbkb
        if cbkb is None:
            return

        try:
            canonical_domain = UserIntent(
                analysis_type=intent.analysis_type, complexity="single_step"
            ).domain
            categories = {intent.domain, canonical_domain, intent.analysis_type} - {None, ""}
            sops = []
            seen_sop_ids = set()
            for category in categories:
                for sop in cbkb.list_sops(category=category):
                    if sop.id not in seen_sop_ids:
                        seen_sop_ids.add(sop.id)
                        sops.append(sop)
            anomalies = cbkb.query_anomalies(phase_type=intent.analysis_type, limit=3)

            # Parameter lore: use any known skill ids referenced by the intent or
            # its sub-intents. Domain-level intents do not yet resolve to skills,
            # so this list may be empty until execution-time retrieval.
            skill_ids = []
            if intent.target and intent.target != intent.analysis_type:
                skill_ids.append(intent.target)
            for sub in intent.sub_intents:
                if sub.target and sub.target != sub.analysis_type:
                    skill_ids.append(sub.target)
            lore: List[Dict[str, Any]] = []
            for skill_id in skill_ids[:5]:
                for entry in cbkb.query_parameter_lore(skill_id=skill_id, limit=2):
                    lore.append({
                        "skill_id": entry.skill_id,
                        "param_name": entry.param_name,
                        "param_value": entry.param_value,
                        "outcome_value": entry.outcome_value,
                        "context": entry.context,
                    })

            intent.metadata["cbkb"] = {
                "sops": [
                    {
                        "id": sop.id,
                        "name": sop.name,
                        "category": sop.category,
                        "version": sop.version,
                        "locked": sop.locked,
                    }
                    for sop in sops[:3]
                ],
                "anomalies": [
                    {
                        "id": rec.id,
                        "phase_type": rec.phase_type,
                        "summary": rec.summary,
                        "flags": rec.flags,
                        "severity": rec.severity,
                    }
                    for rec in anomalies
                ],
                "parameter_lore": lore,
            }
        except Exception:
            # CBKB enrichment is best-effort; never break intent analysis.
            pass

    @staticmethod
    def _legacy_to_intent_type(
        analysis_type: str,
        complexity: str,
        metadata: Dict[str, Any],
    ) -> str:
        if analysis_type == "clarification":
            return "clarification"
        if analysis_type in ("qa", "information_request"):
            return "qa"
        if analysis_type == "general_help":
            return "general_help"
        if analysis_type == "greeting":
            return "greeting"
        if analysis_type == "file_conversion":
            return "file_conversion"
        if metadata.get("tool_name"):
            return "tool_call"
        if complexity == "direct_response":
            return "qa"
        return "analysis"

    @staticmethod
    def _determine_interaction_mode(
        match: IntentMatch,
        complexity: str,
        metadata: Dict[str, Any],
    ) -> str:
        # MCP tool intents must always execute, even if the LLM structured
        # classifier labelled them as a plain answer.
        if metadata.get("tool_name"):
            return "execute"
        if match.structured is not None:
            return match.structured.interaction_mode
        if match.analysis_type == "clarification":
            return "clarify"
        if complexity == "direct_response":
            return "answer"
        return "execute"

    @staticmethod
    def _determine_scope(complexity: str, has_sub_intents: bool) -> str:
        if complexity in ("single_step", "direct_response"):
            return "single_step"
        if has_sub_intents:
            return "partial"
        if complexity == "complex":
            return "full"
        return "full"

    def _determine_domain(
        self,
        match: IntentMatch,
        definition: Optional[Any],
    ) -> Optional[str]:
        if match.structured is not None and match.structured.domain:
            return match.structured.domain
        if definition and definition.domain:
            return definition.domain
        domain_from_analysis = UserIntent(analysis_type=match.analysis_type, complexity="single_step").domain
        return domain_from_analysis

    def _determine_target(
        self,
        match: IntentMatch,
        definition: Optional[Any],
    ) -> Optional[str]:
        if match.structured is not None and match.structured.target:
            return match.structured.target
        # Explicit single-step helpers.
        if match.analysis_type == "file_conversion":
            return "convert_file"
        if match.analysis_type in ("qa", "information_request"):
            return "answer_question"
        if match.analysis_type == "general_help":
            return "generate_code"
        # If the analysis_type itself is a known phase id, treat it as the target.
        if self._is_known_phase(match.analysis_type):
            return match.analysis_type
        return None

    def _is_known_phase(self, analysis_type: str) -> bool:
        """Check whether an analysis_type corresponds to a domain phase id."""
        from homomics_lab.domain.registry import get_domain_registry

        try:
            registry = get_domain_registry()
        except Exception:
            return False
        for domain in registry.list_all():
            if analysis_type in domain.get_phase_types():
                return True
        return False

    async def _build_clarification_intent(
        self,
        result: IntentClassificationResult,
        message: str,
    ) -> UserIntent:
        """Build a clarification UserIntent when confidence is too low."""
        question = result.clarification_question or (
            "我不太确定您的需求，请再具体描述一下您想做什么分析。"
        )
        structured = StructuredIntent(
            intent_type="clarification",
            interaction_mode="clarify",
            scope="single_step",
            confidence=0.0,
            reason="low confidence or ambiguous",
            entities={"clarification_question": question},
        )
        metadata: Dict[str, Any] = {
            "clarification_question": question,
            "alternatives": [
                {"analysis_type": m.analysis_type, "confidence": m.confidence}
                for m in [result.primary] + result.alternatives[:2]
            ],
        }

        if self.debate is not None:
            candidates = LightweightDebate.candidates_from_intents(
                [result.primary] + result.alternatives[:2]
            )
            debate_result = await self.debate.run(
                topic=f"Clarify user intent for: {message}",
                candidates=candidates,
                context={"user_message": message},
            )
            metadata["debate"] = debate_result.to_dict()

        return UserIntent(
            analysis_type="clarification",
            complexity="direct_response",
            confidence=0.0,
            original_message=message,
            metadata=metadata,
            interaction_mode="clarify",
            scope="single_step",
            target=None,
            domain=None,
            structured_intent=structured,
        )
