"""API endpoints for report generation and management."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from homomics_lab.reports.generator import ReportGenerator
from homomics_lab.reports.models import (
    AnalysisReport,
    ReportFigure,
    ReportTable,
    SectionType,
)

router = APIRouter()


class CreateReportRequest(BaseModel):
    title: str
    project_name: str = ""
    analysis_type: str = ""
    author: str = "HomomicsLab Agent"
    parameters: Dict[str, Any] = {}
    tags: List[str] = []


class AddSectionRequest(BaseModel):
    title: str
    content: str = ""
    section_type: str = "custom"
    figures: List[Dict[str, Any]] = []
    tables: List[Dict[str, Any]] = []


class AddStepRequest(BaseModel):
    name: str
    description: str = ""
    skill_id: str = ""
    status: str = ""
    duration_seconds: Optional[float] = None


class GeneratePlotForReportRequest(BaseModel):
    plot_type: str
    data: Dict[str, Any]
    caption: str = ""
    title: str = ""
    width: int = 8
    height: int = 6
    dpi: int = 100


# In-memory storage for demo (replace with DB in production)
_reports_db: Dict[str, AnalysisReport] = {}


def _get_or_create_generator() -> ReportGenerator:
    return ReportGenerator()


@router.post("/create", response_model=Dict[str, Any])
async def create_report(request: CreateReportRequest):
    """Create a new analysis report."""
    generator = _get_or_create_generator()
    report = generator.create_report(
        title=request.title,
        project_name=request.project_name,
        analysis_type=request.analysis_type,
        author=request.author,
        parameters=request.parameters,
        tags=request.tags,
    )
    _reports_db[report.id] = report
    return {"report_id": report.id, "title": report.title, "message": "Report created"}


@router.get("/list")
async def list_reports():
    """List all reports."""
    return [
        {
            "id": r.id,
            "title": r.title,
            "project_name": r.metadata.project_name,
            "analysis_type": r.metadata.analysis_type,
            "created_at": r.metadata.created_at.isoformat(),
            "step_count": len(r.analysis_steps),
            "section_count": len(r.sections),
        }
        for r in _reports_db.values()
    ]


@router.get("/{report_id}")
async def get_report(report_id: str):
    """Get a report by ID."""
    report = _reports_db.get(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found")
    return report.to_dict()


@router.post("/{report_id}/section")
async def add_section(report_id: str, request: AddSectionRequest):
    """Add a section to a report."""
    report = _reports_db.get(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found")

    generator = _get_or_create_generator()
    try:
        section_type = SectionType(request.section_type)
    except ValueError:
        section_type = SectionType.CUSTOM

    figures = [ReportFigure(**f) for f in request.figures]
    tables = [ReportTable(**t) for t in request.tables]

    section = generator.add_section(
        report=report,
        title=request.title,
        content=request.content,
        section_type=section_type,
        figures=figures,
        tables=tables,
    )
    return {"message": "Section added", "section_title": section.title}


@router.post("/{report_id}/step")
async def add_step(report_id: str, request: AddStepRequest):
    """Add an analysis step to a report."""
    report = _reports_db.get(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found")

    generator = _get_or_create_generator()
    step = generator.add_analysis_step(
        report=report,
        name=request.name,
        description=request.description,
        skill_id=request.skill_id,
        status=request.status,
        duration_seconds=request.duration_seconds,
    )
    return {"message": "Step added", "step_number": step.step_number}


@router.post("/{report_id}/summary")
async def set_summary(report_id: str, summary: str):
    """Set the executive summary of a report."""
    report = _reports_db.get(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found")

    generator = _get_or_create_generator()
    generator.add_executive_summary(report, summary)
    return {"message": "Summary updated"}


@router.post("/{report_id}/plot")
async def add_plot_to_report(report_id: str, request: GeneratePlotForReportRequest):
    """Generate a plot and add it as a figure to the report."""
    report = _reports_db.get(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found")

    from homomics_lab.viz.generator import PlotType

    try:
        plot_type = PlotType(request.plot_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid plot type: {request.plot_type}")

    generator = _get_or_create_generator()
    figure = generator.create_figure_from_plot(
        plot_type=plot_type,
        data=request.data,
        caption=request.caption,
        title=request.title,
        width=request.width,
        height=request.height,
        dpi=request.dpi,
    )

    # Add to last results section, or create one
    results_section = None
    for section in reversed(report.sections):
        if section.type == SectionType.RESULTS:
            results_section = section
            break

    if results_section is None:
        results_section = generator.add_section(
            report=report,
            title="Results",
            section_type=SectionType.RESULTS,
        )

    results_section.figures.append(figure)

    return {
        "message": "Plot added to report",
        "figure_caption": figure.caption,
        "figure_type": figure.figure_type,
    }


@router.get("/{report_id}/html")
async def export_html(report_id: str):
    """Export report as HTML."""
    report = _reports_db.get(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found")

    generator = _get_or_create_generator()
    html = generator.generate_html(report)
    return {"html": html, "report_id": report_id, "title": report.title}


@router.get("/{report_id}/markdown")
async def export_markdown(report_id: str):
    """Export report as Markdown."""
    report = _reports_db.get(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found")

    generator = _get_or_create_generator()
    md = generator.generate_markdown(report)
    return {"markdown": md, "report_id": report_id, "title": report.title}


@router.get("/{report_id}/pdf")
async def export_pdf(report_id: str):
    """Export report as PDF."""
    report = _reports_db.get(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found")

    generator = _get_or_create_generator()
    try:
        pdf_bytes = generator.generate_pdf(report)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{report.title.replace(" ", "_")}.pdf"'
            },
        )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/build-from-pipeline")
async def build_from_pipeline(pipeline_data: Dict[str, Any]):
    """Build a complete report from pipeline execution data."""
    generator = _get_or_create_generator()
    report = generator.build_from_pipeline(
        title=pipeline_data.get("title", "Analysis Report"),
        steps=pipeline_data.get("steps", []),
        project_name=pipeline_data.get("project_name", ""),
        analysis_type=pipeline_data.get("analysis_type", ""),
        parameters=pipeline_data.get("parameters"),
    )
    _reports_db[report.id] = report
    return {"report_id": report.id, "title": report.title}
