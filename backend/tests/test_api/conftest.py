"""Shared test fixtures for API-level tests.

Bootstrapping the full application imports and copies external skills, which is
slow and unnecessary for API tests. Disable that machinery here so tests start
quickly and deterministically.
"""

import pytest

from homomics_lab.config import settings


@pytest.fixture(autouse=True)
def _disable_external_skill_import(monkeypatch):
    """Prevent bootstrap from importing external skills during API tests."""
    monkeypatch.setattr(settings, "external_skills_dirs", [])
    monkeypatch.setattr(settings, "skill_sibling_discovery_enabled", False)
    monkeypatch.setattr(settings, "skill_hot_reload_enabled", False)
