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

import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from homomics_lab.config import settings


class ProjectExporter:
    """Export a project and all its data to a .homomics archive."""

    EXTENSION = ".homomics"

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
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "version": "1.0",
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
        """Collect project configuration."""
        # In MVP, config is minimal. Future versions may include
        # analysis parameters, skill versions, environment info.
        return {
            "project_id": self.project_id,
            "data_dir": str(settings.data_dir),
        }

    def _generate_readme(self, meta: Dict[str, Any]) -> str:
        lines = [
            "HomomicsLab Project Archive",
            "===========================",
            "",
            f"Project ID: {meta['project_id']}",
            f"Exported: {meta['exported_at']}",
            f"Format Version: {meta['version']}",
            "",
            "Files:",
            "  project.json   - Project metadata",
            "  MEMORY.md      - Human-readable experiment log",
            "  notes.json     - Structured experiment notes",
            "  config.json    - Project configuration",
            "",
            "Import this archive into HomomicsLab to restore the project.",
        ]
        return "\n".join(lines)


class ProjectImporter:
    """Import a project from a .homomics archive."""

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
            if "config.json" in zf.namelist():
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
