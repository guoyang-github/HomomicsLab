"""Standard FastAPI dependencies for accessing bootstrap-initialized services.

These helpers enforce fail-fast behaviour: if the requested service was not
mounted on ``app.state`` during bootstrap, the endpoint returns HTTP 503 instead
of silently instantiating an unconfigured service.
"""

from typing import Any

from fastapi import HTTPException, Request

from homomics_lab.jobs import JobService
from homomics_lab.jobs.waiting import WaitingService
from homomics_lab.observability.trace_store import TraceStore
from homomics_lab.plan import PlanStore
from homomics_lab.reports.store import ReportStore


def _get_app_state_attr(request: Request, name: str, label: str) -> Any:
    value = getattr(request.app.state, name, None)
    if value is None:
        raise HTTPException(
            status_code=503,
            detail=f"{label} is not initialized. The application may still be starting up.",
        )
    return value


def get_job_service(request: Request) -> JobService:
    return _get_app_state_attr(request, "job_service", "Job service")


def get_plan_store(request: Request) -> PlanStore:
    return _get_app_state_attr(request, "plan_store", "Plan store")


def get_trace_store(request: Request) -> TraceStore:
    return _get_app_state_attr(request, "trace_store", "Trace store")


def get_report_store(request: Request) -> ReportStore:
    return _get_app_state_attr(request, "report_store", "Report store")


def get_execution_pubsub(request: Request) -> Any:
    return _get_app_state_attr(request, "execution_pubsub", "Execution pubsub")


def get_waiting_service(request: Request) -> WaitingService:
    return _get_app_state_attr(request, "waiting_service", "Waiting service")
