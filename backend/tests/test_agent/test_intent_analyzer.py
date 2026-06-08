import pytest
from homics_lab.agent.intent_analyzer import IntentAnalyzer


@pytest.fixture
def analyzer():
    return IntentAnalyzer()


@pytest.mark.asyncio
async def test_detect_single_cell_analysis(analyzer):
    intent = await analyzer.analyze("帮我分析这组单细胞数据")
    assert intent.analysis_type == "single_cell_analysis"
    assert intent.complexity == "complex"


@pytest.mark.asyncio
async def test_detect_simple_task(analyzer):
    intent = await analyzer.analyze("把文件转换成 h5ad 格式")
    assert intent.analysis_type == "file_conversion"
    assert intent.complexity == "single_step"


@pytest.mark.asyncio
async def test_detect_qa(analyzer):
    intent = await analyzer.analyze("什么是 UMAP？")
    assert intent.analysis_type == "qa"
    assert intent.complexity == "direct_response"
