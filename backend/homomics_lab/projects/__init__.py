"""Project export/import for sharing and reproducibility.

A .homomics file is a ZIP archive containing:
  - project.json       (metadata, config)
  - MEMORY.md          (human-readable experiment log)
  - notes.json         (structured experiment notes)
  - task_tree.json     (analysis pipeline snapshot)
  - reports/           (HTML/Markdown/PDF reports)

Usage:
    exporter = ProjectExporter(project_id="proj_1")
    archive_path = exporter.export_to(Path("/tmp/proj_1.homomics"))

    importer = ProjectImporter()
    imported_id = importer.import_from(Path("/tmp/proj_1.homomics"))
"""

import importlib.metadata
import json
import logging
import platform
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from homomics_lab.config import settings
from homomics_lab.context.project_state import ProjectStateManager
from homomics_lab.knowledge.cbkb import CBKB

logger = logging.getLogger(__name__)


class ProjectExporter:
    """Export a project and all its data to a .homomics archive."""

    EXTENSION = ".homomics"
    EXPORTER_VERSION = "1.1"
    APP_VERSION = "0.5.0"

    def __init__(self, project_id: str):
        self.project_id = project_id

    def export_to(self, output_path: Optional[Path] = None) -> Path:
        """Export project to a .homomics archive.

        Args:
            output_path: Destination path. Defaults to
                <data_dir>/exports/<project_id>.homomics

        Returns:
            Path to the created archive.
        """
        if output_path is None:
            exports_dir = settings.data_dir / "exports"
            exports_dir.mkdir(parents=True, exist_ok=True)
            output_path = exports_dir / f"{self.project_id}{self.EXTENSION}"

        project_dir = settings.data_dir / "projects" / self.project_id

        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # 1. Project metadata
            meta = self._gather_metadata()
            zf.writestr("project.json", json.dumps(meta, indent=2, ensure_ascii=False))

            # 2. MEMORY.md
            memory_md = project_dir / "MEMORY.md"
            if memory_md.exists():
                zf.write(memory_md, "MEMORY.md")

            # 3. Experiment notes
            notes = self._gather_notes()
            if notes:
                zf.writestr("notes.json", json.dumps(notes, indent=2, ensure_ascii=False))

            # 4. Config / parameters
            config = self._gather_config()
            zf.writestr("config.json", json.dumps(config, indent=2, ensure_ascii=False))

            # 5. README for manual inspection
            zf.writestr("README.txt", self._generate_readme(meta))

        return output_path

    def _gather_metadata(self) -> Dict[str, Any]:
        """Collect project metadata."""
        return {
            "project_id": self.project_id,
            "original_project_id": self.project_id,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "version": "1.0",
            "exporter_version": self.EXPORTER_VERSION,
        }

    def _gather_notes(self) -> List[Dict[str, Any]]:
        """Collect experiment notes from SQLite."""
        db_path = settings.data_dir / "projects" / self.project_id / "experiment.db"
        if not db_path.exists():
            return []

        import sqlite3

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM experiment_notes WHERE project_id = ? ORDER BY created_at",
            (self.project_id,),
        ).fetchall()
        conn.close()

        return [
            {
                "id": r["id"],
                "step": r["step"],
                "text": r["text"],
                "tags": json.loads(r["tags"]),
                "metadata": json.loads(r["metadata"]),
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    def _gather_config(self) -> Dict[str, Any]:
        """Collect rich project configuration for reproducibility."""
        return {
            "project_id": self.project_id,
            "data_dir": str(settings.data_dir),
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "exporter_version": self.EXPORTER_VERSION,
            "analysis_state": self._gather_analysis_state(),
            "skill_versions": self._gather_skill_versions(),
            "environment": self._gather_environment(),
            "settings_snapshot": self._gather_settings_snapshot(),
            "sop_references": self._gather_sop_references(),
        }

    def _gather_analysis_state(self) -> Dict[str, Any]:
        """Load project analysis state from CBKB."""
        try:
            cbkb = CBKB(settings.data_dir)
            manager = ProjectStateManager(cbkb)
            return manager.load(self.project_id).to_dict()
        except Exception:
            logger.exception("Failed to gather analysis state for project %s", self.project_id)
            return {}

    def _gather_skill_versions(self) -> List[Dict[str, Any]]:
        """Read enabled skill versions from the skill store metadata."""
        skills_path = settings.data_dir / "skill_store" / "skills.json"
        if not skills_path.exists():
            return []

        try:
            raw = json.loads(skills_path.read_text(encoding="utf-8"))
        except Exception:
            logger.exception("Failed to read skill store metadata")
            return []

        entries: List[Dict[str, Any]] = []
        for entry in raw.values():
            if not isinstance(entry, dict):
                continue
            entries.append(
                {
                    "id": entry.get("id"),
                    "namespace": entry.get("namespace"),
                    "version": entry.get("version"),
                    "source": entry.get("source"),
                    "trusted": entry.get("trusted"),
                    "enabled": entry.get("enabled"),
                }
            )
        return entries

    def _gather_environment(self) -> Dict[str, Any]:
        """Capture environment versions relevant to reproducibility."""
        dependencies = {}
        for package in ("scanpy", "anndata", "pandas", "numpy", "sqlalchemy"):
            try:
                dependencies[package] = importlib.metadata.version(package)
            except Exception:
                dependencies[package] = None

        return {
            "python_version": platform.python_version(),
            "app_version": self.APP_VERSION,
            "dependencies": dependencies,
        }

    def _gather_settings_snapshot(self) -> Dict[str, Any]:
        """Return a safe, reproducibility-oriented settings snapshot."""
        masked = settings.masked_dump()
        database_url = masked.get("database_url", "")
        if database_url.startswith("sqlite"):
            database_url_driver = "sqlite"
        elif database_url.startswith("postgresql"):
            database_url_driver = "postgresql"
        else:
            database_url_driver = "unknown"

        return {
            "app_name": masked.get("app_name"),
            "database_url_driver": database_url_driver,
            "storage_backend": masked.get("storage_backend"),
            "queue_backend": masked.get("queue_backend"),
            "llm_model": masked.get("llm_model"),
            "llm_provider": masked.get("llm_provider"),
            "semantic_search_model": masked.get("semantic_search_model"),
        }

    def _gather_sop_references(self) -> List[str]:
        """Collect relevant SOP identifiers from CBKB or filesystem."""
        try:
            cbkb = CBKB(settings.data_dir)
            sops = cbkb.list_sops()
            return [sop.id for sop in sops[:10]]
        except Exception:
            logger.exception("Failed to list CBKB SOPs, falling back to filesystem")

        fallback_dir = settings.data_dir / "cbkb" / "sops"
        if not fallback_dir.exists():
            return []
        return [
            p.name
            for p in fallback_dir.iterdir()
            if p.is_dir() and not p.name.startswith(".")
        ][:10]

    def _generate_readme(self, meta: Dict[str, Any]) -> str:
        lines = [
            "HomomicsLab Project Archive",
            "===========================",
            "",
            f"Project ID: {meta['project_id']}",
            f"Exported: {meta['exported_at']}",
            f"Format Version: {meta['version']}",
            f"Exporter Version: {meta.get('exporter_version', 'unknown')}",
            "",
            "Files:",
            "  project.json   - Project metadata and provenance",
            "  MEMORY.md      - Human-readable experiment log",
            "  notes.json     - Structured experiment notes",
            "  config.json    - Project configuration, analysis state, skill versions, environment, and SOP references",
            "",
            "Import this archive into HomomicsLab to restore the project.",
        ]
        return "\n".join(lines)


class ProjectImporter:
    """Import a project from a .homomics archive."""

    REQUIRED_REPRODUCIBILITY_FIELDS = {
        "analysis_state",
        "skill_versions",
        "environment",
        "settings_snapshot",
        "sop_references",
    }

    def import_from(
        self,
        archive_path: Path,
        target_project_id: Optional[str] = None,
    ) -> str:
        """Import a project from a .homomics archive.

        Args:
            archive_path: Path to the .homomics file.
            target_project_id: Optional new project ID. If not provided,
                a new ID is generated.

        Returns:
            The imported project ID.
        """
        if not zipfile.is_zipfile(archive_path):
            raise ValueError(f"Not a valid archive: {archive_path}")

        with zipfile.ZipFile(archive_path, "r") as zf:
            # Read metadata
            meta = json.loads(zf.read("project.json"))
            original_id = meta["project_id"]
            project_id = target_project_id or f"{original_id}_imported"

            # Validate reproducibility config
            if "config.json" not in zf.namelist():
                raise ValueError(f"Archive missing config.json: {archive_path}")

            config = json.loads(zf.read("config.json"))
            missing_fields = self.REQUIRED_REPRODUCIBILITY_FIELDS - set(config.keys())
            if missing_fields:
                logger.warning(
                    "Archive %s is missing reproducibility fields: %s",
                    archive_path,
                    ", ".join(sorted(missing_fields)),
                )

            # Create project directory
            project_dir = settings.data_dir / "projects" / project_id
            project_dir.mkdir(parents=True, exist_ok=True)

            # Extract MEMORY.md
            if "MEMORY.md" in zf.namelist():
                (project_dir / "MEMORY.md").write_text(
                    zf.read("MEMORY.md").decode("utf-8"), encoding="utf-8"
                )

            # Import notes
            if "notes.json" in zf.namelist():
                notes = json.loads(zf.read("notes.json"))
                self._import_notes(project_id, notes)

            # Extract config
            (project_dir / "config.json").write_bytes(zf.read("config.json"))

        return project_id

    def _import_notes(self, project_id: str, notes: List[Dict[str, Any]]) -> None:
        """Import experiment notes into SQLite."""
        import sqlite3

        db_path = settings.data_dir / "projects" / project_id / "experiment.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(db_path))
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS experiment_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                step TEXT,
                text TEXT NOT NULL,
                tags TEXT NOT NULL DEFAULT '[]',
                metadata TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            )
            """
        )

        for note in notes:
            conn.execute(
                """
                INSERT INTO experiment_notes (project_id, step, text, tags, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    note.get("step"),
                    note["text"],
                    json.dumps(note.get("tags", []), ensure_ascii=False),
                    json.dumps(note.get("metadata", {}), ensure_ascii=False),
                    note["created_at"],
                ),
            )
        conn.commit()
        conn.close()
