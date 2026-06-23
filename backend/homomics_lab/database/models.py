"""SQLAlchemy ORM models for persistent entities."""

from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class JobRecord(Base):
    """Persistent record of a background execution job."""

    __tablename__ = "jobs"

    job_id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(String, index=True)
    project_id: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String, index=True)
    mode: Mapped[str] = mapped_column(String)
    task_tree_json: Mapped[str] = mapped_column(Text, nullable=True)
    working_memory_json: Mapped[str] = mapped_column(Text, nullable=True)
    result_json: Mapped[str] = mapped_column(Text, nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    resume_task_id: Mapped[str] = mapped_column(String, nullable=True)
    resume_choice: Mapped[str] = mapped_column(String, nullable=True)
    resume_parameters_json: Mapped[str] = mapped_column(Text, nullable=True)
    plan_id: Mapped[str] = mapped_column(String, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class PlanRecord(Base):
    """Persistent record of an execution plan."""

    __tablename__ = "plans"

    plan_id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(String, index=True)
    project_id: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String, index=True)
    is_fallback: Mapped[bool] = mapped_column(Boolean, default=False)
    intent_analysis_type: Mapped[str] = mapped_column(String)
    intent_complexity: Mapped[str] = mapped_column(String, nullable=True)
    plan_result_json: Mapped[str] = mapped_column(Text)
    task_tree_json: Mapped[str] = mapped_column(Text)
    working_memory_json: Mapped[str] = mapped_column(Text, nullable=True)
    approved_by: Mapped[str] = mapped_column(String, nullable=True)
    approved_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    parent_plan_id: Mapped[str] = mapped_column(String, nullable=True, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class PlanTemplateRecord(Base):
    """Persisted reusable plan template."""

    __tablename__ = "plan_templates"

    template_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, index=True)
    plan_result_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class ScheduledJobRun(Base):
    """Audit record of a scheduled task execution."""

    __tablename__ = "scheduled_job_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_name: Mapped[str] = mapped_column(String, index=True)
    trigger_time: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    start_time: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    end_time: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String, index=True)
    result_json: Mapped[str] = mapped_column(Text, nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)


class ProjectRecord(Base):
    """Persistent project metadata."""

    __tablename__ = "projects"

    project_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    owner_id: Mapped[str] = mapped_column(String, index=True, default="anonymous")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class ProjectMember(Base):
    """Many-to-many membership between users and projects with RBAC role."""

    __tablename__ = "project_members"

    project_id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, primary_key=True)
    role: Mapped[str] = mapped_column(String, default="member")  # owner / admin / member / viewer
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


class TraceRecord(Base):
    """Persistent execution trace for a job or plan."""

    __tablename__ = "execution_traces"

    trace_id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(String, nullable=True, index=True)
    project_id: Mapped[str] = mapped_column(String, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String, index=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    ended_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    nodes_json: Mapped[str] = mapped_column(Text, default="[]")
