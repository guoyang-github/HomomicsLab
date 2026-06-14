"""ReproducibilityBundle — complete record of an analysis for replay and sharing."""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ExecutionSnapshot:
    """Snapshot of the execution plan."""

    task_tree: Dict[str, Any]
    plan_version: str
    plan_prompt: str = ""
    plan_llm_model: str = ""
    plan_id: Optional[str] = None
    plan_result: Optional[Dict[str, Any]] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class EnvironmentLock:
    """Locked environment state."""

    python_version: str = ""
    pip_freeze: str = ""
    conda_env_export: str = ""
    system_info: Dict[str, str] = field(default_factory=dict)
    homomics_version: str = "0.3.0"


@dataclass
class SkillVersionLock:
    """Locked skill versions."""

    locked_skills: Dict[str, str] = field(default_factory=dict)
    skill_checksums: Dict[str, str] = field(default_factory=dict)


@dataclass
class CodeSnippet:
    """A piece of agent-generated code."""

    snippet_id: str
    phase: str
    code: str
    language: str = "python"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class HITLDecisionRecord:
    """Record of a human-in-the-loop decision."""

    checkpoint_id: str
    choice: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class ReproducibilityBundle:
    """Complete bundle containing everything needed to reproduce an analysis."""

    project_id: str
    random_seed: int

    execution_snapshot: Optional[ExecutionSnapshot] = None
    agent_code_archive: List[CodeSnippet] = field(default_factory=list)
    skill_versions: SkillVersionLock = field(default_factory=SkillVersionLock)
    environment_lock: EnvironmentLock = field(default_factory=EnvironmentLock)
    hitl_decisions: List[HITLDecisionRecord] = field(default_factory=list)

    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_json(self) -> str:
        """Serialize bundle to JSON string."""
        return json.dumps(asdict(self), indent=2, ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "ReproducibilityBundle":
        """Deserialize bundle from JSON string."""
        data = json.loads(json_str)
        return cls(
            project_id=data["project_id"],
            random_seed=data["random_seed"],
            execution_snapshot=ExecutionSnapshot(**data.get("execution_snapshot", {}))
            if data.get("execution_snapshot")
            else None,
            agent_code_archive=[CodeSnippet(**c) for c in data.get("agent_code_archive", [])],
            skill_versions=SkillVersionLock(**data.get("skill_versions", {})),
            environment_lock=EnvironmentLock(**data.get("environment_lock", {})),
            hitl_decisions=[HITLDecisionRecord(**h) for h in data.get("hitl_decisions", [])],
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
        )

    def save(self, path: Path) -> None:
        """Save bundle to a JSON file."""
        path.write_text(self.to_json(), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "ReproducibilityBundle":
        """Load bundle from a JSON file."""
        return cls.from_json(path.read_text(encoding="utf-8"))
