"""SchemaValidator — strict input/output validation for skill execution.

Validates that skill inputs conform to the skill's input_schema (JSON Schema)
and that outputs conform to the output_schema. Catches type mismatches,
missing required fields, and unexpected fields (in strict mode).
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from homomics_lab.skills.models import SkillDefinition


@dataclass
class ValidationResult:
    """Result of a schema validation check."""

    passed: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.passed


class SchemaValidator:
    """Validates skill inputs and outputs against their declared schemas."""

    def __init__(self, strict: bool = False):
        """
        Args:
            strict: If True, reject inputs with fields not declared in the schema.
        """
        self.strict = strict

    # ─────────────────────────────────────────
    # Input validation
    # ─────────────────────────────────────────

    def validate_input(
        self,
        skill: SkillDefinition,
        inputs: Dict[str, Any],
    ) -> ValidationResult:
        """Validate input data against the skill's input_schema."""
        schema = skill.input_schema
        errors = []
        warnings = []

        # Empty schema = no validation (pass-through for external skills)
        if not schema.properties and not schema.required:
            return ValidationResult(passed=True)

        # Check required fields
        for field_name in schema.required:
            if field_name not in inputs:
                errors.append(f"Missing required input field: '{field_name}'")

        # Check known fields
        for field_name, value in inputs.items():
            if field_name in schema.properties:
                prop = schema.properties[field_name]
                type_error = self._check_type(value, prop.get("type"), field_name)
                if type_error:
                    errors.append(type_error)
            elif self.strict:
                errors.append(
                    f"Unexpected input field: '{field_name}' "
                    f"(not declared in schema for skill '{skill.id}')"
                )
            else:
                warnings.append(
                    f"Unexpected input field: '{field_name}' "
                    f"(not declared in schema for skill '{skill.id}')"
                )

        return ValidationResult(
            passed=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    # ─────────────────────────────────────────
    # Output validation
    # ─────────────────────────────────────────

    def validate_output(
        self,
        skill: SkillDefinition,
        output: Dict[str, Any],
    ) -> ValidationResult:
        """Validate output data against the skill's output_schema."""
        schema = skill.output_schema
        errors = []
        warnings = []

        # Empty schema = no validation
        if not schema.properties and not schema.required:
            return ValidationResult(passed=True)

        # Check required fields
        for field_name in schema.required:
            if field_name not in output:
                errors.append(f"Missing required output field: '{field_name}'")

        # Check known fields
        for field_name, value in output.items():
            if field_name in schema.properties:
                prop = schema.properties[field_name]
                type_error = self._check_type(value, prop.get("type"), field_name)
                if type_error:
                    errors.append(type_error)
            elif self.strict:
                errors.append(f"Unexpected output field: '{field_name}'")
            else:
                warnings.append(f"Unexpected output field: '{field_name}'")

        return ValidationResult(
            passed=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    # ─────────────────────────────────────────
    # Type checking
    # ─────────────────────────────────────────

    @staticmethod
    def _check_type(value: Any, expected_type: Optional[str], field_name: str) -> Optional[str]:
        """Check if a value matches an expected JSON Schema type.

        Returns:
            Error message string if type mismatch, None if OK.
        """
        if expected_type is None:
            return None

        type_checks = {
            "string": lambda v: isinstance(v, str),
            "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
            "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
            "boolean": lambda v: isinstance(v, bool),
            "array": lambda v: isinstance(v, list),
            "object": lambda v: isinstance(v, dict),
            "null": lambda v: v is None,
        }

        # Handle array of types: ["string", "null"]
        if isinstance(expected_type, list):
            if any(SchemaValidator._check_single_type(value, t) for t in expected_type):
                return None
            return (
                f"Type mismatch for field '{field_name}': "
                f"expected one of {expected_type}, got {type(value).__name__}"
            )

        if SchemaValidator._check_single_type(value, expected_type):
            return None

        return (
            f"Type mismatch for field '{field_name}': "
            f"expected {expected_type}, got {type(value).__name__}"
        )

    @staticmethod
    def _check_single_type(value: Any, expected: str) -> bool:
        """Check a single type expectation."""
        if expected == "string":
            return isinstance(value, str)
        if expected == "integer":
            return isinstance(value, int) and not isinstance(value, bool)
        if expected == "number":
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        if expected == "boolean":
            return isinstance(value, bool)
        if expected == "array":
            return isinstance(value, list)
        if expected == "object":
            return isinstance(value, dict)
        if expected == "null":
            return value is None
        return True  # Unknown type = permissive
