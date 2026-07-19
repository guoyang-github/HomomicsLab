"""Tests for intent result caching, parallel classification, and prompt slimming."""

import asyncio
import json

import pytest

from homomics_lab.agent.intent import prompts as intent_prompts
from homomics_lab.agent.intent.analyzer import CascadeIntentAnalyzer
from homomics_lab.agent.intent.classifiers import (
    IntentClassifier,
    LLMIntentClassifier,
)
from homomics_lab.agent.intent.models import IntentDefinition, IntentMatch, intent_strategy_key
from homomics_lab.agent.intent.result_cache import IntentResultCache
from homomics_lab.llm_client import LLMClient


@pytest.fixture(autouse=True)
def _non_local_llm(monkeypatch):
    """Ensure the LLM classifier is not skipped as a local provider."""
    monkeypatch.setattr(
        "homomics_lab.llm.runtime_config.is_local_llm_provider", lambda *a, **k: False
    )


class CountingClient:
    """LLM client stub that counts calls and returns a canned intent payload."""

    def __init__(self, payload=None):
        self.calls = 0
        self._payload = payload or {
            "primary_intent": {
                "intent_type": "analysis",
                "interaction_mode": "execute",
                "domain": "single-cell-transcriptomics",
                "target": "single_cell_analysis",
                "scope": "full",
                "entities": {},
                "confidence": 0.95,
                "reason": "test payload",
            },
            "alternative_intents": [],
            "sub_intents": [],
            "needs_clarification": False,
        }

    def is_configured(self):
        return True

    async def chat_completion(self, *args, **kwargs):
        self.calls += 1
        return json.dumps(self._payload)


@pytest.fixture
def definitions():
    return [
        IntentDefinition(
            analysis_type="single_cell_analysis",
            keywords=["单细胞", "single cell"],
            examples=["帮我分析这组单细胞数据"],
            complexity_indicators=["流程"],
            domain="single-cell-transcriptomics",
        ),
        IntentDefinition(
            analysis_type="spatial_analysis",
            keywords=["空间", "spatial"],
            examples=["分析空间转录组数据"],
            domain="spatial-transcriptomics",
        ),
    ]


def _make_analyzer(definitions, client, cache):
    return CascadeIntentAnalyzer(
        definitions=definitions,
        use_domain_registry=False,
        llm_classifier=LLMIntentClassifier(llm_client=client),
        result_cache=cache,
    )


# ---------------------------------------------------------------------------
# Shared-client injection
# ---------------------------------------------------------------------------


def test_shared_llm_client_is_injected(definitions):
    client = CountingClient()
    analyzer = CascadeIntentAnalyzer(
        definitions=definitions,
        use_domain_registry=False,
        llm_client=client,
        result_cache=False,
    )
    assert analyzer.llm_classifier._get_client() is client


def test_classifier_builds_private_client_only_when_not_injected():
    classifier = LLMIntentClassifier()
    assert isinstance(classifier._get_client(), LLMClient)


# ---------------------------------------------------------------------------
# Result cache
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cache_hit_skips_llm_across_analyzer_instances(definitions):
    """A second analyzer (per-message rebuild) reuses the cached result."""
    client = CountingClient()
    cache = IntentResultCache()
    message = "zxqw 帮我跑一下这套流程"  # no keyword hits -> LLM path

    first = await _make_analyzer(definitions, client, cache).analyze(
        message, session_id="s1"
    )
    second = await _make_analyzer(definitions, client, cache).analyze(
        message, session_id="s1"
    )

    assert client.calls == 1
    assert intent_strategy_key(second) == intent_strategy_key(first) == "single_cell_analysis"
    assert second.confidence == first.confidence


