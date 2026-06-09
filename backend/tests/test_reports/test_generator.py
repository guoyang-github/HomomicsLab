"""Tests for report generator."""

import pytest
from datetime import datetime

from homomics_lab.reports.generator import ReportGenerator
from homomics_lab.reports.models import (
    AnalysisReport,
    ReportFigure,
    ReportSection,
    ReportTable,
    SectionType,
)
from homomics_lab.viz.generator import PlotType


@pytest.fixture
def generator():
    return ReportGenerator()


class TestReportGenerator:
    def test_create_report(self, generator):
        report = generator.create_report(
            title="Test Report",
            project_name="Project A",
            analysis_type="single_cell",
        )
        assert isinstance(report, AnalysisReport)
        assert report.title == "Test Report"
        assert report.metadata.project_name == "Project A"
        assert report.metadata.analysis_type == "single_cell"
        assert len(report.id) == 8

    def test_add_executive_summary(self, generator):
        report = generator.create_report(title="Test")
        generator.add_executive_summary(report, "Summary text")
        assert report.summary == "Summary text"

    def test_add_section(self, generator):
        report = generator.create_report(title="Test")
        section = generator.add_section(
            report=report,
            title="Results",
            content="Some results",
            section_type=SectionType.RESULTS,
        )
        assert isinstance(section, ReportSection)
        assert section.title == "Results"
        assert len(report.sections) == 1

    def test_add_analysis_step(self, generator):
        report = generator.create_report(title="Test")
        step = generator.add_analysis_step(
            report=report,
            name="QC",
            skill_id="scanpy_qc",
            status="completed",
            duration_seconds=10.5,
        )
        assert step.step_number == 1
        assert step.name == "QC"
        assert step.status == "completed"
        assert step.duration_seconds == 10.5
        assert len(report.analysis_steps) == 1

    def test_multiple_steps_numbered(self, generator):
        report = generator.create_report(title="Test")
        generator.add_analysis_step(report, "Step 1")
        generator.add_analysis_step(report, "Step 2")
        assert report.analysis_steps[0].step_number == 1
        assert report.analysis_steps[1].step_number == 2

    def test_create_table(self, generator):
        table = generator.create_table(
            headers=["A", "B"],
            rows=[[1, 2], [3, 4]],
            caption="Test table",
        )
        assert isinstance(table, ReportTable)
        assert table.headers == ["A", "B"]
        assert table.caption == "Test table"

    def test_create_figure_from_plot_bar(self, generator):
        figure = generator.create_figure_from_plot(
            plot_type=PlotType.BAR,
            data={"categories": ["A", "B"], "values": [10, 20]},
            caption="Bar chart",
            title="Test Bar",
        )
        assert isinstance(figure, ReportFigure)
        assert figure.caption == "Bar chart"
        assert figure.figure_type == "bar"
        assert len(figure.image_base64) > 100

    def test_create_figure_from_plot_scatter(self, generator):
        figure = generator.create_figure_from_plot(
            plot_type=PlotType.SCATTER,
            data={"x": [1, 2, 3], "y": [1, 4, 9]},
            caption="Scatter plot",
        )
        assert isinstance(figure, ReportFigure)
        assert figure.figure_type == "scatter"

    def test_generate_html(self, generator):
        report = generator.create_report(title="HTML Test")
        generator.add_section(report, "Section 1", "Content")
        html = generator.generate_html(report)
        assert "<!DOCTYPE html>" in html
        assert "HTML Test" in html
        assert "Section 1" in html

    def test_generate_markdown(self, generator):
        report = generator.create_report(title="MD Test")
        generator.add_section(report, "Section 1", "Content")
        md = generator.generate_markdown(report)
        assert "# MD Test" in md
        assert "## Section 1" in md
        assert "Content" in md

    def test_build_from_pipeline(self, generator):
        steps = [
            {
                "name": "QC",
                "description": "Quality control",
                "skill_id": "qc_skill",
                "status": "completed",
                "duration_seconds": 12.0,
            },
            {
                "name": "Clustering",
                "description": "Cell clustering",
                "skill_id": "cluster_skill",
                "status": "completed",
                "duration_seconds": 45.0,
            },
        ]
        report = generator.build_from_pipeline(
            title="Pipeline Report",
            steps=steps,
            project_name="Test Project",
            analysis_type="single_cell",
            parameters={"resolution": 0.8},
        )
        assert report.title == "Pipeline Report"
        assert report.metadata.project_name == "Test Project"
        assert len(report.analysis_steps) == 2
        assert "2 steps" in report.summary
        assert "2 completed successfully" in report.summary
        assert "57.0 seconds" in report.summary

    def test_build_from_pipeline_with_failed_steps(self, generator):
        steps = [
            {
                "name": "QC",
                "status": "completed",
                "duration_seconds": 10.0,
            },
            {
                "name": "Analysis",
                "status": "failed",
                "duration_seconds": 5.0,
            },
        ]
        report = generator.build_from_pipeline(
            title="Failed Pipeline",
            steps=steps,
        )
        assert "1 failed" in report.summary

    def test_build_from_pipeline_with_figures(self, generator):
        steps = [
            {
                "name": "Plotting",
                "status": "completed",
                "figures": [
                    {
                        "image_base64": "abc123",
                        "caption": "Test figure",
                        "figure_type": "umap",
                    }
                ],
                "tables": [
                    {
                        "headers": ["A"],
                        "rows": [[1]],
                        "caption": "Test table",
                    }
                ],
            }
        ]
        report = generator.build_from_pipeline(
            title="With Figures",
            steps=steps,
        )
        results_sections = [s for s in report.sections if s.type == SectionType.RESULTS]
        assert len(results_sections) == 1
        assert len(results_sections[0].figures) == 1
        assert len(results_sections[0].tables) == 1
