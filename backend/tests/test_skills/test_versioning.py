"""Tests for skill semantic versioning helpers."""

import pytest

from homomics_lab.skills.models import SkillDefinition, SkillInputSchema, SkillOutputSchema
from homomics_lab.skills.versioning import (
    SkillVersion,
    bump_version,
    detect_breaking_changes,
)


def test_parse_valid_semver():
    v = SkillVersion.parse("1.2.3")
    assert v.major == 1
    assert v.minor == 2
    assert v.patch == 3
    assert v.prerelease == ""


def test_parse_prerelease():
    v = SkillVersion.parse("2.0.0-beta.1")
    assert v.major == 2
    assert v.prerelease == "beta.1"


def test_parse_invalid():
    with pytest.raises(ValueError):
        SkillVersion.parse("not-a-version")


def test_compatible_same_major():
    assert SkillVersion.parse("1.2.0").is_compatible_with(SkillVersion.parse("1.5.0"))


def test_incompatible_major_bump():
    assert not SkillVersion.parse("1.0.0").is_compatible_with(SkillVersion.parse("2.0.0"))


def test_zero_major_not_compatible_across_minor():
    assert not SkillVersion.parse("0.1.0").is_compatible_with(SkillVersion.parse("0.2.0"))


def test_detect_breaking_input_changes():
    old = SkillDefinition(
        id="test",
        name="Test",
        version="1.0.0",
        category="test",
        input_schema=SkillInputSchema(
            properties={"a": {}, "b": {}},
            required=["a"],
        ),
        output_schema=SkillOutputSchema(),
    )
    new = SkillDefinition(
        id="test",
        name="Test",
        version="1.0.0",
        category="test",
        input_schema=SkillInputSchema(
            properties={"b": {}, "c": {}},
            required=["c"],
        ),
        output_schema=SkillOutputSchema(),
    )
    changes = detect_breaking_changes(old, new)
    assert any("Removed required inputs" in c for c in changes)
    assert any("Added new required inputs" in c for c in changes)


def test_detect_breaking_output_removed():
    old = SkillDefinition(
        id="test",
        name="Test",
        version="1.0.0",
        category="test",
        output_schema=SkillOutputSchema(properties={"result": {}}),
    )
    new = SkillDefinition(
        id="test",
        name="Test",
        version="1.0.0",
        category="test",
        output_schema=SkillOutputSchema(),
    )
    changes = detect_breaking_changes(old, new)
    assert any("Removed guaranteed outputs" in c for c in changes)


def test_bump_version_major_for_breaking():
    assert bump_version("1.2.3", ["breaking"]) == "2.0.0"


def test_bump_version_minor_for_non_breaking():
    assert bump_version("1.2.3", []) == "1.3.0"