@pytest.mark.asyncio
async def test_cached_result_is_isolated_from_caller_mutation(definitions):
    client = CountingClient()
    cache = IntentResultCache()
    message = "zxqw 帮我跑一下这套流程"

    first = await _make_analyzer(definitions, client, cache).analyze(
        message, session_id="s1"
    )
    first.metadata["polluted"] = True
    first.intent_type = "mutated"

    second = await _make_analyzer(definitions, client, cache).analyze(
        message, session_id="s1"
    )
    assert client.calls == 1
    assert intent_strategy_key(second) == "single_cell_analysis"
    assert "polluted" not in second.metadata


@pytest.mark.asyncio
async def test_cache_key_separates_sessions(definitions):
    client = CountingClient()
    cache = IntentResultCache()
    message = "zxqw 帮我跑一下这套流程"

    await _make_analyzer(definitions, client, cache).analyze(message, session_id="s1")
    await _make_analyzer(definitions, client, cache).analyze(message, session_id="s2")

    assert client.calls == 2


@pytest.mark.asyncio
async def test_cache_key_includes_recent_history(definitions):
    from homomics_lab.context.working_memory import WorkingMemory
    from homomics_lab.models.common import ChatMessage, MessageType

    client = CountingClient()
    cache = IntentResultCache()
    message = "zxqw 帮我跑一下这套流程"

    wm_a = WorkingMemory()
    wm_a.add_message(ChatMessage(id="m1", type=MessageType.TEXT, content="之前聊了质控", sender="user"))
    wm_b = WorkingMemory()
    wm_b.add_message(ChatMessage(id="m2", type=MessageType.TEXT, content="之前聊了聚类", sender="user"))

    await _make_analyzer(definitions, client, cache).analyze(
        message, working_memory=wm_a, session_id="s1"
    )
    await _make_analyzer(definitions, client, cache).analyze(
        message, working_memory=wm_b, session_id="s1"
    )
    # Different conversation fingerprints -> two LLM calls.
    assert client.calls == 2

    # Same history again -> cache hit, no third call.
    await _make_analyzer(definitions, client, cache).analyze(
        message, working_memory=wm_a, session_id="s1"
    )
    assert client.calls == 2


@pytest.mark.asyncio
async def test_cache_expires_after_ttl(definitions):
    client = CountingClient()
    cache = IntentResultCache(ttl_seconds=0.05)
    message = "zxqw 帮我跑一下这套流程"
    analyzer = _make_analyzer(definitions, client, cache)

    await analyzer.analyze(message, session_id="s1")
    await asyncio.sleep(0.06)
    await analyzer.analyze(message, session_id="s1")

    assert client.calls == 2


@pytest.mark.asyncio
async def test_cache_can_be_disabled(definitions):
    client = CountingClient()
    message = "zxqw 帮我跑一下这套流程"
    analyzer = _make_analyzer(definitions, client, cache=False)

    await analyzer.analyze(message, session_id="s1")
    await analyzer.analyze(message, session_id="s1")

    assert client.calls == 2


@pytest.mark.asyncio
async def test_shared_default_cache_spans_analyzer_instances(definitions):
    """Default (module-level) cache is shared, matching production rebuilds."""
    client = CountingClient()
    message = "zxqw 默认缓存共享验证"

    await _make_analyzer(definitions, client, cache=None).analyze(message, session_id="s9")
    await _make_analyzer(definitions, client, cache=None).analyze(message, session_id="s9")

    assert client.calls == 1


# ---------------------------------------------------------------------------
# Parallel LLM + embedding classification
# ---------------------------------------------------------------------------


class _GatedEmbeddingClassifier(IntentClassifier):
    """Embedding stub that proves overlap with the LLM call via events."""

    def __init__(self, entered_self, entered_peer):
        super().__init__(weight=0.25)
        self._entered_self = entered_self
        self._entered_peer = entered_peer

    async def classify(self, message, definitions, context):
        self._entered_self.set()
        # If the cascade were still serial, the peer event would never be set
        # within the timeout and this would raise.
        await asyncio.wait_for(self._entered_peer.wait(), timeout=1.0)
        return [
            IntentMatch(
                analysis_type="spatial_analysis",
                confidence=0.9,
                source="embedding",
                reason="semantic similarity 0.90",
                weight=self.weight,
            )
        ]


