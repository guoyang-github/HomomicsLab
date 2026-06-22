from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SkillInputSchema(BaseModel):
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

    def validate_input(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and fill defaults for skill input.

        If no input schema is defined (empty properties), pass through all data
        unchanged. This allows skills loaded from external directories without
        formal parameter schemas to work correctly.
        """
        if not self.input_schema.properties:
            return dict(data)

        validated = {}

        for key, prop in self.input_schema.properties.items():
            if key in data:
                validated[key] = data[key]
            elif "default" in prop:
                validated[key] = prop["default"]
            elif key in self.input_schema.required:
                raise ValueError(f"Missing required parameter: {key}")

        return validated

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

    @property
    def has_entrypoint(self) -> bool:
        """True when the skill has an executable script entrypoint.

        An explicit ``entrypoint`` path relative to ``source_dir`` takes
        precedence; otherwise ``scripts_dir/run.py`` is accepted.
        """
        src = self.source_dir
        if src is not None:
            entrypoint = self.metadata.get("entrypoint")
            if isinstance(entrypoint, (str, Path)):
                if (src / entrypoint).is_file():
                    return True
            if (src / "scripts" / "python" / "run.py").is_file():
                return True
            if (src / "scripts" / "r" / "run.R").is_file():
                return True
        # Discovery-level hint.
        return bool(self.metadata.get("has_entrypoint"))
