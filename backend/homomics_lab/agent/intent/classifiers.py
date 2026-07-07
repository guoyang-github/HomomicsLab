"""Intent classifiers: keyword guardrail, embedding semantic match, and LLM-first."""

import json
import re
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Any, Dict, List, Optional

from homomics_lab.agent.intent.models import (
    IntentDefinition,
    IntentMatch,
    StructuredIntent,
)
from homomics_lab.config import settings
from homomics_lab.llm_client import LLMClient


class IntentClassifier(ABC):
    """Base class for intent classifiers."""

    def __init__(self, weight: float = 1.0):
        self.weight = weight

    @abstractmethod
    async def classify(
        self,
        message: str,
        definitions: List[IntentDefinition],
        context: Dict[str, Any],
    ) -> List[IntentMatch]:
        """Return ranked intent matches for the message."""


class KeywordIntentClassifier(IntentClassifier):
    """Keyword-based guardrail classifier.

    This classifier is intentionally narrow. It does not try to enumerate every
    possible user utterance; instead it provides:

    1. High-confidence fast-path signals for unambiguous domain-agnostic intents
       (qa, information_request, general_help, greeting).
    2. A guardrail that suppresses workflow execution when the user is clearly
       asking for information or code rather than asking the system to run an
       analysis.
    3. Strong domain keywords for known analysis domains.

    The heavy lifting is left to the LLM-first classifier.
    """

    # Strong domain-agnostic signals. Keep these minimal and precise.
    DOMAIN_KEYWORDS: Dict[str, List[str]] = {
        "qa": [
            "什么是", "what is", "怎么", "如何", "how to", "how do",
            "explain", "告诉我", "介绍", "概述", "overview",
            "什么是.*分析", ".*是什么",
        ],
        "information_request": [
            "有哪些", "what are", "包括哪些", "what can you do",
            "你会什么", "你能做什么", "what do you support",
            "有哪些分析内容", "有哪些步骤", "how do i get started",
        ],
        "general_help": [
            "写一段", "写个脚本", "写代码", "生成代码", "generate code",
            "code snippet", "python脚本", "脚本", "shell脚本",
            "示例", "example", "怎么用",
            "处理csv", "处理文件", "filter", "parse", "rename",
        ],
        "greeting": [
            "who are you", "what can you do", "introduce yourself",
            "hello", "hi ", "hi,", "hey", "你好", "您好", "哈喽",
            "你是谁", "你会什么", "介绍一下你自己", "自我介绍一下",
        ],
    }

    # Phrases that should suppress any workflow/analysis intent.
    GUARDRAIL_PATTERNS: List[str] = [
        r"有哪些分析内容",
        r"有哪些步骤",
        r"包括哪些",
        r"what are the (steps|analyses|analyses available)",
        r"what can you do",
        r"how do i get started",
        r"你能做什么",
        r"你会什么",
    ]

    def __init__(self, weight: float = 1.0):
        super().__init__(weight=weight)

    async def classify(
        self,
        message: str,
        definitions: List[IntentDefinition],
        context: Dict[str, Any],
    ) -> List[IntentMatch]:
        text = message.lower()
        scores: Dict[str, float] = defaultdict(float)
        reasons: Dict[str, str] = {}

        # Built-in domain-agnostic keywords
        for analysis_type, keywords in self.DOMAIN_KEYWORDS.items():
            matches = []
            for kw in keywords:
                if kw.startswith(".*") or kw.endswith(".*") or "what is" in kw:
                    # Treat as regex pattern.
                    try:
                        if re.search(kw, message, re.IGNORECASE):
                            matches.append(kw)
                    except re.error:
                        if kw.lower() in text:
                            matches.append(kw)
                else:
                    if kw.lower() in text:
                        matches.append(kw)
            if matches:
                # Stronger weight for explicit information-request patterns.
                boost = 1.2 if analysis_type == "information_request" else 0.8
                scores[analysis_type] += len(matches) * boost
                reasons[analysis_type] = f"matched keywords: {', '.join(matches)}"

        # Domain-specific keywords
        for definition in definitions:
            atype = definition.analysis_type
            keyword_matches = [kw for kw in definition.keywords if kw.lower() in text]
            if keyword_matches:
                scores[atype] += 1.0
                reasons[atype] = f"matched keywords: {', '.join(keyword_matches)}"

            # Complexity indicators boost confidence for multi-step requests
            complexity_hits = [
                kw for kw in definition.complexity_indicators
                if kw.lower() in text
            ]
            if complexity_hits:
                scores[atype] += len(complexity_hits) * 0.2

        # Built-in tool intents (MCP) get a strong boost so their precise
        # keywords outrank broad domain workflow signals.
        TOOL_KEYWORDS = {
            "pubmed_search": ["pubmed"],
            "pubmed_fetch": ["pmid"],
            "uniprot_search": ["uniprot"],
            "geo_search": ["geo", "gene expression omnibus"],
        }
        for atype, kws in TOOL_KEYWORDS.items():
            matches = [kw for kw in kws if kw.lower() in text]
            if matches:
                scores[atype] += 2.0
                reasons[atype] = f"tool keyword matched: {', '.join(matches)}"

        # Guardrail: information-seeking or coding requests suppress workflow/analysis intents.
        is_guardrail = any(re.search(p, message, re.IGNORECASE) for p in self.GUARDRAIL_PATTERNS)
        if is_guardrail:
            workflow_types = {
                "single_cell_analysis", "spatial_analysis", "metagenomics_analysis",
                "genomics_analysis", "proteomics_analysis", "transcriptomics_analysis",
                "epigenomics_analysis",
            }
            for atype in list(scores):
                if atype in workflow_types:
                    scores[atype] *= 0.1
                    reasons[atype] = reasons.get(atype, "") + " (suppressed by guardrail)"
            if "information_request" not in scores and "qa" not in scores:
                scores["information_request"] = 0.95
                reasons["information_request"] = "guardrail pattern detected"

        # Normalize to [0, 1]
        for atype in scores:
            scores[atype] = min(1.0, scores[atype])

        matches = [
            IntentMatch(
                analysis_type=atype,
                confidence=score,
                source="keyword",
                reason=reasons.get(atype, ""),
                weight=self.weight,
                structured=self._to_structured(atype, score, reasons.get(atype, "")),
            )
            for atype, score in scores.items()
            if score > 0
        ]
        matches.sort(key=lambda m: m.confidence, reverse=True)
        return matches

    @staticmethod
    def _to_structured(analysis_type: str, confidence: float, reason: str) -> Optional[StructuredIntent]:
        """Map a keyword analysis_type to a minimal StructuredIntent when possible."""
        mapping = {
            "qa": ("qa", "answer", None, "answer_question", "single_step"),
            "information_request": ("information_request", "answer", None, None, "single_step"),
            "general_help": ("general_help", "answer", None, "generate_code", "single_step"),
            "greeting": ("greeting", "answer", None, None, "single_step"),
            "file_conversion": ("file_conversion", "execute", None, "convert_file", "single_step"),
        }
        if analysis_type in mapping:
            intent_type, interaction_mode, domain, target, scope = mapping[analysis_type]
            return StructuredIntent(
                intent_type=intent_type,
                interaction_mode=interaction_mode,
                domain=domain,
                target=target,
                scope=scope,
                confidence=confidence,
                reason=reason,
            )
        # Domain workflow intents are better left for the LLM/embedding classifiers.
        return None


