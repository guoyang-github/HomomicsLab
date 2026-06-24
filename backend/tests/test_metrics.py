"""Tests for Prometheus metric helpers."""

import pytest
from prometheus_client import CollectorRegistry, Counter, Gauge

from homomics_lab import metrics as metrics_module


@pytest.fixture
def isolated_metrics(monkeypatch):
    """Provide fresh Prometheus metrics isolated from the global registry."""
    registry = CollectorRegistry()
    monkeypatch.setattr(metrics_module, "_PROMETHEUS_AVAILABLE", True)
    monkeypatch.setattr(
        metrics_module,
        "SKILL_EXECUTIONS_TOTAL",
        Counter(
            "homomicslab_skill_executions_total",
            "Total skill executions",
            ["skill_id", "executor_type", "status"],
            registry=registry,
        ),
    )
    monkeypatch.setattr(
        metrics_module,
        "ACTIVE_JOBS",
        Gauge(
            "homomicslab_active_jobs",
            "Number of jobs currently running or queued",
            registry=registry,
        ),
    )
    return registry


def _samples_by_name(registry, name):
    for metric in registry.collect():
        if metric.name == name:
            return metric.samples
    return []


def test_record_skill_execution_success(isolated_metrics):
    metrics_module.record_skill_execution("skill_1", "local", True)
    samples = _samples_by_name(isolated_metrics, "homomicslab_skill_executions")
    match = [
        s
        for s in samples
        if s.name == "homomicslab_skill_executions_total"
        and s.labels == {"skill_id": "skill_1", "executor_type": "local", "status": "success"}
    ]
    assert len(match) == 1
    assert match[0].value == 1


def test_record_skill_execution_failure(isolated_metrics):
    metrics_module.record_skill_execution("skill_1", "local", False)
    samples = _samples_by_name(isolated_metrics, "homomicslab_skill_executions")
    match = [
        s
        for s in samples
        if s.name == "homomicslab_skill_executions_total"
        and s.labels == {"skill_id": "skill_1", "executor_type": "local", "status": "failure"}
    ]
    assert len(match) == 1
    assert match[0].value == 1


def test_set_active_jobs(isolated_metrics):
    metrics_module.set_active_jobs(5)
    samples = _samples_by_name(isolated_metrics, "homomicslab_active_jobs")
    assert len(samples) == 1
    assert samples[0].value == 5


def test_metrics_endpoint_when_prometheus_unavailable(monkeypatch):
    monkeypatch.setattr(metrics_module, "_PROMETHEUS_AVAILABLE", False)
    response = metrics_module.metrics_endpoint()
    assert response.status_code == 200
    assert "Prometheus client not installed" in response.body.decode()
