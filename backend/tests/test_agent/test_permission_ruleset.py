"""Tests for per-agent / per-domain permission rulesets."""

import json

import pytest

from homomics_lab.agent.permission_ruleset import (
    PermissionRegistry,
    PermissionRuleSet,
)


@pytest.fixture
def registry(tmp_path, monkeypatch):
    monkeypatch.setattr("homomics_lab.config.settings.data_dir", tmp_path)
    return PermissionRegistry()


def test_can_auto_approve_tool_exact_match(registry):
    registry._rules = [
        PermissionRuleSet(
            domain="single-cell-transcriptomics",
            auto_approved_tools=["file_read"],
        )
    ]
    assert registry.can_auto_approve_tool(None, "single-cell-transcriptomics", "file_read")
    assert not registry.can_auto_approve_tool(None, "single-cell-transcriptomics", "file_write")


def test_can_auto_approve_tool_wildcard(registry):
    registry._rules = [
        PermissionRuleSet(
            role_id="analyst",
            auto_approved_tools=["file_*"],
        )
    ]
    assert registry.can_auto_approve_tool("analyst", None, "file_read")
    assert registry.can_auto_approve_tool("analyst", None, "file_list")


def test_denied_tool_overrides_auto_approve(registry):
    registry._rules = [
        PermissionRuleSet(
            domain="single-cell-transcriptomics",
            auto_approved_tools=["file_*"],
            denied_tools=["file_delete"],
        )
    ]
    assert registry.can_auto_approve_tool(None, "single-cell-transcriptomics", "file_read")
    assert not registry.can_auto_approve_tool(None, "single-cell-transcriptomics", "file_delete")


def test_can_auto_approve_skill_with_risk_level(registry):
    registry._rules = [
        PermissionRuleSet(
            domain="single-cell-transcriptomics",
            auto_approved_skills=["bio-single-cell-preprocessing"],
            max_auto_approve_risk_level="medium",
        )
    ]
    assert registry.can_auto_approve_skill(
        None, "single-cell-transcriptomics", "bio-single-cell-preprocessing", "low"
    )
    assert registry.can_auto_approve_skill(
        None, "single-cell-transcriptomics", "bio-single-cell-preprocessing", "medium"
    )
    assert not registry.can_auto_approve_skill(
        None, "single-cell-transcriptomics", "bio-single-cell-preprocessing", "high"
    )


def test_load_from_disk(tmp_path, monkeypatch):
    monkeypatch.setattr("homomics_lab.config.settings.data_dir", tmp_path)
    data = [
        {
            "domain": "metagenomics",
            "auto_approved_skills": ["bio-metagenomics-qc"],
            "denied_skills": ["bio-metagenomics-untrusted"],
        }
    ]
    (tmp_path / "permission_rulesets.json").write_text(json.dumps(data))
    registry = PermissionRegistry()
    assert registry.can_auto_approve_skill(None, "metagenomics", "bio-metagenomics-qc")
    assert registry.is_denied_skill(None, "metagenomics", "bio-metagenomics-untrusted")


def test_load_from_domain_role(monkeypatch):
    class FakeDomain:
        domain = "single-cell-transcriptomics"
        roles = []

    class FakeRole:
        role_id = "single_cell_specialist"
        permissions = {
            "auto_approved_skills": ["bio-single-cell-*"],
            "max_auto_approve_risk_level": "medium",
        }

    FakeDomain.roles = [FakeRole()]

    class FakeRegistry:
        def list_all(self):
            return [FakeDomain()]

    monkeypatch.setattr(
        "homomics_lab.agent.permission_ruleset.get_domain_registry", FakeRegistry
    )
    registry = PermissionRegistry()
    assert registry.can_auto_approve_skill(
        "single_cell_specialist",
        "single-cell-transcriptomics",
        "bio-single-cell-preprocessing",
        "low",
    )
