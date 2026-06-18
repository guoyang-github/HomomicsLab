"""Structured project state for context assembly.

ProjectState captures the current execution state of a project so the agent
does not have to infer it from raw chat history. It is persisted in CBKB and
updated at the end of each turn.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from homomics_lab.knowledge.cbkb import CBKB


@dataclass
class FileRecord:
    """A file generated or referenced in the project."""

    path: str
    file_type: str = ""
    description: str = ""
    created_at: str = ""


@dataclass
class ProjectState:
    """Snapshot of a project's current execution state."""

    project_id: str
    completed_phases: List[str] = field(default_factory=list)
    pending_phases: List[str] = field(default_factory=list)
    generated_files: List[FileRecord] = field(default_factory=list)
    last_skill_id: Optional[str] = None
    last_parameters: Dict[str, Any] = field(default_factory=dict)
    open_hitl: List[Dict[str, Any]] = field(default_factory=list)
    recent_errors: List[str] = field(default_factory=list)
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_prompt_text(self) -> str:
        """Render the state as a concise prompt section."""
        lines = ["Current project state:"]
        if self.completed_phases:
            lines.append(f"- Completed phases: {', '.join(self.completed_phases)}")
        if self.pending_phases:
            lines.append(f"- Pending phases: {', '.join(self.pending_phases)}")
        if self.generated_files:
            recent = self.generated_files[-5:]
            lines.append("- Recent files:")
            for f in recent:
                lines.append(f"  - {f.path} ({f.file_type or 'file'})")
        if self.last_skill_id:
            lines.append(f"- Last executed skill: {self.last_skill_id}")
        if self.last_parameters:
            params = ", ".join(f"{k}={v}" for k, v in list(self.last_parameters.items())[:5])
            lines.append(f"- Last parameters: {params}")
        if self.open_hitl:
            lines.append(f"- Open human-in-the-loop items: {len(self.open_hitl)}")
        if self.recent_errors:
            lines.append("- Recent errors:")
            for err in self.recent_errors[-3:]:
                lines.append(f"  - {err}")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_id": self.project_id,
            "completed_phases": self.completed_phases,
            "pending_phases": self.pending_phases,
            "generated_files": [
                {"path": f.path, "file_type": f.file_type, "description": f.description, "created_at": f.created_at}
                for f in self.generated_files
            ],
            "last_skill_id": self.last_skill_id,
            "last_parameters": self.last_parameters,
            "open_hitl": self.open_hitl,
            "recent_errors": self.recent_errors,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectState":
        files = [
            FileRecord(
                path=f.get("path", ""),
                file_type=f.get("file_type", ""),
                description=f.get("description", ""),
                created_at=f.get("created_at", ""),
            )
            for f in data.get("generated_files", [])
        ]
        return cls(
            project_id=data.get("project_id", ""),
            completed_phases=list(data.get("completed_phases", [])),
            pending_phases=list(data.get("pending_phases", [])),
            generated_files=files,
            last_skill_id=data.get("last_skill_id"),
            last_parameters=dict(data.get("last_parameters", {})),
            open_hitl=list(data.get("open_hitl", [])),
            recent_errors=list(data.get("recent_errors", [])),
            updated_at=data.get("updated_at", datetime.now(timezone.utc).isoformat()),
        )


class ProjectStateManager:
    """Load and persist ProjectState via CBKB."""

    def __init__(self, cbkb: CBKB):
        self.cbkb = cbkb

    def load(self, project_id: str) -> ProjectState:
        """Load project state; return a fresh state if none exists."""
        data = self.cbkb.get_project_state(project_id)
        if data is None:
            return ProjectState(project_id=project_id)
        try:
            return ProjectState.from_dict(data)
        except Exception:
            return ProjectState(project_id=project_id)

    def save(self, state: ProjectState) -> None:
        """Persist project state to CBKB."""
        state.updated_at = datetime.now(timezone.utc).isoformat()
        try:
            self.cbkb.save_project_state(state.project_id, state.to_dict())
        except Exception:
            # Best-effort persistence; never break the chat flow.
            pass

    def update_from_turn(
        self,
        state: ProjectState,
        task_tree: Optional[Any],
        turn_result: Optional[Any],
    ) -> ProjectState:
        """Update project state based on the latest turn result.

        This is intentionally lightweight; detailed provenance lives in CBKB
        experiment nodes. Here we only keep the minimal state needed for the
        next turn's context.
        """
        if turn_result is None:
            return state

        # Record errors
        if getattr(turn_result, "error", None):
            state.recent_errors.append(str(turn_result.error))
            state.recent_errors = state.recent_errors[-10:]

        # Record HITL
        if getattr(turn_result, "hitl_task_id", None):
            state.open_hitl.append(
                {
                    "task_id": turn_result.hitl_task_id,
                    "checkpoint": turn_result.hitl_checkpoint,
                }
            )

        # Record completed/pending phases from task tree
        tree = getattr(turn_result, "task_tree", None) or task_tree
        if tree is not None and hasattr(tree, "tasks"):
            for task in tree.tasks:
                phase = getattr(task, "phase", None)
                if phase and phase not in state.completed_phases:
                    state.completed_phases.append(phase)
                # Heuristic: phases that appear later in the tree are pending
                task_status = getattr(task, "status", None)
                if task_status == "pending" and phase and phase not in state.pending_phases:
                    state.pending_phases.append(phase)

        # Clean pending phases that are now completed
        state.pending_phases = [p for p in state.pending_phases if p not in state.completed_phases]

        # Record last skill and parameters if available
        if getattr(turn_result, "agent_message", None):
            msg = turn_result.agent_message
            if getattr(msg, "skill_id", None):
                state.last_skill_id = msg.skill_id

        return state
