"""Async repository for background jobs using SQLAlchemy."""

import json
from typing import List, Optional

from sqlalchemy import desc, select

from homomics_lab.context.working_memory import WorkingMemory
from homomics_lab.database.connection import get_session_factory
from homomics_lab.database.models import JobRecord
from homomics_lab.tasks.models import TaskNode
from homomics_lab.tasks.task_tree import TaskTree

from .models import Job, JobMode, JobStatus


class JobRepository:
    """Persist and retrieve background jobs from SQLite."""

    def __init__(self, session_factory=None):
        session_factory = session_factory or get_session_factory()
        self._session_factory = session_factory

    async def create(self, job: Job) -> Job:
        async with self._session_factory() as session:
            record = self._to_record(job)
            session.add(record)
            await session.commit()
            return job

    async def get(self, job_id: str) -> Optional[Job]:
        async with self._session_factory() as session:
            record = await session.get(JobRecord, job_id)
            return self._to_model(record) if record else None

    async def update(self, job: Job) -> Job:
        async with self._session_factory() as session:
            record = await session.get(JobRecord, job.job_id)
            if record is None:
                raise ValueError(f"Job {job.job_id} not found")
            self._update_record(record, job)
            await session.commit()
            return job

    async def get_latest_by_session(
        self,
        session_id: str,
        statuses: Optional[List[str]] = None,
    ) -> Optional[Job]:
        async with self._session_factory() as session:
            stmt = select(JobRecord).where(JobRecord.session_id == session_id)
            if statuses:
                stmt = stmt.where(JobRecord.status.in_(statuses))
            stmt = stmt.order_by(desc(JobRecord.created_at))
            result = await session.execute(stmt)
            record = result.scalars().first()
            return self._to_model(record) if record else None

    async def list_by_session(self, session_id: str) -> List[Job]:
        async with self._session_factory() as session:
            stmt = (
                select(JobRecord)
                .where(JobRecord.session_id == session_id)
                .order_by(desc(JobRecord.created_at))
            )
            result = await session.execute(stmt)
            return [self._to_model(r) for r in result.scalars().all()]

    async def list_by_status(self, status: str) -> List[Job]:
        async with self._session_factory() as session:
            stmt = (
                select(JobRecord)
                .where(JobRecord.status == status)
                .order_by(desc(JobRecord.created_at))
            )
            result = await session.execute(stmt)
            return [self._to_model(r) for r in result.scalars().all()]

    async def list_all(self, project_id: Optional[str] = None) -> List[Job]:
        async with self._session_factory() as session:
            stmt = select(JobRecord)
            if project_id:
                stmt = stmt.where(JobRecord.project_id == project_id)
            stmt = stmt.order_by(desc(JobRecord.created_at))
            result = await session.execute(stmt)
            return [self._to_model(r) for r in result.scalars().all()]

    # ------------------------------------------------------------------
    # Serialization helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_record(job: Job) -> JobRecord:
        return JobRecord(
            job_id=job.job_id,
            session_id=job.session_id,
            project_id=job.project_id,
            status=job.status.value,
            mode=job.mode.value,
            task_tree_json=_serialize_task_tree(job.task_tree),
            working_memory_json=job.working_memory.to_json() if job.working_memory else None,
            result_json=json.dumps(job.result) if job.result is not None else None,
            error_message=job.error_message,
            resume_task_id=job.resume_task_id,
            resume_choice=job.resume_choice,
            resume_parameters_json=json.dumps(job.resume_parameters) if job.resume_parameters is not None else None,
            plan_id=job.plan_id,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )

    @staticmethod
    def _update_record(record: JobRecord, job: Job) -> None:
        record.status = job.status.value
        record.mode = job.mode.value
        record.task_tree_json = _serialize_task_tree(job.task_tree)
        record.working_memory_json = (
            job.working_memory.to_json() if job.working_memory else None
        )
        record.result_json = json.dumps(job.result) if job.result is not None else None
        record.error_message = job.error_message
        record.resume_task_id = job.resume_task_id
        record.resume_choice = job.resume_choice
        record.resume_parameters_json = (
            json.dumps(job.resume_parameters) if job.resume_parameters is not None else None
        )
        record.plan_id = job.plan_id
        record.updated_at = job.updated_at

    @staticmethod
    def _to_model(record: JobRecord) -> Job:
        resume_parameters = None
        if record.resume_parameters_json:
            resume_parameters = json.loads(record.resume_parameters_json)
        return Job(
            job_id=record.job_id,
            session_id=record.session_id,
            project_id=record.project_id,
            status=JobStatus(record.status),
            mode=JobMode(record.mode),
            task_tree=_deserialize_task_tree(record.task_tree_json),
            working_memory=_deserialize_working_memory(record.working_memory_json),
            result=json.loads(record.result_json) if record.result_json else None,
            error_message=record.error_message,
            resume_task_id=record.resume_task_id,
            resume_choice=record.resume_choice,
            resume_parameters=resume_parameters,
            plan_id=record.plan_id,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )


def _serialize_task_tree(tree: Optional[TaskTree]) -> Optional[str]:
    if tree is None:
        return None
    return json.dumps([t.model_dump(mode="json") for t in tree.tasks])


def _deserialize_task_tree(raw: Optional[str]) -> Optional[TaskTree]:
    if raw is None:
        return None
    tasks = [TaskNode.model_validate(d) for d in json.loads(raw)]
    return TaskTree(tasks)


def _deserialize_working_memory(raw: Optional[str]) -> Optional[WorkingMemory]:
    if raw is None:
        return None
    return WorkingMemory.from_json(raw)
