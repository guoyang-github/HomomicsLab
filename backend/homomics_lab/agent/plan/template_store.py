"""File-backed store for AnalysisTemplate presets."""

import json
import logging
import shutil
from pathlib import Path
from typing import List, Optional

from homomics_lab.agent.plan.template import AnalysisTemplate
from homomics_lab.config import Settings, settings as default_settings

logger = logging.getLogger(__name__)

_BUILTIN_TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates" / "analysis"


class AnalysisTemplateStore:
    """Store and retrieve analysis templates from JSON files.

    Templates are persisted under ``{data_dir}/analysis_templates/`` as individual
    JSON files. Built-in templates shipped with the package are copied into this
    directory on first use so users can edit or delete them without modifying the
    package installation.
    """

    def __init__(self, data_dir: Optional[Path] = None, settings: Optional[Settings] = None) -> None:
        self.settings = settings or default_settings
        self.data_dir = Path(data_dir) if data_dir is not None else self.settings.data_dir
        self.templates_dir = self.data_dir / "analysis_templates"
        self.templates_dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, template_id: str) -> Path:
        return self.templates_dir / f"{template_id}.json"

    def import_builtin_templates(self) -> int:
        """Copy built-in templates into the user data directory.

        Returns the number of templates imported.
        """
        if not _BUILTIN_TEMPLATES_DIR.exists():
            return 0
        imported = 0
        for source in _BUILTIN_TEMPLATES_DIR.glob("*.json"):
            dest = self._path_for(source.stem)
            if dest.exists():
                continue
            try:
                shutil.copy2(source, dest)
                imported += 1
            except Exception as exc:
                logger.warning("Failed to import built-in template %s: %s", source.name, exc)
        return imported

    def list_templates(self) -> List[AnalysisTemplate]:
        """Return all stored templates, sorted by name."""
        templates: List[AnalysisTemplate] = []
        if not self.templates_dir.exists():
            return templates
        for path in sorted(self.templates_dir.glob("*.json")):
            try:
                templates.append(self._load(path))
            except Exception as exc:
                logger.warning("Failed to load template %s: %s", path.name, exc)
        return sorted(templates, key=lambda t: t.name.lower())

    def get_template(self, template_id: str) -> Optional[AnalysisTemplate]:
        """Retrieve a single template by ID."""
        path = self._path_for(template_id)
        if not path.exists():
            return None
        try:
            return self._load(path)
        except Exception as exc:
            logger.warning("Failed to load template %s: %s", template_id, exc)
            return None

    def save_template(self, template: AnalysisTemplate) -> None:
        """Persist a template, replacing any existing one with the same ID."""
        path = self._path_for(template.template_id)
        path.write_text(
            json.dumps(template.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def delete_template(self, template_id: str) -> bool:
        """Delete a template. Returns True if it existed."""
        path = self._path_for(template_id)
        if not path.exists():
            return False
        try:
            path.unlink()
            return True
        except Exception as exc:
            logger.warning("Failed to delete template %s: %s", template_id, exc)
            return False

    @staticmethod
    def _load(path: Path) -> AnalysisTemplate:
        data = json.loads(path.read_text(encoding="utf-8"))
        return AnalysisTemplate.from_dict(data)
