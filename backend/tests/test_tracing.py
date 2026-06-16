"""Tests for OpenTelemetry tracing setup."""

import pytest

from homomics_lab.config import settings


class TestTracingSetup:
    def test_disabled_by_default(self):
        assert settings.otel_enabled is False

    def test_setup_tracing_returns_none_when_disabled(self, monkeypatch):
        monkeypatch.setattr(settings, "otel_enabled", False)
        from homomics_lab.tracing import setup_tracing

        assert setup_tracing() is None

    def test_setup_tracing_console_when_enabled(self, monkeypatch):
        monkeypatch.setattr(settings, "otel_enabled", True)
        monkeypatch.setattr(settings, "otel_exporter", "console")
        from homomics_lab.tracing import setup_tracing

        provider = setup_tracing()
        assert provider is not None

    def test_set_attribute_when_disabled_does_not_crash(self, monkeypatch):
        monkeypatch.setattr(settings, "otel_enabled", False)
        from homomics_lab.tracing import set_attribute

        set_attribute("key", "value")  # should be a no-op
