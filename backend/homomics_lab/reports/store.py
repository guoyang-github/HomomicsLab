"""Persistent store for analysis reports."""

import json
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import desc, select

from homomics_lab.database.connection import AsyncSessionLocal
from homomics_lab.database.models import ReportRecord

from .models import (
    AnalysisReport,
    AnalysisStep,
    ReportFigure,
    ReportMetadata,
    ReportSection,
    ReportTable,
    SectionType,
)


class ReportStore:
    """Persist and retrieve :class:`AnalysisReport` models from the database."""

    def __init__(self, session_factory=AsyncSessionLocal):
        self._session_factory = session_factory

    async def create(self, report: AnalysisReport) -> AnalysisReport:
        """Persist a new report."""
        async with self._session_factory() as session:
            session.add(self._to_record(report))
            await session.commit()
        return report

    async def get(self, report_id: str) -> Optional[AnalysisReport]:
        """Retrieve a report by ID."""
        async with self._session_factory() as session:
            record = await session.get(ReportRecord, report_id)
            return self._to_model(record) if record else None

    async def update(self, report: AnalysisReport) -> AnalysisReport:
        """Update an existing report in place."""
        async with self._session_factory() as session:
            record = await session.get(ReportRecord, report.id)
            if record is None:
                raise ValueError(f"Report {report.id} not found")
            self._update_record(record, report)
            await session.commit()
        return report

    async def list_all(
        self,
        project_name: Optional[str] = None,
        analysis_type: Optional[str] = None,
        limit: int = 1000,
    ) -> List[AnalysisReport]:
        """List reports, optionally filtered."""
        async with self._session_factory() as session:
            stmt = select(ReportRecord)
            if project_name:
                stmt = stmt.where(ReportRecord.project_name == project_name)
            if analysis_type:
                stmt = stmt.where(ReportRecord.analysis_type == analysis_type)
            stmt = stmt.order_by(desc(ReportRecord.created_at)).limit(limit)
            result = await session.execute(stmt)
            return [self._to_model(r) for r in result.scalars().all()]

    async def delete(self, report_id: str) -> bool:
        """Delete a report by ID."""
        async with self._session_factory() as session:
            record = await session.get(ReportRecord, report_id)
            if record is None:
                return False
            await session.delete(record)
            await session.commit()
            return True

    @staticmethod
    def _to_record(report: AnalysisReport) -> ReportRecord:
        metadata = report.metadata
        return ReportRecord(
            report_id=report.id,
            title=report.title,
            project_name=metadata.project_name,
            analysis_type=metadata.analysis_type,
            author=metadata.author,
            tags_json=json.dumps(metadata.tags, default=str),
            parameters_json=json.dumps(metadata.parameters, default=str),
            summary=report.summary,
            sections_json=json.dumps(
                [s.model_dump(mode="json") for s in report.sections], default=str
            ),
            steps_json=json.dumps(
                [s.model_dump(mode="json") for s in report.analysis_steps], default=str
            ),
            created_at=metadata.created_at,
            updated_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def _update_record(record: ReportRecord, report: AnalysisReport) -> None:
        metadata = report.metadata
        record.title = report.title
        record.project_name = metadata.project_name
        record.analysis_type = metadata.analysis_type
        record.author = metadata.author
        record.tags_json = json.dumps(metadata.tags, default=str)
        record.parameters_json = json.dumps(metadata.parameters, default=str)
        record.summary = report.summary
        record.sections_json = json.dumps(
            [s.model_dump(mode="json") for s in report.sections], default=str
        )
        record.steps_json = json.dumps(
            [s.model_dump(mode="json") for s in report.analysis_steps], default=str
        )
        record.updated_at = datetime.now(timezone.utc)

    @staticmethod
    def _to_model(record: ReportRecord) -> AnalysisReport:
        metadata = ReportMetadata(
            project_name=record.project_name,
            analysis_type=record.analysis_type,
            author=record.author,
            created_at=record.created_at,
            tags=json.loads(record.tags_json) if record.tags_json else [],
            parameters=json.loads(record.parameters_json)
            if record.parameters_json
            else {},
        )
        sections = [
            ReportSection(
                title=s["title"],
                type=SectionType(s.get("type", "custom")),
                content=s.get("content", ""),
                figures=[ReportFigure(**f) for f in s.get("figures", [])],
                tables=[ReportTable(**t) for t in s.get("tables", [])],
                metadata=s.get("metadata", {}),
            )
            for s in json.loads(record.sections_json or "[]")
        ]
        steps = [
            AnalysisStep(**s) for s in json.loads(record.steps_json or "[]")
        ]
        return AnalysisReport(
            id=record.report_id,
            title=record.title,
            metadata=metadata,
            sections=sections,
            analysis_steps=steps,
            summary=record.summary or "",
        )
