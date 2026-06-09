"""Data models for analysis reports."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SectionType(str, Enum):
    """Types of report sections."""

    EXECUTIVE_SUMMARY = "executive_summary"
    METHODOLOGY = "methodology"
    RESULTS = "results"
    DISCUSSION = "discussion"
    CONCLUSION = "conclusion"
    REFERENCES = "references"
    APPENDIX = "appendix"
    CUSTOM = "custom"


class ReportFigure(BaseModel):
    """A figure embedded in a report."""

    image_base64: str = Field(description="Base64-encoded PNG image")
    caption: str = ""
    figure_type: str = "plot"  # plot, diagram, workflow
    width: int = 600
    height: int = 400


class ReportTable(BaseModel):
    """A data table embedded in a report."""

    headers: List[str]
    rows: List[List[Any]]
    caption: str = ""


class ReportSection(BaseModel):
    """A section within an analysis report."""

    title: str
    type: SectionType = SectionType.CUSTOM
    content: str = ""  # Markdown or HTML content
    figures: List[ReportFigure] = Field(default_factory=list)
    tables: List[ReportTable] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ReportMetadata(BaseModel):
    """Metadata for an analysis report."""

    project_name: str = ""
    analysis_type: str = ""  # e.g., "single_cell_rna", "spatial_transcriptomics"
    author: str = "HomomicsLab Agent"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: str = "1.0"
    tags: List[str] = Field(default_factory=list)
    parameters: Dict[str, Any] = Field(default_factory=dict)


class AnalysisStep(BaseModel):
    """A single step in the analysis pipeline."""

    step_number: int
    name: str
    description: str = ""
    skill_id: str = ""
    status: str = ""  # pending, running, completed, failed
    duration_seconds: Optional[float] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    inputs: Dict[str, Any] = Field(default_factory=dict)
    outputs: Dict[str, Any] = Field(default_factory=dict)
    notes: str = ""


class AnalysisReport(BaseModel):
    """A complete bioinformatics analysis report."""

    id: str
    title: str
    metadata: ReportMetadata = Field(default_factory=ReportMetadata)
    sections: List[ReportSection] = Field(default_factory=list)
    analysis_steps: List[AnalysisStep] = Field(default_factory=list)
    summary: str = ""  # Auto-generated executive summary

    def add_section(self, section: ReportSection) -> None:
        """Add a section to the report."""
        self.sections.append(section)

    def get_section(self, section_type: SectionType) -> Optional[ReportSection]:
        """Get first section of given type."""
        for section in self.sections:
            if section.type == section_type:
                return section
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary."""
        return self.model_dump()
