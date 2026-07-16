import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SkillInputSchema(BaseModel):
    """Input schema for a skill.

    Each property may carry JSON-Schema constraints plus anti-hallucination
    metadata:
      - ``source``: expected provenance ("user", "file", "llm-derived", "auto").
      - ``range``: a human-readable description of valid values.
      - ``rationale``: why the parameter is needed.
    """

    type: str = "object"
    properties: Dict[str, Any] = Field(default_factory=dict)
    required: List[str] = Field(default_factory=list)


class SkillOutputSchema(BaseModel):
    type: str = "object"
    properties: Dict[str, Any] = Field(default_factory=dict)
    required: List[str] = Field(default_factory=list)


class SkillResources(BaseModel):
    memory: str = "4G"
    cpu: int = 2
    time: str = "30m"


class SkillRuntime(BaseModel):
    type: str = "python"
    python_version: str = "3.10"
    dependencies: List[str] = Field(default_factory=list)
    executor: str = "auto"  # auto/local/slurm/cloud
    resources: SkillResources = Field(default_factory=SkillResources)


class SkillTestCase(BaseModel):
    name: str
    input: Dict[str, Any]
    expected_output: Dict[str, Any]


class SkillQuality(BaseModel):
    test_cases: List[SkillTestCase] = Field(default_factory=list)
    validation_rules: List[str] = Field(default_factory=list)


class SkillDefinition(BaseModel):
    id: str
    name: str
    version: str
    category: str
    author: str = "builtin"
    description: str = ""
    input_schema: SkillInputSchema = Field(default_factory=SkillInputSchema)
    output_schema: SkillOutputSchema = Field(default_factory=SkillOutputSchema)
    runtime: SkillRuntime = Field(default_factory=SkillRuntime)
    quality: SkillQuality = Field(default_factory=SkillQuality)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    # Optional domain/category affiliations. A skill can belong to zero or more
    # domains and categories. When ``domains`` is empty, the skill is considered
    # standalone / domain-agnostic.
    domains: List[str] = Field(default_factory=list)
    categories: List[str] = Field(default_factory=list)

    def belongs_to_domain(self, domain: str) -> bool:
        """Return True if the skill is affiliated with the given domain."""
        return domain in self.domains

    def has_category(self, category: str) -> bool:
        """Return True if the skill has the given category tag."""
        return category in self.categories

    @property
    def is_standalone(self) -> bool:
        """Return True when the skill is not tied to any specific domain.

        Standalone skills are available to the standalone planner and can be
        used without a domain strategy.
        """
        return not self.domains

    def validate_input(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and fill defaults for skill input.

        If no input schema is defined (empty properties), pass through all data
        unchanged. This allows skills loaded from external directories without
        formal parameter schemas to work correctly.

        Properties may include anti-hallucination metadata:
          - ``source``: expected provenance ("user", "file", "llm-derived", "auto").
          - ``range``: human-readable constraint description.
          - ``rationale``: why the parameter exists.
        In addition, JSON-Schema-style constraints are enforced when present:
          - ``enum``, ``minimum``/``maximum``, ``minLength``/``maxLength``,
            ``pattern``.
        """
        if not self.input_schema.properties:
            return dict(data)

        validated = {}

        for key, prop in self.input_schema.properties.items():
            if key in data:
                value = data[key]
                self._validate_parameter(key, prop, value)
                validated[key] = value
            elif "default" in prop:
                validated[key] = prop["default"]
            elif key in self.input_schema.required:
                raise ValueError(f"Missing required parameter: {key}")

        return validated

    @staticmethod
    def _validate_parameter(key: str, prop: Dict[str, Any], value: Any) -> None:
        """Validate a single parameter value against its schema."""
        if value is None and prop.get("nullable"):
            return

        # enum
        enum_values = prop.get("enum")
        if enum_values is not None and value not in enum_values:
            raise ValueError(
                f"Parameter '{key}' must be one of {enum_values}, got {value!r}"
            )

        # numeric range
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            minimum = prop.get("minimum")
            if minimum is not None and value < minimum:
                raise ValueError(
                    f"Parameter '{key}' must be >= {minimum}, got {value}"
                )
            maximum = prop.get("maximum")
            if maximum is not None and value > maximum:
                raise ValueError(
                    f"Parameter '{key}' must be <= {maximum}, got {value}"
                )

        # string length
        if isinstance(value, str):
            min_length = prop.get("minLength")
            if min_length is not None and len(value) < min_length:
                raise ValueError(
                    f"Parameter '{key}' must be at least {min_length} characters"
                )
            max_length = prop.get("maxLength")
            if max_length is not None and len(value) > max_length:
                raise ValueError(
                    f"Parameter '{key}' must be at most {max_length} characters"
                )
            pattern = prop.get("pattern")
            if pattern is not None and not re.search(pattern, value):
                raise ValueError(
                    f"Parameter '{key}' must match pattern {pattern!r}"
                )

    @property
    def source_dir(self) -> Optional[Path]:
        """Canonical source directory for the skill, if known."""
        raw = self.metadata.get("source_dir") or self.metadata.get("source_path")
        if isinstance(raw, (str, Path)):
            return Path(raw)
        return None

    @property
    def body_path(self) -> Optional[Path]:
        """Path to the skill's SKILL.md body (Level 2)."""
        src = self.source_dir
        return src / "SKILL.md" if src else None

    @property
    def has_scripts(self) -> bool:
        """True when the skill has a scripts directory (Level 3 reference material)."""
        src = self.source_dir
        if src is not None:
            return (src / "scripts").is_dir()
        # Discovery-level skills may record this hint before scripts_dir is resolved.
        return bool(self.metadata.get("has_scripts"))

