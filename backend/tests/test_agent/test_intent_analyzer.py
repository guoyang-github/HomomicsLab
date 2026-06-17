import pytest

from homomics_lab.agent.intent_analyzer import IntentAnalyzer


@pytest.fixture
def analyzer():
    return IntentAnalyzer(use_domain_registry=False)


@pytest.fixture
def analyzer_with_single_cell_domain(analyzer):
    analyzer.register_intent(
        "single_cell_analysis",
        {
            "domain": "single_cell_standard",
            "keywords": [
                "单细胞",
                "single cell",
                "scRNA",
                "10x",
                "scanpy",
                "seurat",
                "PBMC",
                "细胞",
                "cell",
            ],
            "complexity_indicators": [
                "分析",
                "analysis",
                "流程",
                "pipeline",
                "全流程",
                "完整",
            ],
            "data_scale_patterns": [
                r"(\d+)\s*个细胞",
                r"(\d+)\s*cells",
                r"(\d+)k\s*cells",
            ],
        },
    )
    analyzer.register_intent(
        "file_conversion",
        {
            "domain": "general",
            "keywords": ["转换", "convert", "格式", "format", "变成", "转成"],
            "complexity_indicators": [],
            "data_scale_patterns": [],
        },
    )
    return analyzer


@pytest.mark.asyncio
async def test_detect_single_cell_analysis(analyzer_with_single_cell_domain):
    intent = await analyzer_with_single_cell_domain.analyze("帮我分析这组单细胞数据")
    assert intent.analysis_type == "single_cell_analysis"
    assert intent.complexity == "complex"


@pytest.mark.asyncio
async def test_detect_simple_task(analyzer_with_single_cell_domain):
    intent = await analyzer_with_single_cell_domain.analyze("把文件转换成 h5ad 格式")
    assert intent.analysis_type == "file_conversion"
    assert intent.complexity == "single_step"


@pytest.mark.asyncio
async def test_detect_qa(analyzer):
    intent = await analyzer.analyze("什么是 UMAP？")
    assert intent.analysis_type == "qa"
    assert intent.complexity == "direct_response"


@pytest.mark.asyncio
async def test_detect_generic(analyzer):
    intent = await analyzer.analyze("hello world")
    # Unknown input triggers active clarification in the new cascade analyzer.
    assert intent.analysis_type in ("general", "clarification")
    assert intent.confidence >= 0.0


@pytest.mark.asyncio
async def test_detect_general_help_chinese(analyzer):
    intent = await analyzer.analyze("帮我写个 Python 脚本过滤 CSV")
    assert intent.analysis_type == "general_help"
    assert intent.complexity == "direct_response"


@pytest.mark.asyncio
async def test_detect_general_help_english(analyzer):
    intent = await analyzer.analyze("generate code to rename sample files")
    assert intent.analysis_type == "general_help"
    assert intent.complexity == "direct_response"


@pytest.mark.asyncio
async def test_general_help_overrides_unknown_domain(analyzer):
    """Coding requests should be recognized as general help even without domain knowledge."""
    intent = await analyzer.analyze("show me an example of parsing a tsv file")
    assert intent.analysis_type == "general_help"
    assert intent.complexity == "direct_response"


@pytest.mark.asyncio
async def test_structured_intent_fields_for_qa(analyzer):
    intent = await analyzer.analyze("什么是 UMAP？")
    assert intent.interaction_mode == "answer"
    assert intent.scope == "single_step"
    assert intent.target == "answer_question"


@pytest.mark.asyncio
async def test_structured_intent_fields_for_execution(analyzer_with_single_cell_domain):
    intent = await analyzer_with_single_cell_domain.analyze("帮我分析这组单细胞数据")
    assert intent.analysis_type == "single_cell_analysis"
    assert intent.interaction_mode == "execute"
    assert intent.domain == "single_cell_standard"
    assert intent.scope == "full"


@pytest.mark.asyncio
async def test_structured_intent_fields_for_single_step(analyzer_with_single_cell_domain):
    intent = await analyzer_with_single_cell_domain.analyze("把文件转换成 h5ad 格式")
    assert intent.analysis_type == "file_conversion"
    assert intent.interaction_mode == "execute"
    assert intent.scope == "single_step"
    assert intent.target == "convert_file"
