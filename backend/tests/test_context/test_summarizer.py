import pytest
from homics_lab.context.summarizer import ContextSummarizer


@pytest.fixture
def summarizer():
    return ContextSummarizer(max_length=500)


def test_summarize_results(summarizer):
    text = """
    Performed QC on PBMC 3k dataset. Started with 2700 cells.
    Filtered cells with fewer than 200 genes and genes expressed in fewer than 3 cells.
    Removed cells with mitochondrial content above 5%.
    Final dataset contains 2531 cells and 13714 genes.
    """

    summary = summarizer.summarize(text, summary_type="result")
    assert any("2531 cells" in c or "13714 genes" in c for c in summary.key_conclusions)


def test_preserves_parameters(summarizer):
    text = "QC parameters: min_genes=200, min_cells=3, mt_threshold=0.05"
    summary = summarizer.summarize(text, summary_type="method")
    assert summary.key_parameters.get("min_genes") == "200"
