"""Pydantic models for domain declarations."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class DomainPhase(BaseModel):
    """A phase in a domain analysis strategy."""

    id: str = Field(description="Phase type identifier")
    required: bool = Field(default=True, description="Whether this phase is required")
    description: str = Field(default="", description="Human-readable description")
    skills: List[str] = Field(
        default_factory=list,
        description="Candidate skill IDs for this phase",
    )
    default_skill: Optional[str] = Field(
        default=None,
        description="Default skill if none specified",
    )


class DomainStateCheck(BaseModel):
    """A conditional check on data state that may modify the plan.

    The condition is expressed as a string expression that will be evaluated
    against the DataState. Example: 'host_contamination > 0.1'.
    """

    condition: str = Field(description="Expression evaluated against DataState")
    action: str = Field(description="insert | skip | modify_param")
    target: str = Field(description="Phase ID or param name to act on")
    value: Optional[Any] = Field(default=None, description="New value for modify_param")
    after: Optional[str] = Field(
        default=None,
        description="For insert: phase to insert after",
    )

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        allowed = {"insert", "skip", "modify_param"}
        if v not in allowed:
            raise ValueError(f"action must be one of {allowed}, got '{v}'")
        return v


class DomainIntent(BaseModel):
    """Intent matching configuration for a domain."""

    analysis_type: str = Field(description="Intent type identifier")
    keywords: List[str] = Field(
        default_factory=list,
        description="Keywords that trigger this intent",
    )
    examples: List[str] = Field(
        default_factory=list,
        description="Natural-language examples for semantic intent matching",
    )
    complexity_indicators: List[str] = Field(
        default_factory=list,
        description="Keywords indicating complex (multi-step) analysis",
    )
    data_scale_patterns: List[str] = Field(
        default_factory=list,
        description="Regex patterns to extract data scale hints",
    )


class DomainDAGSeed(BaseModel):
    """A seed edge for the SkillDAG."""

    from_skill: str = Field(alias="from")
    to_skill: str = Field(alias="to")
    type: str = Field(description="followed_by | conflicts_with | alternative_to | depends_on")
    context: str = Field(default="", description="Human-readable explanation")

    model_config = {"populate_by_name": True}


class DomainRole(BaseModel):
    """An agent role definition for a domain."""

    role_id: str
    name: str
    description: str = ""
    allowed_skills: List[str] = Field(default_factory=list)
    allowed_tools: List[str] = Field(default_factory=list)
    permissions: Dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(default=2, description="Role priority for task routing")


class DomainSOP(BaseModel):
    """A standard operating procedure for a domain."""

    id: str
    title: str
    version: str = "1.0.0"
    locked: bool = False
    content: str = ""


class DomainDefinition(BaseModel):
    """Complete declaration of a bioinformatics domain.

    A single domain.yaml file declares everything needed to extend HomomicsLab
    to a new sub-discipline.
    """

    domain: str = Field(description="Domain identifier (e.g. metagenomics, genomics)")
    description: str = Field(default="", description="Human-readable description")
    version: str = Field(default="1.0.0")

    # Analysis strategy
    phases: List[DomainPhase] = Field(default_factory=list)
    state_checks: List[DomainStateCheck] = Field(default_factory=list)

    # Intent analysis
    intents: List[DomainIntent] = Field(default_factory=list)

    # SkillDAG seeds
    dag_seeds: List[DomainDAGSeed] = Field(default_factory=list)

    # Agent roles
    roles: List[DomainRole] = Field(default_factory=list)

    # SOPs
    sops: List[DomainSOP] = Field(default_factory=list)

    # DataState schema (optional - describes expected domain-specific fields)
    data_state_schema: Dict[str, Any] = Field(
        default_factory=dict,
        description="Schema for domain-specific DataState fields",
    )

    # Skills directory (relative to domain.yaml)
    skills_dir: Optional[str] = Field(
        default=None,
        description="Relative path to skills directory",
    )

    # Code generation guidance
    preferred_libraries: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Preferred libraries per language (python, r, bash)",
    )
    code_templates: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Named code templates for common tasks",
    )
    data_sources: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Domain-specific data sources available to generated code",
    )
    fallback_rules: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Rules for selecting execution mode when no curated skill matches",
    )

    def get_intent_keywords(self) -> Dict[str, List[str]]:
        """Build a map of analysis_type -> keywords for IntentAnalyzer."""
        return {
            intent.analysis_type: intent.keywords
            for intent in self.intents
        }

    def get_phase_types(self) -> List[str]:
        """Return all phase type IDs in this domain."""
        return [phase.id for phase in self.phases]
