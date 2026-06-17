"""Fixtures for the agent test package."""

import pytest


@pytest.fixture(autouse=True)
def _disable_nfcore_network(monkeypatch):
    """Prevent nf-core pipeline downloads from blocking/hanging in tests."""

    def _no_suggest(self, analysis_type: str):
        return None

    monkeypatch.setattr(
        "homomics_lab.nfcore_integration.NFCoreManager.suggest_pipeline",
        _no_suggest,
    )
