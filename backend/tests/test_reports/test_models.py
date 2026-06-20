"""Tests for report data models."""

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


class TestReportModels:
    def test_create_report(self):
        report = AnalysisReport(id="rpt001", title="Test Report")
        assert report.id == "rpt001"
        assert report.title == "Test Report"
        assert report.sections == []
        assert report.analysis_steps == []
        assert report.summary == ""

    def test_report_metadata_defaults(self):
        meta = ReportMetadata()
        assert meta.author == "HomomicsLab Agent"
        assert meta.version == "1.0"
        assert meta.tags == []
        assert meta.parameters == {}
        assert isinstance(meta.created_at, datetime)

    def test_add_section(self):
        report = AnalysisReport(id="rpt001", title="Test")
        section = ReportSection(title="Results", type=SectionType.RESULTS, content="Some results")
        report.add_section(section)
        assert len(report.sections) == 1
        assert report.sections[0].title == "Results"

    def test_get_section_by_type(self):
        report = AnalysisReport(id="rpt001", title="Test")
        report.add_section(ReportSection(title="Methods", type=SectionType.METHODOLOGY))
        report.add_section(ReportSection(title="Results", type=SectionType.RESULTS))

        found = report.get_section(SectionType.RESULTS)
        assert found is not None
        assert found.title == "Results"

        not_found = report.get_section(SectionType.CONCLUSION)
        assert not_found is None

    def test_report_table(self):
        table = ReportTable(
            headers=["Gene", "Expression"],
            rows=[["TP53", 12.5], ["BRCA1", 8.3]],
            caption="Gene expression table",
        )
        assert table.headers == ["Gene", "Expression"]
        assert len(table.rows) == 2
        assert table.caption == "Gene expression table"

    def test_report_figure(self):
        fig = ReportFigure(
            image_base64="iVBORw0KGgo=",
            caption="UMAP plot",
            figure_type="umap",
            width=800,
            height=600,
        )
        assert fig.caption == "UMAP plot"
        assert fig.width == 800
        assert fig.height == 600

    def test_analysis_step(self):
        step = AnalysisStep(
            step_number=1,
            name="Quality Control",
            skill_id="qc_skill",
            status="completed",
            duration_seconds=45.2,
        )
        assert step.step_number == 1
        assert step.name == "Quality Control"
        assert step.status == "completed"
        assert step.duration_seconds == 45.2

    def test_report_to_dict(self):
        report = AnalysisReport(
            id="rpt001",
            title="Test",
            metadata=ReportMetadata(project_name="Proj A"),
        )
        data = report.to_dict()
        assert data["id"] == "rpt001"
        assert data["title"] == "Test"
        assert data["metadata"]["project_name"] == "Proj A"


class TestSectionType:
    def test_section_type_values(self):
        assert SectionType.EXECUTIVE_SUMMARY.value == "executive_summary"
        assert SectionType.METHODOLOGY.value == "methodology"
        assert SectionType.RESULTS.value == "results"
        assert SectionType.CONCLUSION.value == "conclusion"
        assert SectionType.CUSTOM.value == "custom"
