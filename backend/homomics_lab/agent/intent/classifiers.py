"""Intent classifiers: keyword, embedding, and LLM-based."""

import json
import re
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Any, Dict, List, Optional

from homomics_lab.agent.intent.models import IntentDefinition, IntentMatch
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
    """Keyword-based intent classifier with weighted matching and negation."""

    # Strong domain-agnostic signals
    DOMAIN_KEYWORDS: Dict[str, List[str]] = {
        "qa": [
            "什么是", "what is", "有哪些", "what are", "包括哪些",
            "怎么", "如何", "how to", "how do", "explain", "what is",
            "告诉我", "介绍", "概述", " overview", "include",
            "单细胞转录组有哪些分析内容",
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

    NEGATIVE_SIGNALS: Dict[str, List[str]] = {
        "qa": ["generate code", "写代码", "code snippet", "脚本"],
        "general_help": ["什么是", "what is", "how does", "解释", "有哪些", "what are"],
    }

    # Information-seeking patterns that should suppress workflow execution intents.
    INFORMATION_REQUEST_PATTERNS: List[str] = [
        r"有哪些分析内容",
        r"有哪些步骤",
        r"包括哪些",
        r"什么是.*分析",
        r"介绍一下.*分析",
        r".*是什么",
        r".*有哪些",
    ]

    def __init__(self, weight: float = 0.3):
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
            matches = [kw for kw in keywords if kw.lower() in text]
            if matches:
                scores[analysis_type] += len(matches) * 0.8
                reasons[analysis_type] = f"matched keywords: {', '.join(matches)}"

        # Domain-specific keywords
        for definition in definitions:
            atype = definition.analysis_type
            keyword_matches = []
            for kw in definition.keywords:
                if kw.lower() in text:
                    keyword_matches.append(kw)
                    scores[atype] += 1.0

            if keyword_matches:
                reasons[atype] = f"matched keywords: {', '.join(keyword_matches)}"

            # Complexity indicators boost confidence for multi-step requests
            complexity_hits = [
                kw for kw in definition.complexity_indicators
                if kw.lower() in text
            ]
            if complexity_hits:
                scores[atype] += len(complexity_hits) * 0.2

        # Apply negation penalties. For example, "generate code" should suppress
        # a QA classification even if the message also contains "explain".
        for target_type, neg_keywords in self.NEGATIVE_SIGNALS.items():
            if target_type in scores and any(kw in text for kw in neg_keywords):
                scores[target_type] *= 0.3
                reasons[target_type] = reasons.get(target_type, "") + " (negated by opposing signals)"

        # Strong information-request patterns should suppress workflow/analysis intents.
        is_info_request = any(re.search(p, message) for p in self.INFORMATION_REQUEST_PATTERNS)
        if is_info_request:
            workflow_types = {
                "single_cell_analysis", "spatial_analysis", "metagenomics_analysis",
                "genomics_analysis", "proteomics_analysis", "transcriptomics_analysis",
            }
            for atype in list(scores):
                if atype in workflow_types:
                    scores[atype] *= 0.2
                    reasons[atype] = reasons.get(atype, "") + " (suppressed by information-request pattern)"
            if "qa" not in scores:
                scores["qa"] = 0.8
                reasons["qa"] = "information-request pattern detected"

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
            )
            for atype, score in scores.items()
            if score > 0
        ]
        matches.sort(key=lambda m: m.confidence, reverse=True)
        return matches


class EmbeddingIntentClassifier(IntentClassifier):
    """Embedding-based semantic intent classifier.

    Uses sentence-transformers when available and configured; otherwise falls
    back to TF-IDF + cosine similarity so tests and offline usage still work.
    """

    def __init__(self, weight: float = 0.3, model_name: Optional[str] = None):
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
            matches.append(
                IntentMatch(
                    analysis_type=atype,
                    confidence=float(min(1.0, score)),
                    source="embedding",
                    reason=f"semantic similarity {score:.2f}",
                    weight=self.weight,
                )
            )
        return matches


class LLMIntentClassifier(IntentClassifier):
    """LLM-based intent classifier with structured JSON output."""

    def __init__(self, weight: float = 0.4, llm_client: Optional[LLMClient] = None):
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
        if primary and primary.get("analysis_type"):
            matches.append(
                IntentMatch(
                    analysis_type=primary["analysis_type"],
                    confidence=float(primary.get("confidence", 0.0)),
                    source="llm",
                    reason=primary.get("reason", ""),
                    weight=self.weight,
                )
            )

        for alt in parsed.get("alternative_intents", []):
            if alt.get("analysis_type"):
                matches.append(
                    IntentMatch(
                        analysis_type=alt["analysis_type"],
                        confidence=float(alt.get("confidence", 0.0)),
                        source="llm",
                        reason="alternative",
                        weight=self.weight,
                    )
                )

        matches.sort(key=lambda m: m.confidence, reverse=True)
        return matches
