"""Report generator for bioinformatics analysis pipelines."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from homomics_lab.viz.generator import PlotGenerator, PlotType

from .models import (
    AnalysisReport,
    AnalysisStep,
    ReportFigure,
    ReportMetadata,
    ReportSection,
    ReportTable,
    SectionType,
)
from .templates import ReportTemplateEngine


class ReportGenerator:
    """Generate analysis reports from pipeline results."""

    def __init__(self):
        self.template_engine = ReportTemplateEngine()
        self.plot_generator = PlotGenerator()

    def create_report(
        self,
        title: str,
        project_name: str = "",
        analysis_type: str = "",
        author: str = "HomomicsLab Agent",
        parameters: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
    ) -> AnalysisReport:
        """Create a new empty report."""
        return AnalysisReport(
            id=str(uuid.uuid4())[:8],
            title=title,
            metadata=ReportMetadata(
                project_name=project_name,
                analysis_type=analysis_type,
                author=author,
                parameters=parameters or {},
                tags=tags or [],
            ),
        )

    def add_executive_summary(self, report: AnalysisReport, summary: str) -> None:
        """Add an executive summary to the report."""
        report.summary = summary

    def add_section(
        self,
        report: AnalysisReport,
        title: str,
        content: str = "",
        section_type: SectionType = SectionType.CUSTOM,
        figures: Optional[List[ReportFigure]] = None,
        tables: Optional[List[ReportTable]] = None,
    ) -> ReportSection:
        """Add a section to the report."""
        section = ReportSection(
            title=title,
            type=section_type,
            content=content,
            figures=figures or [],
            tables=tables or [],
        )
        report.add_section(section)
        return section

    def add_analysis_step(
        self,
        report: AnalysisReport,
        name: str,
        description: str = "",
        skill_id: str = "",
        status: str = "",
        duration_seconds: Optional[float] = None,
        inputs: Optional[Dict[str, Any]] = None,
        outputs: Optional[Dict[str, Any]] = None,
    ) -> AnalysisStep:
        """Record an analysis step in the pipeline timeline."""
        step = AnalysisStep(
            step_number=len(report.analysis_steps) + 1,
            name=name,
            description=description,
            skill_id=skill_id,
            status=status,
            duration_seconds=duration_seconds,
            inputs=inputs or {},
            outputs=outputs or {},
        )
        report.analysis_steps.append(step)
        return step

    def create_table(
        self,
        headers: List[str],
        rows: List[List[Any]],
        caption: str = "",
    ) -> ReportTable:
        """Create a data table for embedding in a report."""
        return ReportTable(headers=headers, rows=rows, caption=caption)

    def create_figure_from_plot(
        self,
        plot_type: PlotType,
        data: Dict[str, Any],
        caption: str = "",
        title: str = "",
        width: int = 8,
        height: int = 6,
        dpi: int = 100,
    ) -> ReportFigure:
        """Generate a plot and wrap it as a report figure."""
        image_base64 = self.plot_generator.generate(
            plot_type=plot_type,
            data=data,
            title=title,
            width=width,
            height=height,
            dpi=dpi,
        )
        return ReportFigure(
            image_base64=image_base64,
            caption=caption,
            figure_type=plot_type.value,
            width=width * dpi,
            height=height * dpi,
        )

    def generate_html(self, report: AnalysisReport) -> str:
        """Generate final HTML report."""
        return self.template_engine.render_html(report)

    def generate_markdown(self, report: AnalysisReport) -> str:
        """Generate final Markdown report."""
        return self.template_engine.render_markdown(report)

    def generate_pdf(self, report: AnalysisReport) -> bytes:
        """Generate final PDF report."""
        return self.template_engine.render_pdf(report)

    def build_from_pipeline(
        self,
        title: str,
        steps: List[Dict[str, Any]],
        project_name: str = "",
        analysis_type: str = "",
        parameters: Optional[Dict[str, Any]] = None,
    ) -> AnalysisReport:
        """Build a complete report from a pipeline execution summary.

        Args:
            title: Report title
            steps: List of step dicts with keys: name, description, skill_id,
                   status, duration_seconds, inputs, outputs, figures, tables
            project_name: Project name
            analysis_type: Type of analysis
            parameters: Analysis parameters

        Returns:
            Complete AnalysisReport
        """
        report = self.create_report(
            title=title,
            project_name=project_name,
            analysis_type=analysis_type,
            parameters=parameters,
        )

        # Add analysis steps
        for step_data in steps:
            self.add_analysis_step(
                report=report,
                name=step_data["name"],
                description=step_data.get("description", ""),
                skill_id=step_data.get("skill_id", ""),
                status=step_data.get("status", ""),
                duration_seconds=step_data.get("duration_seconds"),
                inputs=step_data.get("inputs"),
                outputs=step_data.get("outputs"),
            )

        # Build executive summary
        completed = sum(1 for s in report.analysis_steps if s.status == "completed")
        failed = sum(1 for s in report.analysis_steps if s.status == "failed")
        total_time = sum(
            (s.duration_seconds or 0) for s in report.analysis_steps
        )

        summary_parts = [
            f"This report documents a **{analysis_type.replace('_', ' ')}** analysis",
        ]
        if project_name:
            summary_parts[-1] += f" for project **{project_name}**"
        summary_parts[-1] += "."
        summary_parts.append(
            f"\nThe analysis pipeline consisted of **{len(steps)} steps**, "
            f"of which **{completed} completed successfully**"
        )
        if failed:
            summary_parts[-1] += f" and **{failed} failed**"
        summary_parts[-1] += "."
        if total_time > 0:
            summary_parts.append(
                f"\nTotal execution time: **{total_time:.1f} seconds**."
            )

        self.add_executive_summary(report, "\n".join(summary_parts))

        # Add results section with figures and tables
        for step_data in steps:
            figures = step_data.get("figures", [])
            tables = step_data.get("tables", [])
            if figures or tables:
                section = self.add_section(
                    report=report,
                    title=f"Results: {step_data['name']}",
                    section_type=SectionType.RESULTS,
                    content=step_data.get("description", ""),
                )
                for fig_data in figures:
                    if "image_base64" in fig_data:
                        section.figures.append(
                            ReportFigure(**fig_data)
                        )
                for tbl_data in tables:
                    section.tables.append(
                        ReportTable(**tbl_data)
                    )

        return report
