"""Tests for anti-hallucination parameter validation."""

import pytest

from homomics_lab.skills.models import SkillDefinition, SkillInputSchema


def _make_skill(properties: dict, required: list = None) -> SkillDefinition:
    return SkillDefinition(
        id="test",
        name="Test Skill",
        version="1.0.0",
        category="test",
        input_schema=SkillInputSchema(
            type="object",
            properties=properties,
            required=required or [],
        ),
    )


def test_enum_validation_rejects_invalid_value():
    skill = _make_skill({"mode": {"type": "string", "enum": ["fast", "slow"]}})

    with pytest.raises(ValueError, match="must be one of"):
        skill.validate_input({"mode": "invalid"})


def test_enum_validation_accepts_valid_value():
    skill = _make_skill({"mode": {"type": "string", "enum": ["fast", "slow"]}})

    validated = skill.validate_input({"mode": "fast"})

    assert validated["mode"] == "fast"


def test_minimum_maximum_validation():
    skill = _make_skill({
        "iterations": {"type": "integer", "minimum": 1, "maximum": 10}
    })

    with pytest.raises(ValueError, match="must be >="):
        skill.validate_input({"iterations": 0})

    with pytest.raises(ValueError, match="must be <="):
        skill.validate_input({"iterations": 11})

    assert skill.validate_input({"iterations": 5})["iterations"] == 5


def test_string_length_validation():
    skill = _make_skill({
        "name": {"type": "string", "minLength": 2, "maxLength": 5}
    })

    with pytest.raises(ValueError, match="at least"):
        skill.validate_input({"name": "a"})

    with pytest.raises(ValueError, match="at most"):
        skill.validate_input({"name": "abcdef"})

    assert skill.validate_input({"name": "abc"})["name"] == "abc"


def test_pattern_validation():
    skill = _make_skill({
        "sample_id": {"type": "string", "pattern": r"^[A-Z0-9]+$"}
    })

    with pytest.raises(ValueError, match="must match pattern"):
        skill.validate_input({"sample_id": "sample-01"})

    assert skill.validate_input({"sample_id": "S01"})["sample_id"] == "S01"


def test_source_and_rationale_metadata_are_preserved():
    skill = _make_skill({
        "threshold": {
            "type": "number",
            "source": "user",
            "range": "0..1",
            "rationale": "Controls sensitivity",
        }
    })

    prop = skill.input_schema.properties["threshold"]
    assert prop["source"] == "user"
    assert prop["range"] == "0..1"
    assert prop["rationale"] == "Controls sensitivity"