class EmbeddingIntentClassifier(IntentClassifier):
    """Embedding-based semantic intent classifier.

    Uses sentence-transformers when available and configured; otherwise falls
    back to TF-IDF + cosine similarity so tests and offline usage still work.
    """

    def __init__(self, weight: float = 0.2, model_name: Optional[str] = None):
        super().__init__(weight=weight)
        # Only use dense embeddings when explicitly configured. Otherwise the
        # default TF-IDF fallback avoids network/model download stalls.
        self._model_name = model_name or settings.semantic_search_model
        self._model = None
        self._vectorizer = None
        self._embeddings = None
        self._analysis_types: List[str] = []
        self._definitions: List[IntentDefinition] = []

    def _load_dense_model(self):
        """Lazy-load sentence-transformers model."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self._model_name or "all-MiniLM-L6-v2")

    def _build_texts(self, definitions: List[IntentDefinition]) -> List[str]:
        """Build searchable texts from intent definitions and examples."""
        from homomics_lab.agent.intent.examples import get_builtin_examples

        texts = []
        for definition in definitions:
            parts = [definition.analysis_type.replace("_", " ")]
            parts.extend(definition.keywords)
            examples = definition.examples or get_builtin_examples(definition.analysis_type)
            parts.extend(examples)
            if definition.domain:
                parts.append(definition.domain)
            texts.append(" ".join(filter(None, parts)))
        return texts

    def fit(self, definitions: List[IntentDefinition]) -> None:
        """Build the embedding index from intent definitions."""
        self._definitions = definitions
        self._analysis_types = [d.analysis_type for d in definitions]
        if not definitions:
            self._embeddings = None
            return

        texts = self._build_texts(definitions)

        # Use dense embeddings only when explicitly configured to avoid blocking
        # on model downloads in offline/test environments.
        if self._model_name:
            try:
                self._load_dense_model()
                self._embeddings = self._model.encode(texts, convert_to_tensor=False)
                return
            except Exception:
                pass

        # Fall back to TF-IDF with character n-grams to handle short Chinese
        # messages and mixed-language examples robustly.
        from sklearn.feature_extraction.text import TfidfVectorizer
        self._vectorizer = TfidfVectorizer(
            lowercase=True,
            analyzer="char_wb",
            ngram_range=(2, 5),
            max_features=5000,
        )
        self._embeddings = self._vectorizer.fit_transform(texts)
        self._model = None

    async def classify(
        self,
        message: str,
        definitions: List[IntentDefinition],
        context: Dict[str, Any],
    ) -> List[IntentMatch]:
        if not definitions:
            return []

        if self._definitions != definitions:
            self.fit(definitions)

        if self._embeddings is None:
            return []

        try:
            if self._model is not None:
                import numpy as np
                query_embedding = self._model.encode([message], convert_to_tensor=False)
                query_norm = query_embedding / np.linalg.norm(query_embedding, axis=1, keepdims=True)
                doc_norms = self._embeddings / np.linalg.norm(self._embeddings, axis=1, keepdims=True)
                similarities = np.dot(doc_norms, query_norm.T).flatten()
            else:
                from sklearn.metrics.pairwise import cosine_similarity
                query_vec = self._vectorizer.transform([message])
                similarities = cosine_similarity(query_vec, self._embeddings).flatten()
        except Exception:
            return []

        indexed = list(enumerate(similarities))
        indexed.sort(key=lambda x: x[1], reverse=True)

        matches = []
        for idx, score in indexed:
            if score <= 0.05:
                continue
            atype = self._analysis_types[idx]
            definition = definitions[idx] if idx < len(definitions) else None
            matches.append(
                IntentMatch(
                    analysis_type=atype,
                    confidence=float(min(1.0, score)),
                    source="embedding",
                    reason=f"semantic similarity {score:.2f}",
                    weight=self.weight,
                    structured=StructuredIntent(
                        intent_type="analysis" if (definition and definition.domain) else atype,
                        interaction_mode="execute",
                        domain=definition.domain if definition else None,
                        target=atype,
                        scope="full",
                        confidence=float(min(1.0, score)),
                        reason=f"semantic similarity {score:.2f}",
                    ) if definition and definition.domain else None,
                )
            )
        return matches


class LLMIntentClassifier(IntentClassifier):
    """LLM-based intent classifier with structured JSON output.

    This classifier produces the v2 ``StructuredIntent`` schema. It is the
    primary decision maker in the cascade; keyword and embedding classifiers
    provide guardrails and alternatives.
    """

    def __init__(self, weight: float = 0.6, llm_client: Optional[LLMClient] = None):
        super().__init__(weight=weight)
        self._client = llm_client

    def _get_client(self) -> Optional[LLMClient]:
        if self._client is None:
            self._client = LLMClient()
        return self._client

    def is_available(self) -> bool:
        client = self._get_client()
        if client is None or not client.is_configured():
            return False
        # Local/self-hosted models are typically much slower; skip the optional
        # LLM intent classifier and rely on keyword + embedding classifiers.
        from homomics_lab.llm.runtime_config import is_local_llm_provider
        return not is_local_llm_provider()

    async def classify(
        self,
        message: str,
        definitions: List[IntentDefinition],
        context: Dict[str, Any],
    ) -> List[IntentMatch]:
        client = self._get_client()
        if client is None or not client.is_configured():
            return []

        from homomics_lab.agent.intent.prompts import build_classification_prompt

        prompt = build_classification_prompt(definitions, context, message)

        try:
            raw = await client.chat_completion(
                messages=[
                    {"role": "system", "content": prompt},
                ],
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            parsed = json.loads(raw)
        except Exception:
            return []

        matches = []
        primary = parsed.get("primary_intent", {})
        # Robust fallback: some models return a flat object instead of the
        # documented primary_intent wrapper.
        if not primary and "intent_type" in parsed:
            primary = parsed
        if not primary and "intent" in parsed:
            primary = {
                "intent_type": parsed.get("intent"),
                "interaction_mode": parsed.get("interaction_mode"),
                "domain": parsed.get("domain"),
                "target": parsed.get("target"),
                "scope": parsed.get("scope", "single_step"),
                "entities": parsed.get("entities", {}),
                "confidence": parsed.get("confidence", 0.0),
                "reason": parsed.get("reason", ""),
                "needs_clarification": parsed.get("needs_clarification", False),
            }
        if primary and primary.get("intent_type"):
            structured = self._parse_structured_intent(primary)
            matches.append(
                IntentMatch(
                    analysis_type=structured.to_legacy_analysis_type(),
                    confidence=structured.confidence,
                    source="llm",
                    reason=structured.reason,
                    weight=self.weight,
                    structured=structured,
                )
            )

        for alt in parsed.get("alternative_intents", []):
            if alt.get("intent_type"):
                structured = self._parse_structured_intent(alt)
                matches.append(
                    IntentMatch(
                        analysis_type=structured.to_legacy_analysis_type(),
                        confidence=structured.confidence,
                        source="llm",
                        reason="alternative",
                        weight=self.weight,
                        structured=structured,
                    )
                )

        # Propagate sub-intents as additional matches so the analyzer can build
        # a multi-step workflow when the LLM detects one.
        for sub in parsed.get("sub_intents", []):
            if sub.get("intent_type"):
                structured = self._parse_structured_intent(sub)
                matches.append(
                    IntentMatch(
                        analysis_type=structured.to_legacy_analysis_type(),
                        confidence=structured.confidence,
                        source="llm",
                        reason="sub_intent",
                        weight=self.weight,
                        structured=structured,
                    )
                )

        matches.sort(key=lambda m: m.confidence, reverse=True)
        return matches

    @staticmethod
    def _parse_structured_intent(data: Dict[str, Any]) -> StructuredIntent:
        """Parse a JSON intent object into a StructuredIntent."""
        entities = data.get("entities") or {}
        if not isinstance(entities, dict):
            # LLMs occasionally return entities as a string or a list; coerce to
            # a safe dict so downstream metadata merging never crashes.
            entities = {"_raw": entities}
        return StructuredIntent(
            intent_type=data.get("intent_type", "general"),
            interaction_mode=data.get("interaction_mode", "answer"),
            domain=data.get("domain") or None,
            target=data.get("target") or None,
            scope=data.get("scope", "single_step"),
            entities=entities,
            confidence=float(data.get("confidence", 0.0)),
            reason=data.get("reason", ""),
        )
