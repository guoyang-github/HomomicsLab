"""OpenTelemetry tracing setup for HomomicsLab.

Provides optional distributed tracing. Tracing is off by default (the former
``HOMOMICS_OTEL_*`` config fields are now the module constants below); when
enabled, the FastAPI app is instrumented and spans are exported via OTLP or
printed to console for local development.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Former HOMOMICS_OTEL_* config fields; defaults kept (tracing off).
OTEL_ENABLED = False
OTEL_EXPORTER = "console"  # console | otlp
OTEL_OTLP_ENDPOINT = "http://localhost:4317"
OTEL_SERVICE_NAME = "homomicslab"


def setup_tracing(service_name: str = OTEL_SERVICE_NAME) -> Optional[object]:
    """Initialize OpenTelemetry tracing if enabled.

    Returns the tracer provider or None if tracing is disabled.
    """
    if not OTEL_ENABLED:
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

    exporter_type = OTEL_EXPORTER.lower()
    if exporter_type == "otlp":
        exporter = OTLPSpanExporter(endpoint=OTEL_OTLP_ENDPOINT)
    else:
        exporter = ConsoleSpanExporter()

    provider.add_span_processor(BatchSpanProcessor(exporter))
    logger.info("OpenTelemetry tracing enabled (%s exporter)", exporter_type)
    return provider


def instrument_fastapi(app) -> None:
    """Instrument a FastAPI app with OpenTelemetry if enabled."""
    if not OTEL_ENABLED:
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


def get_tracer(name: str = "homomicslab") -> Optional[object]:
    """Return a tracer if OpenTelemetry is enabled and available, else None."""
    if not OTEL_ENABLED:
        return None
    try:
        from opentelemetry import trace
        return trace.get_tracer(name)
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
