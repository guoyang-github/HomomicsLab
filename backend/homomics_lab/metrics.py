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
    LLM_REQUEST_DURATION = Histogram(
        "homomicslab_llm_request_duration_seconds",
        "LLM request duration",
        ["model", "provider"],
        buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
    )
    LLM_REQUEST_ERRORS_TOTAL = Counter(
        "homomicslab_llm_request_errors_total",
        "Total LLM request errors",
        ["model", "provider", "error_type"],
    )
    LLM_FALLBACK_TOTAL = Counter(
        "homomicslab_llm_fallback_total",
        "Total LLM fallback events",
        ["reason", "from_model", "to_model"],
    )
    LLM_CACHE_HITS_TOTAL = Counter(
        "homomicslab_llm_cache_hits_total",
        "Total LLM cache hits",
        ["model"],
    )

    # Intent metrics
    INTENT_DECISIONS_TOTAL = Counter(
        "homomicslab_intent_decisions_total",
        "Total intent classification decisions",
        ["intent", "confidence_bucket"],
    )
    INTENT_CLARIFICATION_TOTAL = Counter(
        "homomicslab_intent_clarification_total",
        "Total intent clarification requests",
        ["intent"],
    )
    INTENT_LOW_CONFIDENCE_TOTAL = Counter(
        "homomicslab_intent_low_confidence_total",
        "Total low-confidence intent decisions",
        ["intent"],
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

    # Context engine metrics
    CONTEXT_ENGINE_BUILDS_TOTAL = Counter(
        "homomicslab_context_engine_builds_total",
        "Total ContextEngine builds",
        ["model"],
    )
    CONTEXT_USAGE_TOKENS = Histogram(
        "homomicslab_context_usage_tokens",
        "Input tokens used in assembled context",
        ["model"],
        buckets=[500, 1000, 2000, 4000, 8000, 16000, 32000, 64000, 128000],
    )
    CONTEXT_COMPRESSION_RATE = Histogram(
        "homomicslab_context_compression_rate",
        "Ratio of kept parts to total candidate parts",
        buckets=[0.0, 0.25, 0.5, 0.75, 1.0],
    )
    CONTEXT_DROPPED_PARTS_TOTAL = Counter(
        "homomicslab_context_dropped_parts_total",
        "Total context parts dropped by the ContextEngine",
        ["source"],
    )
    CONTEXT_SOURCE_TOKENS = Gauge(
        "homomicslab_context_source_tokens",
        "Tokens contributed by each context source before compression",
        ["source", "model"],
    )
    CONTEXT_DROPPED_BY_DUPLICATE_TOTAL = Counter(
        "homomicslab_context_dropped_by_duplicate_total",
        "Total context parts dropped as duplicates",
        ["source"],
    )
else:
    APP_INFO = None
    HTTP_REQUESTS_TOTAL = None
    HTTP_REQUEST_DURATION = None
    HTTP_REQUESTS_IN_PROGRESS = None
    LLM_REQUESTS_TOTAL = None
    LLM_TOKENS_TOTAL = None
    LLM_COST_USD = None
    LLM_REQUEST_DURATION = None
    LLM_REQUEST_ERRORS_TOTAL = None
    LLM_FALLBACK_TOTAL = None
    LLM_CACHE_HITS_TOTAL = None
    INTENT_DECISIONS_TOTAL = None
    INTENT_CLARIFICATION_TOTAL = None
    INTENT_LOW_CONFIDENCE_TOTAL = None
    SKILL_EXECUTIONS_TOTAL = None
    ACTIVE_JOBS = None
    CONTEXT_ENGINE_BUILDS_TOTAL = None
    CONTEXT_USAGE_TOKENS = None
    CONTEXT_COMPRESSION_RATE = None
    CONTEXT_DROPPED_PARTS_TOTAL = None
    CONTEXT_SOURCE_TOKENS = None
    CONTEXT_DROPPED_BY_DUPLICATE_TOTAL = None


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
    except Exception:
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


def record_context_build(
    model: str,
    used_tokens: int,
    kept_parts: int,
    total_parts: int,
    dropped_by_source: Optional[dict] = None,
    source_tokens: Optional[dict] = None,
    dropped_by_duplicate: Optional[dict] = None,
) -> None:
    """Record ContextEngine build metrics."""
    if not _PROMETHEUS_AVAILABLE:
        return
    if CONTEXT_ENGINE_BUILDS_TOTAL is not None:
        CONTEXT_ENGINE_BUILDS_TOTAL.labels(model=model).inc()
    if CONTEXT_USAGE_TOKENS is not None:
        CONTEXT_USAGE_TOKENS.labels(model=model).observe(used_tokens)
    if total_parts > 0 and CONTEXT_COMPRESSION_RATE is not None:
        CONTEXT_COMPRESSION_RATE.observe(kept_parts / total_parts)
    if dropped_by_source and CONTEXT_DROPPED_PARTS_TOTAL is not None:
        for source, count in dropped_by_source.items():
            CONTEXT_DROPPED_PARTS_TOTAL.labels(source=source).inc(count)
    if source_tokens and CONTEXT_SOURCE_TOKENS is not None:
        for source, tokens in source_tokens.items():
            CONTEXT_SOURCE_TOKENS.labels(source=source, model=model).set(tokens)
    if dropped_by_duplicate and CONTEXT_DROPPED_BY_DUPLICATE_TOTAL is not None:
        for source, count in dropped_by_duplicate.items():
            CONTEXT_DROPPED_BY_DUPLICATE_TOTAL.labels(source=source).inc(count)


def record_llm_request_duration(model: str, provider: str, duration_seconds: float) -> None:
    """Record LLM request duration."""
    if not _PROMETHEUS_AVAILABLE or LLM_REQUEST_DURATION is None:
        return
    LLM_REQUEST_DURATION.labels(model=model, provider=provider).observe(duration_seconds)


def record_llm_error(model: str, provider: str, error_type: str) -> None:
    """Record an LLM request error."""
    if not _PROMETHEUS_AVAILABLE or LLM_REQUEST_ERRORS_TOTAL is None:
        return
    LLM_REQUEST_ERRORS_TOTAL.labels(model=model, provider=provider, error_type=error_type).inc()


def record_llm_fallback(reason: str, from_model: str, to_model: str) -> None:
    """Record an LLM fallback event."""
    if not _PROMETHEUS_AVAILABLE or LLM_FALLBACK_TOTAL is None:
        return
    LLM_FALLBACK_TOTAL.labels(reason=reason, from_model=from_model, to_model=to_model).inc()


def record_llm_cache_hit(model: str) -> None:
    """Record an LLM cache hit."""
    if not _PROMETHEUS_AVAILABLE or LLM_CACHE_HITS_TOTAL is None:
        return
    LLM_CACHE_HITS_TOTAL.labels(model=model).inc()


def _confidence_bucket(confidence: float) -> str:
    if confidence >= 0.9:
        return "high"
    if confidence >= 0.7:
        return "medium"
    if confidence >= 0.5:
        return "low"
    return "very_low"


def record_intent_decision(intent: str, confidence: float) -> None:
    """Record an intent classification decision."""
    if not _PROMETHEUS_AVAILABLE or INTENT_DECISIONS_TOTAL is None:
        return
    INTENT_DECISIONS_TOTAL.labels(intent=intent, confidence_bucket=_confidence_bucket(confidence)).inc()


def record_intent_clarification(intent: str) -> None:
    """Record a clarification request triggered by low confidence."""
    if not _PROMETHEUS_AVAILABLE or INTENT_CLARIFICATION_TOTAL is None:
        return
    INTENT_CLARIFICATION_TOTAL.labels(intent=intent).inc()


def record_intent_low_confidence(intent: str) -> None:
    """Record a low-confidence but accepted intent decision."""
    if not _PROMETHEUS_AVAILABLE or INTENT_LOW_CONFIDENCE_TOTAL is None:
        return
    INTENT_LOW_CONFIDENCE_TOTAL.labels(intent=intent).inc()
