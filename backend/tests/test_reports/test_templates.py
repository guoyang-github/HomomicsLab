"""Tests for report template engine."""

import pytest
from datetime import datetime

from homomics_lab.reports.models import (
    AnalysisReport,
    AnalysisStep,
    ReportFigure,
    ReportMetadata,
    ReportSection,
    ReportTable,
    SectionType,
)
from homomics_lab.reports.templates import ReportTemplateEngine


@pytest.fixture
def sample_report():
    report = AnalysisReport(
        id="rpt001",
        title="Single Cell RNA-seq Analysis",
        metadata=ReportMetadata(
            project_name="Tumor Microenvironment",
            analysis_type="single_cell_rna",
            author="HomomicsLab Agent",
            created_at=datetime(2024, 6, 1, 10, 0),
            tags=["scRNA", "tumor"],
            parameters={"resolution": 0.8, "n_pcs": 30},
        ),
        summary="Analysis of 10,000 cells identified 12 clusters.",
    )
    report.analysis_steps = [
        AnalysisStep(
            step_number=1,
            name="QC",
            description="Quality control filtering",
            skill_id="scanpy_qc",
            status="completed",
            duration_seconds=12.5,
        ),
        AnalysisStep(
            step_number=2,
            name="Clustering",
            description="Louvain clustering",
            skill_id="scanpy_cluster",
            status="completed",
            duration_seconds=45.0,
        ),
    ]
    report.add_section(
        ReportSection(
            title="Clustering Results",
            type=SectionType.RESULTS,
            content="Identified 12 cell clusters.",
            figures=[
                ReportFigure(
                    image_base64="iVBORw0KGgo=",
                    caption="UMAP clustering",
                    figure_type="umap",
                )
            ],
            tables=[
                ReportTable(
                    headers=["Cluster", "Count"],
                    rows=[["0", 1500], ["1", 2300]],
                    caption="Cluster sizes",
                )
            ],
        )
    )
    return report


class TestReportTemplateEngine:
    def test_render_html_contains_title(self, sample_report):
        engine = ReportTemplateEngine()
        html = engine.render_html(sample_report)
        assert "Single Cell RNA-seq Analysis" in html
        assert "<!DOCTYPE html>" in html

    def test_render_html_contains_metadata(self, sample_report):
        engine = ReportTemplateEngine()
        html = engine.render_html(sample_report)
        assert "Tumor Microenvironment" in html
        assert "single cell rna" in html.lower() or "Single Cell Rna" in html
        assert "HomomicsLab Agent" in html

    def test_render_html_contains_summary(self, sample_report):
        engine = ReportTemplateEngine()
        html = engine.render_html(sample_report)
        assert "Analysis of 10,000 cells identified 12 clusters" in html

    def test_render_html_contains_timeline(self, sample_report):
        engine = ReportTemplateEngine()
        html = engine.render_html(sample_report)
        assert "QC" in html
        assert "Clustering" in html
        assert "scanpy_qc" in html
        assert "12.5s" in html or "12.5" in html

    def test_render_html_contains_figure(self, sample_report):
        engine = ReportTemplateEngine()
        html = engine.render_html(sample_report)
        assert "UMAP clustering" in html
        assert "data:image/png;base64,iVBORw0KGgo=" in html

    def test_render_html_contains_table(self, sample_report):
        engine = ReportTemplateEngine()
        html = engine.render_html(sample_report)
        assert "Cluster sizes" in html
        assert "Cluster" in html
        assert "Count" in html
        assert "1500" in html

    def test_render_html_contains_parameters(self, sample_report):
        engine = ReportTemplateEngine()
        html = engine.render_html(sample_report)
        assert "resolution" in html
        assert "0.8" in html
        assert "n_pcs" in html
        assert "30" in html

    def test_render_markdown_contains_title(self, sample_report):
        engine = ReportTemplateEngine()
        md = engine.render_markdown(sample_report)
        assert "# Single Cell RNA-seq Analysis" in md

    def test_render_markdown_contains_timeline(self, sample_report):
        engine = ReportTemplateEngine()
        md = engine.render_markdown(sample_report)
        assert "QC" in md
        assert "Clustering" in md

    def test_render_markdown_contains_table(self, sample_report):
        engine = ReportTemplateEngine()
        md = engine.render_markdown(sample_report)
        assert "| Cluster | Count |" in md
        assert "| 0 | 1500 |" in md

    def test_render_empty_report(self):
        report = AnalysisReport(id="empty", title="Empty Report")
        engine = ReportTemplateEngine()
        html = engine.render_html(report)
        assert "Empty Report" in html
        assert "<!DOCTYPE html>" in html

    def test_markdown_to_html_basic(self):
        engine = ReportTemplateEngine()
        md = "# Title\n\nSome paragraph.\n\n- Item 1\n- Item 2"
        html = engine._markdown_to_html(md)
        assert "<h1>Title</h1>" in html
        assert "<p>Some paragraph.</p>" in html
        assert "<ul>" in html
        assert "<li>Item 1</li>" in html

    def test_fmt_cell_float(self):
        engine = ReportTemplateEngine()
        assert engine._fmt_cell(3.14159) == "3.142"
        assert engine._fmt_cell(1000000.0) == "1e+06"

    def test_fmt_cell_none(self):
        engine = ReportTemplateEngine()
        assert engine._fmt_cell(None) == ""
