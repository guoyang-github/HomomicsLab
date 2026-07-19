"""Tests for OpenTelemetry tracing setup."""


class TestTracingSetup:
    def test_disabled_by_default(self):
        from homomics_lab import tracing

        assert tracing.OTEL_ENABLED is False

    def test_setup_tracing_returns_none_when_disabled(self, monkeypatch):
        import homomics_lab.tracing as tracing

        monkeypatch.setattr(tracing, "OTEL_ENABLED", False)
        assert tracing.setup_tracing() is None

    def test_setup_tracing_console_when_enabled(self, monkeypatch):
        pytest = __import__("pytest")
        try:
            # Mirror the import chain in homomics_lab.tracing.setup_tracing;
            # it returns None gracefully when any of these are missing.
            __import__("opentelemetry")
            from opentelemetry.sdk.resources import Resource, SERVICE_NAME  # noqa: F401
            from opentelemetry.sdk.trace import TracerProvider  # noqa: F401
            from opentelemetry.sdk.trace.export import (  # noqa: F401
                BatchSpanProcessor,
                ConsoleSpanExporter,
            )
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (  # noqa: F401
                OTLPSpanExporter,
            )
        except ImportError:
            pytest.skip("opentelemetry packages not installed")

        import homomics_lab.tracing as tracing

        monkeypatch.setattr(tracing, "OTEL_ENABLED", True)
        monkeypatch.setattr(tracing, "OTEL_EXPORTER", "console")
        provider = tracing.setup_tracing()
        assert provider is not None

    def test_set_attribute_when_disabled_does_not_crash(self, monkeypatch):
        import homomics_lab.tracing as tracing

        monkeypatch.setattr(tracing, "OTEL_ENABLED", False)
        tracing.set_attribute("key", "value")  # should be a no-op
