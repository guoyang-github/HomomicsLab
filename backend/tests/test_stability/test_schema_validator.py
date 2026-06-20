"""Tests for SchemaValidator."""


from homomics_lab.skills.models import SkillDefinition, SkillInputSchema, SkillOutputSchema
from homomics_lab.stability.schema_validator import SchemaValidator


class TestSchemaValidator:
    def test_empty_schema_passes(self):
        """Skills with no schema properties should pass all inputs."""
        skill = SkillDefinition(
            id="no_schema",
            name="No Schema",
            version="1.0",
            category="test",
            input_schema=SkillInputSchema(),
            output_schema=SkillOutputSchema(),
        )
        validator = SchemaValidator()
        result = validator.validate_input(skill, {"anything": "goes"})
        assert result.passed is True

    def test_required_field_missing(self):
        skill = SkillDefinition(
            id="needs_path",
            name="Needs Path",
            version="1.0",
            category="test",
            input_schema=SkillInputSchema(
                type="object",
                properties={"path": {"type": "string"}},
                required=["path"],
            ),
        )
        validator = SchemaValidator()
        result = validator.validate_input(skill, {})
        assert result.passed is False
        assert "Missing required input field: 'path'" in result.errors

    def test_type_mismatch(self):
        skill = SkillDefinition(
            id="needs_int",
            name="Needs Int",
            version="1.0",
            category="test",
            input_schema=SkillInputSchema(
                type="object",
                properties={"count": {"type": "integer"}},
                required=["count"],
            ),
        )
        validator = SchemaValidator()
        result = validator.validate_input(skill, {"count": "not a number"})
        assert result.passed is False
        assert any("Type mismatch for field 'count'" in e for e in result.errors)

    def test_valid_input_passes(self):
        skill = SkillDefinition(
            id="multi_param",
            name="Multi Param",
            version="1.0",
            category="test",
            input_schema=SkillInputSchema(
                type="object",
                properties={
                    "path": {"type": "string"},
                    "count": {"type": "integer"},
                    "threshold": {"type": "number"},
                },
                required=["path"],
            ),
        )
        validator = SchemaValidator()
        result = validator.validate_input(
            skill, {"path": "/tmp/file.h5ad", "count": 100, "threshold": 0.05}
        )
        assert result.passed is True
        assert result.errors == []

    def test_strict_mode_rejects_extra_fields(self):
        skill = SkillDefinition(
            id="strict",
            name="Strict",
            version="1.0",
            category="test",
            input_schema=SkillInputSchema(
                type="object",
                properties={"path": {"type": "string"}},
                required=["path"],
            ),
        )
        validator = SchemaValidator(strict=True)
        result = validator.validate_input(skill, {"path": "/tmp", "extra": "field"})
        assert result.passed is False
        assert any("Unexpected input field: 'extra'" in e for e in result.errors)

    def test_non_strict_mode_warns_extra_fields(self):
        skill = SkillDefinition(
            id="loose",
            name="Loose",
            version="1.0",
            category="test",
            input_schema=SkillInputSchema(
                type="object",
                properties={"path": {"type": "string"}},
                required=["path"],
            ),
        )
        validator = SchemaValidator(strict=False)
        result = validator.validate_input(skill, {"path": "/tmp", "extra": "field"})
        assert result.passed is True
        assert len(result.warnings) == 1
        assert "Unexpected input field" in result.warnings[0]

    def test_output_validation(self):
        skill = SkillDefinition(
            id="output_test",
            name="Output Test",
            version="1.0",
            category="test",
            output_schema=SkillOutputSchema(
                type="object",
                properties={
                    "status": {"type": "string"},
                    "count": {"type": "integer"},
                },
                required=["status"],
            ),
        )
        validator = SchemaValidator()

        # Missing required output
        result = validator.validate_output(skill, {"count": 42})
        assert result.passed is False
        assert "Missing required output field: 'status'" in result.errors

        # Valid output
        result = validator.validate_output(skill, {"status": "ok", "count": 42})
        assert result.passed is True

    def test_boolean_type(self):
        skill = SkillDefinition(
            id="bool_test",
            name="Bool Test",
            version="1.0",
            category="test",
            input_schema=SkillInputSchema(
                type="object",
                properties={"flag": {"type": "boolean"}},
                required=["flag"],
            ),
        )
        validator = SchemaValidator()

        # Integer 1 is not boolean
        result = validator.validate_input(skill, {"flag": 1})
        assert result.passed is False

        # True is boolean
        result = validator.validate_input(skill, {"flag": True})
        assert result.passed is True

    def test_array_type(self):
        skill = SkillDefinition(
            id="array_test",
            name="Array Test",
            version="1.0",
            category="test",
            input_schema=SkillInputSchema(
                type="object",
                properties={"genes": {"type": "array"}},
                required=["genes"],
            ),
        )
        validator = SchemaValidator()

        result = validator.validate_input(skill, {"genes": ["Gene1", "Gene2"]})
        assert result.passed is True

        result = validator.validate_input(skill, {"genes": "not a list"})
        assert result.passed is False

    def test_nullable_type(self):
        skill = SkillDefinition(
            id="nullable",
            name="Nullable",
            version="1.0",
            category="test",
            input_schema=SkillInputSchema(
                type="object",
                properties={"optional": {"type": ["string", "null"]}},
            ),
        )
        validator = SchemaValidator()

        result = validator.validate_input(skill, {"optional": None})
        assert result.passed is True

        result = validator.validate_input(skill, {"optional": "value"})
        assert result.passed is True

        result = validator.validate_input(skill, {"optional": 123})
        assert result.passed is False
