"""Tests for the cascade intent analyzer."""

import pytest

from homomics_lab.agent.intent.analyzer import CascadeIntentAnalyzer
from homomics_lab.agent.intent.models import IntentDefinition, intent_strategy_key


@pytest.fixture
def definitions():
    return [
        IntentDefinition(
            analysis_type="single_cell_analysis",
            keywords=["单细胞", "single cell"],
            examples=["帮我分析这组单细胞数据", "run scRNA-seq QC and clustering"],
            complexity_indicators=["分析", "流程"],
            domain="single-cell-transcriptomics",
        ),
        IntentDefinition(
            analysis_type="file_conversion",
            keywords=["转换", "convert", "格式", "format", "变成", "转成"],
            examples=["把 CSV 转成 h5ad"],
            domain="general",
        ),
    ]


@pytest.fixture
def analyzer(definitions):
    return CascadeIntentAnalyzer(
        definitions=definitions,
        use_domain_registry=False,
        llm_classifier=None,  # disable LLM for deterministic tests
    )


@pytest.mark.asyncio
async def test_analyze_single_cell(analyzer):
    intent = await analyzer.analyze("帮我分析单细胞数据")
    assert intent_strategy_key(intent) == "single_cell_analysis"
    assert intent.confidence > 0
    assert intent.domain_knowledge == ["single-cell-transcriptomics"]


@pytest.mark.asyncio
async def test_analyze_file_conversion(analyzer):
    intent = await analyzer.analyze("把文件转成 h5ad 格式")
    assert intent.target == "convert_file"


@pytest.mark.asyncio
async def test_analyze_unknown_returns_general_or_clarification(analyzer):
    intent = await analyzer.analyze("hello world")
    # The keyword guardrail now confidently recognizes greetings as direct-response.
    assert intent_strategy_key(intent) in ("general", "clarification", "greeting")
    assert intent.interaction_mode == "answer"


@pytest.mark.asyncio
async def test_complexity_from_indicators(analyzer):
    intent = await analyzer.analyze("帮我做一个完整的单细胞分析流程")
    assert intent_strategy_key(intent) == "single_cell_analysis"
    assert intent.scope in ("partial", "full")


@pytest.mark.asyncio
async def test_data_scale_extraction(analyzer):
    intent = await analyzer.analyze("分析 5000 个细胞的单细胞数据")
    assert intent.data_scale == "5000 个细胞"
