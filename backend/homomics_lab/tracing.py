"""OpenTelemetry tracing setup for HomomicsLab.

Provides optional distributed tracing. When ``HOMOMICS_OTEL_ENABLED=true``,
the FastAPI app is instrumented and spans are exported via OTLP (default) or
printed to console for local development.
"""

from __future__ import annotations

import logging
from typing import Optional

from homomics_lab.config import settings

logger = logging.getLogger(__name__)


def setup_tracing(service_name: str = "homomicslab") -> Optional[object]:
    """Initialize OpenTelemetry tracing if enabled in settings.

    Returns the tracer provider or None if tracing is disabled.
    """
    if not getattr(settings, "otel_enabled", False):
        return None

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource, SERVICE_NAME
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    except ImportError as e:
        logger.warning("OpenTelemetry packages not installed; tracing disabled: %s", e)
        return None

    resource = Resource({SERVICE_NAME: service_name})
    provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(provider)

    exporter_type = getattr(settings, "otel_exporter", "console").lower()
    if exporter_type == "otlp":
        endpoint = getattr(settings, "otel_otlp_endpoint", "http://localhost:4317")
        exporter = OTLPSpanExporter(endpoint=endpoint)
    else:
        exporter = ConsoleSpanExporter()

    provider.add_span_processor(BatchSpanProcessor(exporter))
    logger.info("OpenTelemetry tracing enabled (%s exporter)", exporter_type)
    return provider


def instrument_fastapi(app) -> None:
    """Instrument a FastAPI app with OpenTelemetry if enabled."""
    if not getattr(settings, "otel_enabled", False):
        return

    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
        logger.info("FastAPI OpenTelemetry instrumentation enabled")
    except ImportError as e:
        logger.warning("Failed to instrument FastAPI: %s", e)


def get_current_span():
    """Return the current OpenTelemetry span, or a no-op span."""
    try:
        from opentelemetry import trace
        return trace.get_current_span()
    except Exception:
        return None


def set_attribute(key: str, value) -> None:
    """Set an attribute on the current span if tracing is active."""
    span = get_current_span()
    if span is not None:
        try:
            span.set_attribute(key, value)
        except Exception:
            pass