class _GatedLLMClient(CountingClient):
    def __init__(self, entered_self, entered_peer, payload=None):
        super().__init__(payload=payload)
        self._entered_self = entered_self
        self._entered_peer = entered_peer

    async def chat_completion(self, *args, **kwargs):
        self._entered_self.set()
        await asyncio.wait_for(self._entered_peer.wait(), timeout=1.0)
        return await super().chat_completion(*args, **kwargs)


@pytest.mark.asyncio
async def test_llm_and_embedding_classify_concurrently_and_arbitrate(definitions):
    entered_llm = asyncio.Event()
    entered_embedding = asyncio.Event()
    client = _GatedLLMClient(entered_llm, entered_embedding)
    embedding = _GatedEmbeddingClassifier(entered_embedding, entered_llm)

    analyzer = CascadeIntentAnalyzer(
        definitions=definitions,
        use_domain_registry=False,
        llm_classifier=LLMIntentClassifier(llm_client=client),
        embedding_classifier=embedding,
        result_cache=False,
    )
    # No keyword hits -> no fast path; both classifiers must run.
    intent = await analyzer.analyze("zxqw 帮我跑一下这套流程", session_id="s1")

    # Both gates were crossed -> the two classifiers overlapped in time.
    assert entered_llm.is_set() and entered_embedding.is_set()
    assert client.calls == 1
    # Arbitration unchanged: the LLM match stays the primary intent; the
    # embedding match survives as an alternative.
    assert intent_strategy_key(intent) == "single_cell_analysis"
    assert intent.metadata["source"] == "llm"
    alt_types = {a["analysis_type"] for a in intent.metadata.get("alternatives", [])}
    assert "spatial_analysis" in alt_types


@pytest.mark.asyncio
async def test_embedding_only_when_llm_unavailable(definitions, monkeypatch):
    """Without a configured LLM the cascade still returns embedding results."""

    class _PlainEmbedding(IntentClassifier):
        async def classify(self, message, definitions, context):
            return [
                IntentMatch(
                    analysis_type="spatial_analysis",
                    confidence=0.6,
                    source="embedding",
                    reason="semantic similarity 0.60",
                    weight=self.weight,
                )
            ]

    unconfigured = LLMClient()
    monkeypatch.setattr(unconfigured, "is_configured", lambda: False)
    analyzer = CascadeIntentAnalyzer(
        definitions=definitions,
        use_domain_registry=False,
        llm_classifier=LLMIntentClassifier(llm_client=unconfigured),
        embedding_classifier=_PlainEmbedding(weight=0.25),
        result_cache=False,
    )
    intent = await analyzer.analyze("zxqw 看看这批材料", session_id="s1")
    assert intent_strategy_key(intent) == "spatial_analysis"
    assert intent.metadata["source"] == "embedding"


# ---------------------------------------------------------------------------
# Prompt top-K pre-filtering
# ---------------------------------------------------------------------------


@pytest.fixture
def many_definitions():
    defs = [
        IntentDefinition(
            analysis_type="single_cell_analysis",
            keywords=["单细胞", "single cell", "scRNA"],
            examples=["帮我分析这组单细胞数据"],
            domain="single-cell-transcriptomics",
        ),
        IntentDefinition(
            analysis_type="spatial_analysis",
            keywords=["空间", "spatial", "visium"],
            examples=["分析空间转录组数据"],
            domain="spatial-transcriptomics",
        ),
        IntentDefinition(
            analysis_type="metagenomics_analysis",
            keywords=["宏基因组", "16S", "amplicon"],
            examples=["做 16S 多样性分析"],
            domain="metagenomics",
        ),
        IntentDefinition(
            analysis_type="genomics_analysis",
            keywords=["基因组", "WGS", "variant"],
            examples=["做人基因组变异检测"],
            domain="genomics",
        ),
        IntentDefinition(
            analysis_type="proteomics_analysis",
            keywords=["蛋白组", "proteomics", "质谱"],
            examples=["做蛋白组定量"],
            domain="proteomics",
        ),
        IntentDefinition(
            analysis_type="transcriptomics_analysis",
            keywords=["转录组", "RNA-seq", "表达"],
            examples=["做 RNA-seq 差异表达"],
            domain="transcriptomics",
        ),
        IntentDefinition(
            analysis_type="file_conversion",
            keywords=["转换", "convert", "格式"],
            examples=["把 CSV 转成 h5ad"],
            domain="builtin",
        ),
        IntentDefinition(
            analysis_type="pubmed_search",
            keywords=["pubmed", "文献"],
            examples=["搜索 CRISPR 文献"],
            domain="builtin",
        ),
    ]
    return defs


