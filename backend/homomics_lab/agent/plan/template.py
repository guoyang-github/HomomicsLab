"""AnalysisTemplate — user-facing scenario presets for plan generation.

An AnalysisTemplate sits between the user and the Domain/PlanEngine:
- Domain defines which phases exist.
- AnalysisTemplate defines default parameters and preferred skills for a concrete
  scenario (e.g. "10x Genomics 3' scRNA-seq").
- PlanEngine applies the template when generating a plan.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AnalysisTemplate:
    """A reusable scenario preset for analysis planning."""

    template_id: str
    name: str
    description: str = ""
    domain: str = ""  # maps to an AnalysisStrategy / domain name
    applicable_intents: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    phase_defaults: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    preferred_skills: Dict[str, str] = field(default_factory=dict)
    default_parameters: Dict[str, Any] = field(default_factory=dict)
    sop_ids: List[str] = field(default_factory=list)
    data_sources: List[Dict[str, Any]] = field(default_factory=list)
    icon: Optional[str] = None
    version: str = "1.0.0"

    # Advanced scenario customisation
    phase_overrides: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    """Per-phase overrides: required, description, add_skills, remove_skills, preferred_skill."""

    insert_phases: List[Dict[str, Any]] = field(default_factory=list)
    """New phases to insert after a target phase. Each dict must contain
    'after' (phase_type) and 'phase' (phase spec dict)."""

    remove_phases: List[str] = field(default_factory=list)
    """Phase types to remove from the skeleton."""

    data_type_rules: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    """Conditional overrides keyed by data_state.data_type.
    Each value may contain phase_overrides, insert_phases, remove_phases."""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "template_id": self.template_id,
            "name": self.name,
            "description": self.description,
            "domain": self.domain,
            "applicable_intents": self.applicable_intents,
            "tags": self.tags,
            "phase_defaults": self.phase_defaults,
            "preferred_skills": self.preferred_skills,
            "default_parameters": self.default_parameters,
            "sop_ids": self.sop_ids,
            "data_sources": self.data_sources,
            "icon": self.icon,
            "version": self.version,
            "phase_overrides": self.phase_overrides,
            "insert_phases": self.insert_phases,
            "remove_phases": self.remove_phases,
            "data_type_rules": self.data_type_rules,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AnalysisTemplate":
        return cls(
            template_id=data["template_id"],
            name=data.get("name", ""),
            description=data.get("description", ""),
            domain=data.get("domain", ""),
            applicable_intents=list(data.get("applicable_intents", [])),
            tags=list(data.get("tags", [])),
            phase_defaults=dict(data.get("phase_defaults", {})),
            preferred_skills=dict(data.get("preferred_skills", {})),
            default_parameters=dict(data.get("default_parameters", {})),
            sop_ids=list(data.get("sop_ids", [])),
            data_sources=list(data.get("data_sources", [])),
            icon=data.get("icon"),
            version=data.get("version", "1.0.0"),
            phase_overrides=dict(data.get("phase_overrides", {})),
            insert_phases=list(data.get("insert_phases", [])),
            remove_phases=list(data.get("remove_phases", [])),
            data_type_rules=dict(data.get("data_type_rules", {})),
        )
