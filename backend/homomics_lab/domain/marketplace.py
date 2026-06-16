"""Domain template marketplace — import/export domain.yaml and code templates.

Supports:
  - Listing locally available domains
  - Exporting a domain as a zip archive
  - Importing a domain from a zip archive, local path, or git URL
  - Importing standalone code templates into an existing domain
"""

import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import yaml

from homomics_lab.skills.registry import SkillRegistry


class DomainMarketplaceError(Exception):
    """Raised when marketplace operations fail."""

    pass


@dataclass
class DomainListing:
    """Lightweight description of an available domain template."""

    domain_id: str
    name: str
    description: str
    version: str
    path: str
    source: str  # "builtin" | "marketplace" | "custom"


class DomainMarketplace:
    """Manage domain template import/export."""

    def __init__(
        self,
        builtin_domains_dir: Path,
        marketplace_dir: Path,
        skill_registry: Optional[SkillRegistry] = None,
    ):
        self.builtin_domains_dir = Path(builtin_domains_dir)
        self.marketplace_dir = Path(marketplace_dir)
        self.marketplace_dir.mkdir(parents=True, exist_ok=True)
        self.skill_registry = skill_registry or SkillRegistry()

    def list_domains(self) -> List[DomainListing]:
        """List all available domain templates."""
        listings: List[DomainListing] = []
        seen: set[str] = set()

        for source, root in [
            ("builtin", self.builtin_domains_dir),
            ("marketplace", self.marketplace_dir),
        ]:
            if not root.exists():
                continue
            for domain_yaml in root.rglob("domain.yaml"):
                try:
                    data = yaml.safe_load(domain_yaml.read_text(encoding="utf-8"))
                except Exception:
                    continue
                domain_id = data.get("domain", domain_yaml.parent.name)
                if domain_id in seen:
                    continue
                seen.add(domain_id)
                listings.append(DomainListing(
                    domain_id=domain_id,
                    name=domain_id,
                    description=data.get("description", ""),
                    version=data.get("version", "1.0.0"),
                    path=str(domain_yaml.parent),
                    source=source,
                ))
        return listings

    def export_domain(self, domain_id: str, output_path: Optional[Path] = None) -> Path:
        """Export a domain template to a zip archive.

        Args:
            domain_id: Domain identifier.
            output_path: Optional explicit output path. Defaults to a temp file.

        Returns:
            Path to the created zip archive.
        """
        source_dir = self._find_domain_dir(domain_id)
        if source_dir is None:
            raise DomainMarketplaceError(f"Domain '{domain_id}' not found")

        if output_path is None:
            output_path = Path(tempfile.gettempdir()) / f"{domain_id}_domain.zip"

        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in source_dir.rglob("*"):
                if file_path.is_file():
                    arcname = file_path.relative_to(source_dir)
                    zf.write(file_path, arcname)
        return output_path

    def import_domain(
        self,
        source: str,
        target_name: Optional[str] = None,
    ) -> Path:
        """Import a domain template from a zip archive, local path, or git URL.

        Args:
            source: Path to zip/local dir, or git URL.
            target_name: Optional explicit directory name under marketplace_dir.

        Returns:
            Path to the imported domain directory.
        """
        parsed = urlparse(source)
        is_git = parsed.scheme in {"http", "https", "git", "ssh"} or source.endswith(".git")

        if is_git:
            temp_dir = Path(tempfile.mkdtemp())
            self._clone_git(source, temp_dir)
            extracted = self._find_domain_root(temp_dir)
        elif zipfile.is_zipfile(source):
            temp_dir = Path(tempfile.mkdtemp())
            with zipfile.ZipFile(source, "r") as zf:
                zf.extractall(temp_dir)
            extracted = self._find_domain_root(temp_dir)
        else:
            source_path = Path(source)
            if not source_path.exists():
                raise DomainMarketplaceError(f"Source not found: {source}")
            extracted = self._find_domain_root(source_path)

        if extracted is None:
            raise DomainMarketplaceError("Could not locate domain.yaml in source")

        domain_data = yaml.safe_load((extracted / "domain.yaml").read_text(encoding="utf-8"))
        domain_id = target_name or domain_data.get("domain", extracted.name)
        target_dir = self.marketplace_dir / domain_id

        if target_dir.exists():
            shutil.rmtree(target_dir)
        shutil.copytree(extracted, target_dir)

        return target_dir

    def import_code_templates(
        self,
        domain_id: str,
        templates: Dict[str, Dict[str, Any]],
    ) -> Path:
        """Import standalone code templates into an existing domain.

        Args:
            domain_id: Target domain identifier.
            templates: Map of template name -> {language, skeleton}.

        Returns:
            Path to the updated domain directory.
        """
        domain_dir = self._find_domain_dir(domain_id)
        if domain_dir is None:
            raise DomainMarketplaceError(f"Domain '{domain_id}' not found")

        domain_yaml = domain_dir / "domain.yaml"
        data = yaml.safe_load(domain_yaml.read_text(encoding="utf-8"))
        existing = data.get("code_templates", {})
        existing.update(templates)
        data["code_templates"] = existing
        domain_yaml.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        return domain_dir

    def _find_domain_dir(self, domain_id: str) -> Optional[Path]:
        """Find the directory containing domain.yaml for a given domain id."""
        for root in (self.builtin_domains_dir, self.marketplace_dir):
            if not root.exists():
                continue
            for domain_yaml in root.rglob("domain.yaml"):
                try:
                    data = yaml.safe_load(domain_yaml.read_text(encoding="utf-8"))
                except Exception:
                    continue
                if data.get("domain") == domain_id:
                    return domain_yaml.parent
        return None

    @staticmethod
    def _find_domain_root(path: Path) -> Optional[Path]:
        """Locate the directory containing domain.yaml under path."""
        if (path / "domain.yaml").exists():
            return path
        for subdir in path.iterdir():
            if subdir.is_dir() and (subdir / "domain.yaml").exists():
                return subdir
        return None

    @staticmethod
    def _clone_git(url: str, target_dir: Path) -> None:
        """Clone a git repository to target_dir."""
        import subprocess

        result = subprocess.run(
            ["git", "clone", "--depth", "1", url, str(target_dir)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise DomainMarketplaceError(f"Git clone failed: {result.stderr}")
