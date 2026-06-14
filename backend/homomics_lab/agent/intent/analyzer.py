"""Cascade intent analyzer — combines keyword, embedding, and LLM classifiers."""

import re
from collections import defaultdict
from typing import Any, Dict, List, Optional

from homomics_lab.agent.intent.classifiers import (
    EmbeddingIntentClassifier,
    IntentClassifier,
    IntentDefinition,
    KeywordIntentClassifier,
    LLMIntentClassifier,
)
from homomics_lab.agent.intent.models import (
    IntentClassificationResult,
    IntentMatch,
    UserIntent,
)
from homomics_lab.agent.debate import LightweightDebate
from homomics_lab.context.working_memory import WorkingMemory


class CascadeIntentAnalyzer:
    """Hybrid intent analyzer with layered classification and active clarification.

    Layer 1: Keyword classifier (fast path, high-confidence direct return)
    Layer 2: Embedding classifier (semantic similarity over intent examples)
    Layer 3: LLM classifier (complex/ambiguous/context-dependent requests)
    Layer 4: Clarification (when ensemble confidence is too low)
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
    ):
        self._definitions = list(definitions or [])
        self.use_domain_registry = use_domain_registry
        self.clarification_threshold = clarification_threshold
        self.high_confidence_threshold = high_confidence_threshold

        self.keyword_classifier = keyword_classifier or KeywordIntentClassifier(weight=0.25)
        self.embedding_classifier = embedding_classifier or EmbeddingIntentClassifier(weight=0.35)
        self.llm_classifier = llm_classifier or LLMIntentClassifier(weight=0.40)
        self.debate = debate

        # Always load built-in intents (qa, general_help, file_conversion) so
        # domain-agnostic requests work even without domain registry.
        self._load_builtin_definitions()

        if use_domain_registry:
            self._load_domain_definitions()

    def _load_builtin_definitions(self) -> None:
        """Load built-in domain-agnostic intent definitions."""
        from homomics_lab.agent.intent.examples import get_builtin_examples

        builtins = [
            ("qa", "builtin"),
            ("general_help", "builtin"),
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
                    "什么是", "how to", "怎么", "如何", "explain", "what is",
                    "how do", "解释", "告诉我",
                ]
            elif analysis_type == "general_help":
                keywords = [
                    "写一段", "写个脚本", "写代码", "生成代码", "generate code",
                    "code snippet", "python脚本", "脚本", "shell脚本",
                    "解释", "explain", "示例", "example", "怎么用",
                    "处理csv", "处理文件", "filter", "parse", "rename",
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
    ) -> UserIntent:
        """Analyze user message and return structured intent."""
        context = self._build_context(working_memory)

        # Layer 1: keyword fast path
        keyword_matches = await self.keyword_classifier.classify(
            message, self._definitions, context
        )
        top_keyword = keyword_matches[0] if keyword_matches else None
        if top_keyword and top_keyword.confidence >= self.high_confidence_threshold:
            top_keyword = self._apply_mcp_override(
                top_keyword, message, keyword_matches[1:]
            )
            return self._to_user_intent(top_keyword, message)

        # Layer 2: embedding semantic match
        embedding_matches = await self.embedding_classifier.classify(
            message, self._definitions, context
        )

        # Layer 3: LLM classifier
        llm_matches = []
        if isinstance(self.llm_classifier, LLMIntentClassifier) and self.llm_classifier.is_available():
            llm_matches = await self.llm_classifier.classify(
                message, self._definitions, context
            )

        # Ensemble fusion
        fused = self._fuse_matches(keyword_matches, embedding_matches, llm_matches)

        # Layer 4: clarification only when the ensemble signals genuine ambiguity.
        if fused.needs_clarification:
            return await self._build_clarification_intent(fused, message)

        primary = self._apply_mcp_override(fused.primary, message, fused.alternatives)
        return self._to_user_intent(primary, message, sub_intents=fused.sub_intents)

    def _build_context(
        self,
        working_memory: Optional[WorkingMemory],
    ) -> Dict[str, Any]:
        """Build context dict from working memory."""
        if working_memory is None:
            return {}
        recent = working_memory.get_recent_messages(5)
        return {
            "recent_messages": [
                {"role": msg.sender, "content": msg.content}
                for msg in recent
            ],
            "current_task_id": working_memory.current_task_id,
            "pinned_items": working_memory.pinned_items,
        }

    def _fuse_matches(
        self,
        keyword: List[IntentMatch],
        embedding: List[IntentMatch],
        llm: List[IntentMatch],
    ) -> IntentClassificationResult:
        """Fuse scores from all classifiers into a single result."""
        # If no strong keyword signal, ignore weak embedding noise.
        min_embedding_confidence = 0.25
        if not keyword and embedding:
            max_emb = max(m.confidence for m in embedding)
            if max_emb < min_embedding_confidence:
                embedding = []

        scores: Dict[str, List[tuple[float, float]]] = defaultdict(list)
        reasons: Dict[str, List[str]] = defaultdict(list)

        for m in keyword:
            scores[m.analysis_type].append((m.confidence * m.weight, m.weight))
            reasons[m.analysis_type].append(f"keyword:{m.confidence:.2f}")
        for m in embedding:
            scores[m.analysis_type].append((m.confidence * m.weight, m.weight))
            reasons[m.analysis_type].append(f"embedding:{m.confidence:.2f}")
        for m in llm:
            scores[m.analysis_type].append((m.confidence * m.weight, m.weight))
            reasons[m.analysis_type].append(f"llm:{m.confidence:.2f}")

        aggregated: List[IntentMatch] = []
        for atype, pairs in scores.items():
            total_weight = sum(w for _, w in pairs)
            avg_score = sum(s for s, _ in pairs) / total_weight if total_weight else 0.0
            aggregated.append(
                IntentMatch(
                    analysis_type=atype,
                    confidence=min(1.0, avg_score),
                    source="ensemble",
                    reason="; ".join(reasons[atype]),
                )
            )

        aggregated.sort(key=lambda m: m.confidence, reverse=True)
        if not aggregated:
            return IntentClassificationResult(
                primary=IntentMatch(
                    analysis_type="general",
                    confidence=0.0,
                    source="fallback",
                    reason="no classifier produced a match",
                ),
                needs_clarification=True,
                clarification_question="我不太确定您的需求，请再具体描述一下您想做什么分析。",
            )

        primary = aggregated[0]
        alternatives = aggregated[1:]

        # Detect multi-intent: if top-2 are close and both are analysis intents,
        # or if an LLM explicitly provided sub_intents (approximated here by
        # looking for near-tied high-confidence matches).
        sub_intents: List[IntentMatch] = []
        if len(aggregated) >= 2:
            second = aggregated[1]
            if primary.confidence > 0 and (second.confidence / primary.confidence) > 0.5:
                if second.confidence > 0.2:
                    sub_intents.append(second)

        # If primary is a broad analysis type and we have strong specific signals,
        # treat the specific ones as sub_intents.
        broad_types = {"single_cell_analysis", "spatial_analysis", "metagenomics_analysis"}
        if primary.analysis_type in broad_types:
            for alt in alternatives[:2]:
                if alt.confidence > 0.4 and alt.analysis_type not in broad_types:
                    sub_intents.append(alt)

        # Only ask for clarification when there is genuine ambiguity:
        # the top candidate is below threshold and at least one alternative is
        # close enough to be a plausible interpretation.
        needs_clarification = False
        clarification_question = None
        if primary.confidence < self.clarification_threshold and alternatives:
            top_alt = alternatives[0]
            gap = primary.confidence - top_alt.confidence
            if top_alt.confidence > 0.2 and gap < 0.15:
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
        text = message.lower()

        # Direct-response intents
        if match.analysis_type in (
            "qa",
            "general_help",
            "clarification",
            "pubmed_search",
            "pubmed_fetch",
            "uniprot_search",
            "geo_search",
        ):
            return "direct_response"

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
            r"(?:搜索|查找|查|search|find|query)\s*[:=]?\s*[\"']?([^\"'\n，。]+)",
            r"(?:关于|for|about)\s*[:=]?\s*[\"']?([^\"'\n，。]+)",
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

    def _to_user_intent(
        self,
        match: IntentMatch,
        message: str,
        sub_intents: Optional[List[IntentMatch]] = None,
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
        if match.analysis_type in (
            "pubmed_search",
            "pubmed_fetch",
            "uniprot_search",
            "geo_search",
        ):
            metadata["tool_name"] = match.analysis_type
            metadata["tool_inputs"] = self._extract_mcp_inputs(match.analysis_type, message)

        return UserIntent(
            analysis_type=match.analysis_type,
            complexity=complexity,
            confidence=match.confidence,
            original_message=message,
            data_scale=data_scale,
            domain_knowledge=domain_knowledge,
            sub_intents=sub_user_intents,
            metadata=metadata,
        )

    async def _build_clarification_intent(
        self,
        result: IntentClassificationResult,
        message: str,
    ) -> UserIntent:
        """Build a clarification UserIntent when confidence is too low."""
        question = result.clarification_question or (
            "我不太确定您的需求，请再具体描述一下您想做什么分析。"
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
        )
