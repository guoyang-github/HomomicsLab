"""Tests for context engine Prometheus metrics."""

import pytest
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

from homomics_lab import metrics as metrics_module


@pytest.fixture
def isolated_metrics(monkeypatch):
    """Provide fresh Prometheus metrics isolated from the global registry."""
    registry = CollectorRegistry()

    monkeypatch.setattr(metrics_module, "_PROMETHEUS_AVAILABLE", True)
    monkeypatch.setattr(
        metrics_module,
        "CONTEXT_ENGINE_BUILDS_TOTAL",
        Counter(
            "homomicslab_context_engine_builds_total",
            "Total ContextEngine builds",
            ["model"],
            registry=registry,
        ),
    )
    monkeypatch.setattr(
        metrics_module,
        "CONTEXT_USAGE_TOKENS",
        Histogram(
            "homomicslab_context_usage_tokens",
            "Input tokens used in assembled context",
            ["model"],
            buckets=[500, 1000],
            registry=registry,
        ),
    )
    monkeypatch.setattr(
        metrics_module,
        "CONTEXT_COMPRESSION_RATE",
        Histogram(
            "homomicslab_context_compression_rate",
            "Ratio of kept parts to total candidate parts",
            buckets=[0.0, 1.0],
            registry=registry,
        ),
    )
    monkeypatch.setattr(
        metrics_module,
        "CONTEXT_DROPPED_PARTS_TOTAL",
        Counter(
            "homomicslab_context_dropped_parts_total",
            "Total context parts dropped by the ContextEngine",
            ["source"],
            registry=registry,
        ),
    )
    monkeypatch.setattr(
        metrics_module,
        "CONTEXT_SOURCE_TOKENS",
        Gauge(
            "homomicslab_context_source_tokens",
            "Tokens contributed by each context source before compression",
            ["source", "model"],
            registry=registry,
        ),
    )
    monkeypatch.setattr(
        metrics_module,
        "CONTEXT_DROPPED_BY_DUPLICATE_TOTAL",
        Counter(
            "homomicslab_context_dropped_by_duplicate_total",
            "Total context parts dropped as duplicates",
            ["source"],
            registry=registry,
        ),
    )
    return registry


def _samples_by_name(registry, name):
    for metric in registry.collect():
        if metric.name == name:
            return metric.samples
    return []


def test_record_context_build_source_tokens_and_duplicates(isolated_metrics):
    metrics_module = isolated_metrics  # registry returned by fixture
    import homomics_lab.metrics as m

    m.record_context_build(
        model="test-model",
        used_tokens=120,
        kept_parts=3,
        total_parts=5,
        dropped_by_source={"chat": 1},
        source_tokens={"chat": 80, "system": 40},
        dropped_by_duplicate={"chat": 2},
    )

    source_samples = _samples_by_name(metrics_module, "homomicslab_context_source_tokens")
    chat_source = [s for s in source_samples if s.labels == {"source": "chat", "model": "test-model"}]
    system_source = [s for s in source_samples if s.labels == {"source": "system", "model": "test-model"}]
    assert len(chat_source) == 1
    assert chat_source[0].value == 80
    assert len(system_source) == 1
    assert system_source[0].value == 40

    dup_samples = _samples_by_name(metrics_module, "homomicslab_context_dropped_by_duplicate")
    chat_dup = [
        s for s in dup_samples
        if s.name == "homomicslab_context_dropped_by_duplicate_total" and s.labels == {"source": "chat"}
    ]
    assert len(chat_dup) == 1
    assert chat_dup[0].value == 2
