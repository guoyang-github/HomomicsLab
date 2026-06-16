"""Prometheus metrics for HomomicsLab.

Exposes a /metrics endpoint for scraping by Prometheus. Tracks:
  - HTTP request count/latency
  - LLM token usage and cost
  - Skill execution count
  - Active job gauge
"""

from __future__ import annotations

import time
from typing import Callable, Optional

from fastapi import Request, Response

try:
    from prometheus_client import (
        Counter,
        Gauge,
        Histogram,
        Info,
        generate_latest,
        CONTENT_TYPE_LATEST,
    )
    _PROMETHEUS_AVAILABLE = True
except ImportError:
    _PROMETHEUS_AVAILABLE = False

from homomics_lab import __version__


if _PROMETHEUS_AVAILABLE:
    # Application info
    APP_INFO = Info("homomicslab", "HomomicsLab application information")
    APP_INFO.info({"version": __version__})

    # HTTP metrics
    HTTP_REQUESTS_TOTAL = Counter(
        "homomicslab_http_requests_total",
        "Total HTTP requests",
        ["method", "endpoint", "status_code"],
    )
    HTTP_REQUEST_DURATION = Histogram(
        "homomicslab_http_request_duration_seconds",
        "HTTP request duration",
        ["method", "endpoint"],
        buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
    )
    HTTP_REQUESTS_IN_PROGRESS = Gauge(
        "homomicslab_http_requests_in_progress",
        "HTTP requests currently in progress",
        ["method", "endpoint"],
    )

    # LLM metrics
    LLM_REQUESTS_TOTAL = Counter(
        "homomicslab_llm_requests_total",
        "Total LLM requests",
        ["model"],
    )
    LLM_TOKENS_TOTAL = Counter(
        "homomicslab_llm_tokens_total",
        "Total LLM tokens consumed",
        ["model", "token_type"],
    )
    LLM_COST_USD = Counter(
        "homomicslab_llm_cost_usd_total",
        "Total estimated LLM cost in USD",
        ["model"],
    )

    # Skill/job metrics
    SKILL_EXECUTIONS_TOTAL = Counter(
        "homomicslab_skill_executions_total",
        "Total skill executions",
        ["skill_id", "executor_type", "status"],
    )
    ACTIVE_JOBS = Gauge(
        "homomicslab_active_jobs",
        "Number of jobs currently running or queued",
    )
else:
    APP_INFO = None
    HTTP_REQUESTS_TOTAL = None
    HTTP_REQUEST_DURATION = None
    HTTP_REQUESTS_IN_PROGRESS = None
    LLM_REQUESTS_TOTAL = None
    LLM_TOKENS_TOTAL = None
    LLM_COST_USD = None
    SKILL_EXECUTIONS_TOTAL = None
    ACTIVE_JOBS = None


def metrics_endpoint() -> Response:
    """Return Prometheus metrics in text format."""
    if not _PROMETHEUS_AVAILABLE:
        return Response(
            content="# Prometheus client not installed. Run: pip install prometheus-client\n",
            media_type="text/plain",
        )
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


def _normalize_path(path: str) -> str:
    """Normalize dynamic path segments for stable metric labels."""
    # Replace UUID-like and hex IDs with placeholders.
    import re
    path = re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "<uuid>", path)
    path = re.sub(r"[0-9a-f]{12,}", "<id>", path)
    path = re.sub(r"\d+", "<n>", path)
    return path


async def prometheus_middleware(request: Request, call_next: Callable) -> Response:
    """FastAPI middleware that records Prometheus metrics per request."""
    if not _PROMETHEUS_AVAILABLE:
        return await call_next(request)

    method = request.method
    path = _normalize_path(request.url.path)

    HTTP_REQUESTS_IN_PROGRESS.labels(method=method, endpoint=path).inc()
    start = time.time()
    try:
        response = await call_next(request)
    except Exception as exc:
        HTTP_REQUESTS_TOTAL.labels(method=method, endpoint=path, status_code="500").inc()
        raise
    finally:
        HTTP_REQUESTS_IN_PROGRESS.labels(method=method, endpoint=path).dec()

    duration = time.time() - start
    HTTP_REQUEST_DURATION.labels(method=method, endpoint=path).observe(duration)
    HTTP_REQUESTS_TOTAL.labels(
        method=method, endpoint=path, status_code=str(response.status_code)
    ).inc()
    return response


def record_llm_usage(model: str, prompt_tokens: int, completion_tokens: int, cost_usd: float) -> None:
    """Record LLM usage in Prometheus metrics."""
    if not _PROMETHEUS_AVAILABLE:
        return
    LLM_REQUESTS_TOTAL.labels(model=model).inc()
    LLM_TOKENS_TOTAL.labels(model=model, token_type="prompt").inc(prompt_tokens)
    LLM_TOKENS_TOTAL.labels(model=model, token_type="completion").inc(completion_tokens)
    LLM_COST_USD.labels(model=model).inc(cost_usd)


def record_skill_execution(skill_id: str, executor_type: str, success: bool) -> None:
    """Record a skill execution in Prometheus metrics."""
    if not _PROMETHEUS_AVAILABLE:
        return
    status = "success" if success else "failure"
    SKILL_EXECUTIONS_TOTAL.labels(skill_id=skill_id, executor_type=executor_type, status=status).inc()


def set_active_jobs(count: int) -> None:
    """Update the active jobs gauge."""
    if not _PROMETHEUS_AVAILABLE:
        return
    ACTIVE_JOBS.set(count)
