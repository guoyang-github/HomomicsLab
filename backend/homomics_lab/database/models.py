"""SQLAlchemy ORM models for persistent entities."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Tenant(Base):
    """Multi-tenant workspace."""

    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    users: Mapped[list["User"]] = relationship("User", back_populates="tenant")


class User(Base):
    """Application user account."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    username: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String, nullable=True)
    role: Mapped[str] = mapped_column(String, default="analyst")  # admin / analyst / viewer
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="users")


class JobRecord(Base):
    """Persistent record of a background execution job."""

    __tablename__ = "jobs"

    job_id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(String, index=True)
    project_id: Mapped[str] = mapped_column(String, index=True)
    user_id: Mapped[str] = mapped_column(String, nullable=True, index=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=True, index=True)
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
    user_id: Mapped[str] = mapped_column(String, nullable=True, index=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String, index=True)
    is_fallback: Mapped[bool] = mapped_column(Boolean, default=False)
    intent_analysis_type: Mapped[str] = mapped_column(String)
    intent_complexity: Mapped[str] = mapped_column(String, nullable=True)
    original_intent_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
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
    user_id: Mapped[str] = mapped_column(String, nullable=True, index=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=True, index=True)
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

    nodes: Mapped[list["TraceNodeRecord"]] = relationship(
        "TraceNodeRecord",
        back_populates="trace",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="TraceNodeRecord.id",
    )


class TraceNodeRecord(Base):
    """Individual node within an execution trace.

    Storing nodes in separate rows allows TraceStore to update a single node
    without rewriting the entire trace JSON blob.
    """

    __tablename__ = "execution_trace_nodes"

    __table_args__ = (UniqueConstraint("trace_id", "node_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trace_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("execution_traces.trace_id"),
        nullable=False,
        index=True,
    )
    node_id: Mapped[str] = mapped_column(String, nullable=False)
    parent_id: Mapped[str] = mapped_column(String, nullable=True)
    node_type: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="running")
    started_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    ended_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    inputs_json: Mapped[str] = mapped_column(Text, default="null")
    outputs_json: Mapped[str] = mapped_column(Text, default="null")
    error: Mapped[str] = mapped_column(Text, nullable=True)
    logs_json: Mapped[str] = mapped_column(Text, default="[]")
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")

    trace: Mapped["TraceRecord"] = relationship("TraceRecord", back_populates="nodes")


class ReportRecord(Base):
    """Persistent analysis report."""

    __tablename__ = "analysis_reports"

    report_id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    project_name: Mapped[str] = mapped_column(
        String, nullable=False, default="", index=True
    )
    analysis_type: Mapped[str] = mapped_column(
        String, nullable=False, default="", index=True
    )
    author: Mapped[str] = mapped_column(String, nullable=False, default="HomomicsLab Agent")
    tags_json: Mapped[str] = mapped_column(Text, default="[]")
    parameters_json: Mapped[str] = mapped_column(Text, default="{}")
    summary: Mapped[str] = mapped_column(Text, default="")
    sections_json: Mapped[str] = mapped_column(Text, default="[]")
    steps_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