def test_prefilter_returns_top_k_with_keyword_hits(many_definitions):
    selected = intent_prompts.prefilter_definitions(
        many_definitions, "帮我分析这组单细胞数据", top_k=5
    )
    assert len(selected) <= 5
    types = [d.analysis_type for d in selected]
    assert "single_cell_analysis" in types
    # Unrelated intents are excluded.
    assert "proteomics_analysis" not in types
    assert "pubmed_search" not in types


def test_prefilter_falls_back_to_full_list_without_hits(many_definitions):
    selected = intent_prompts.prefilter_definitions(many_definitions, "zxqw 无从下手")
    assert len(selected) == len(many_definitions)


def test_prefilter_disabled_when_top_k_none(many_definitions):
    selected = intent_prompts.prefilter_definitions(
        many_definitions, "帮我分析这组单细胞数据", top_k=None
    )
    assert len(selected) == len(many_definitions)


def test_classification_prompt_is_slimmed(many_definitions):
    full = intent_prompts.build_classification_prompt(
        many_definitions, {}, "帮我分析这组单细胞数据", top_k=None
    )
    slim = intent_prompts.build_classification_prompt(
        many_definitions, {}, "帮我分析这组单细胞数据", top_k=5
    )
    assert len(slim) < len(full)
    assert "single_cell_analysis" in slim
    assert "proteomics_analysis" not in slim
    # Zero-hit messages keep the full intent list.
    fallback = intent_prompts.build_classification_prompt(
        many_definitions, {}, "zxqw 无从下手", top_k=5
    )
    assert "proteomics_analysis" in fallback


@pytest.mark.asyncio
async def test_typical_messages_keep_expected_candidates(many_definitions):
    """Typical messages must keep their true intent in the slimmed prompt."""
    cases = {
        "帮我分析这组单细胞数据": "single_cell_analysis",
        "分析我的 visium 空间数据": "spatial_analysis",
        "做 16S 多样性分析": "metagenomics_analysis",
        "把 CSV 转成 h5ad": "file_conversion",
        "帮我搜索 CRISPR 的 pubmed 文献": "pubmed_search",
    }
    for message, expected in cases.items():
        selected = intent_prompts.prefilter_definitions(many_definitions, message, top_k=5)
        assert expected in [d.analysis_type for d in selected], message


@pytest.mark.asyncio
async def test_slimmed_prompt_does_not_change_llm_classification(definitions, many_definitions):
    """The LLM classifier result is unchanged when the prompt is slimmed."""
    captured = {}

    class _CapturingClient(CountingClient):
        async def chat_completion(self, *args, **kwargs):
            captured["prompt"] = kwargs.get("messages", [{}])[0].get("content", "")
            return await super().chat_completion(*args, **kwargs)

    client = _CapturingClient()
    classifier = LLMIntentClassifier(llm_client=client)
    matches = await classifier.classify(
        "帮我分析这组单细胞数据", many_definitions, {}
    )
    assert matches[0].analysis_type == "single_cell_analysis"
    # The slimmed prompt still names the matched intent.
    assert "single_cell_analysis" in captured["prompt"]
    assert "proteomics_analysis" not in captured["prompt"]
