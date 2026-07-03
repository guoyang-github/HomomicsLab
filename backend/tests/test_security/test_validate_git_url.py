"""Tests for git URL whitelist validation."""

import pytest

from homomics_lab.config import Settings
from homomics_lab.security import PathSecurityError, validate_git_url


def test_allows_any_url_when_whitelist_empty(monkeypatch):
    monkeypatch.setattr(
        "homomics_lab.security.settings",
        Settings(allowed_skill_git_urls=[]),
    )
    # Should not raise.
    validate_git_url("https://example.com/repo.git")


def test_allows_matching_prefix(monkeypatch):
    monkeypatch.setattr(
        "homomics_lab.security.settings",
        Settings(allowed_skill_git_urls=["https://github.com/myorg/"]),
    )
    validate_git_url("https://github.com/myorg/bio-skills.git")


def test_rejects_non_matching_url(monkeypatch):
    monkeypatch.setattr(
        "homomics_lab.security.settings",
        Settings(allowed_skill_git_urls=["https://github.com/myorg/"]),
    )
    with pytest.raises(PathSecurityError):
        validate_git_url("https://evil.com/repo.git")


def test_supports_comma_separated_config(monkeypatch):
    monkeypatch.setattr(
        "homomics_lab.security.settings",
        Settings(
            allowed_skill_git_urls="https://github.com/myorg/, https://gitlab.com/myorg/"
        ),
    )
    validate_git_url("https://gitlab.com/myorg/bio-skills.git")
    with pytest.raises(PathSecurityError):
        validate_git_url("https://bitbucket.org/other/repo.git")
