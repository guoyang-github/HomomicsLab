"""Data models for execution provenance."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class FileRecord:
    """A file referenced or produced during execution."""

    path: str
    checksum: Optional[str] = None
    size_bytes: int = 0
    mime_type: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "checksum": self.checksum,
            "size_bytes": self.size_bytes,
            "mime_type": self.mime_type,
        }


@dataclass
class ExecutionProvenance:
    """Full provenance record for a single skill execution."""

    execution_id: str
    skill_id: str
    skill_version: str
    project_id: Optional[str] = None
    session_id: Optional[str] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    input_files: List[FileRecord] = field(default_factory=list)
    output_files: List[FileRecord] = field(default_factory=list)
    sandbox_backend: str = ""
    container_image: Optional[str] = None
    container_digest: Optional[str] = None
    dependency_manifest: Dict[str, Any] = field(default_factory=dict)
    result_summary: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "skill_id": self.skill_id,
            "skill_version": self.skill_version,
            "project_id": self.project_id,
            "session_id": self.session_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "parameters": self.parameters,
            "input_files": [f.to_dict() for f in self.input_files],
            "output_files": [f.to_dict() for f in self.output_files],
            "sandbox_backend": self.sandbox_backend,
            "container_image": self.container_image,
            "container_digest": self.container_digest,
            "dependency_manifest": self.dependency_manifest,
            "result_summary": self.result_summary,
            "metadata": self.metadata,
        }
