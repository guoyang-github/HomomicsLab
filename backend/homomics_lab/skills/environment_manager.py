"""Manage per-skill execution environments.

Creates isolated Python virtualenvs and R project libraries, reads dependency
files, and installs missing packages when configured to do so.
"""

import hashlib
import json
import logging
import shutil
import subprocess
import sys
import venv
from pathlib import Path
from typing import Any, Dict, List, Optional

from homomics_lab.config import settings

logger = logging.getLogger(__name__)


class EnvironmentInfo:
    """Information about a prepared execution environment."""

    def __init__(
        self,
        language: str,
        python_path: Optional[str] = None,
        r_executable: Optional[str] = None,
        r_library_path: Optional[str] = None,
        dependency_files: Optional[List[str]] = None,
        installed_packages: Optional[Dict[str, str]] = None,
    ):
        self.language = language
        self.python_path = python_path
        self.r_executable = r_executable
        self.r_library_path = r_library_path
        self.dependency_files = dependency_files or []
        self.installed_packages = installed_packages or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "language": self.language,
            "python_path": self.python_path,
            "r_executable": self.r_executable,
            "r_library_path": self.r_library_path,
            "dependency_files": self.dependency_files,
            "installed_packages": self.installed_packages,
        }


class EnvironmentManager:
    """Prepare and cache isolated environments for skills."""

    def __init__(self, base_dir: Optional[Path] = None, auto_install: Optional[bool] = None):
        self.base_dir = (base_dir or settings.data_dir / "environments").resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.auto_install = auto_install if auto_install is not None else settings.auto_install_dependencies

    def _env_hash(self, skill_id: str, dependency_file: Optional[Path]) -> str:
        """Stable hash used as the environment cache key."""
        hasher = hashlib.sha256(skill_id.encode())
        if dependency_file and dependency_file.exists():
            hasher.update(dependency_file.read_bytes())
        return hasher.hexdigest()[:16]

    def prepare_python(
        self,
        skill_id: str,
        scripts_dir: Path,
    ) -> EnvironmentInfo:
        """Return a Python environment for the skill, creating a venv or conda env if needed."""
        skill_dir = scripts_dir.parent.parent
        req_file = scripts_dir / "requirements.txt"
        if not req_file.exists():
            req_file = skill_dir / "requirements.txt"
        env_yml = scripts_dir / "environment.yml"
        if not env_yml.exists():
            env_yml = skill_dir / "environment.yml"

        # Local sandbox reuses the host project venv; skip isolated venv creation
        # unless the skill explicitly declares a conda environment.
        if settings.skill_sandbox_backend == "local" and not (
            env_yml.exists() and self._conda_available()
        ):
            dependency_files = []
            for candidate in (req_file, env_yml):
                if candidate.exists() and str(candidate) not in dependency_files:
                    dependency_files.append(str(candidate))
            return EnvironmentInfo(
                language="python",
                python_path=sys.executable,
                dependency_files=dependency_files,
                installed_packages={},
            )

        if env_yml.exists() and self._conda_available():
            return self._prepare_conda(skill_id, env_yml)

        dependency_file = req_file if req_file.exists() else None
        env_hash = self._env_hash(skill_id, dependency_file)
        env_dir = self.base_dir / "python" / skill_id / env_hash
        venv_dir = env_dir / "venv"
        python_path = str(venv_dir / ("Scripts" if sys.platform == "win32" else "bin") / "python")
        info = EnvironmentInfo(
            language="python",
            python_path=python_path,
            dependency_files=[str(dependency_file)] if dependency_file else [],
        )

        if venv_dir.exists():
            # Refresh installed package manifest.
            info.installed_packages = self._list_venv_packages(venv_dir)
            return info

        logger.info("Creating Python venv for skill %s at %s", skill_id, venv_dir)
        venv.create(venv_dir, with_pip=True)

        installed: Dict[str, str] = {}
        if req_file.exists():
            if self.auto_install:
                logger.info("Installing Python requirements for %s", skill_id)
                installed = self._install_requirements(venv_dir, req_file)
            else:
                logger.warning("auto_install disabled; requirements not installed for %s", skill_id)
        elif env_yml.exists():
            logger.warning(
                "environment.yml detected for %s but conda/mamba is not available and requirements.txt is missing",
                skill_id,
            )

        info.installed_packages = installed
        return info

    @staticmethod
    def _conda_available() -> bool:
        """Return True if conda or mamba is available on PATH."""
        for binary in ("mamba", "conda"):
            if shutil.which(binary):
                return True
        return False

    def _prepare_conda(
        self,
        skill_id: str,
        env_yml: Path,
    ) -> EnvironmentInfo:
        """Create or reuse a conda environment from an environment.yml file."""
        binary = "mamba" if shutil.which("mamba") else "conda"
        env_hash = self._env_hash(skill_id, env_yml)
        env_path = self.base_dir / "conda" / skill_id / env_hash
        python_path = str(env_path / ("python.exe" if sys.platform == "win32" else Path("bin") / "python"))
        info = EnvironmentInfo(
            language="python",
            python_path=python_path,
            dependency_files=[str(env_yml)],
        )

        if env_path.exists():
            info.installed_packages = self._list_conda_packages(env_path)
            return info

        if not self.auto_install:
            logger.warning("auto_install disabled; conda env not created for %s", skill_id)
            return info

        logger.info("Creating conda env for skill %s at %s", skill_id, env_path)
        try:
            subprocess.run(
                [binary, "env", "create", "-f", str(env_yml), "-p", str(env_path), "--yes"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=600,
            )
            info.installed_packages = self._list_conda_packages(env_path)
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.decode(errors="replace") if exc.stderr else ""
            raise RuntimeError(f"Failed to create conda env from {env_yml}: {stderr}") from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"Timeout creating conda env from {env_yml}") from exc

        return info

    def _list_conda_packages(self, env_path: Path) -> Dict[str, str]:
        """List packages installed in a conda prefix."""
        binary = "mamba" if shutil.which("mamba") else "conda"
        try:
            result = subprocess.run(
                [binary, "list", "-p", str(env_path), "--json"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=60,
            )
            data = json.loads(result.stdout)
            return {entry.get("name", "unknown"): entry.get("version", "") for entry in data}
        except Exception as exc:
            logger.warning("Could not list conda packages: %s", exc)
            return {}

    def _install_requirements(self, venv_dir: Path, req_file: Path) -> Dict[str, str]:
        """Install a requirements.txt into a venv and return installed packages."""
        pip = venv_dir / ("Scripts" if sys.platform == "win32" else "bin") / "pip"
        try:
            subprocess.run(
                [str(pip), "install", "--no-input", "-r", str(req_file)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=300,
            )
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.decode(errors="replace") if exc.stderr else ""
            raise RuntimeError(f"Failed to install requirements from {req_file}: {stderr}") from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"Timeout installing requirements from {req_file}") from exc
        return self._list_venv_packages(venv_dir)

    def _list_venv_packages(self, venv_dir: Path) -> Dict[str, str]:
        """List packages installed in a venv."""
        pip = venv_dir / ("Scripts" if sys.platform == "win32" else "bin") / "pip"
        try:
            result = subprocess.run(
                [str(pip), "list", "--format=json"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=30,
            )
            data = json.loads(result.stdout)
            return {entry["name"]: entry["version"] for entry in data}
        except Exception as exc:
            logger.warning("Could not list venv packages: %s", exc)
            return {}

    def prepare_r(
        self,
        skill_id: str,
        scripts_dir: Path,
    ) -> EnvironmentInfo:
        """Return an R environment for the skill, installing missing packages if allowed."""
        dep_file = scripts_dir / "dependencies.R"
        dependency_files = [str(dep_file)] if dep_file.exists() else []
        library_path = self.base_dir / "r" / skill_id / "library"
        library_path.mkdir(parents=True, exist_ok=True)

        info = EnvironmentInfo(
            language="r",
            r_executable="Rscript",
            r_library_path=str(library_path),
            dependency_files=dependency_files,
        )

        if dep_file.exists() and self.auto_install:
            packages = self._parse_r_dependencies(dep_file)
            installed = self._install_r_packages(packages, library_path)
            info.installed_packages = installed

        return info

    @staticmethod
    def _parse_r_dependencies(dep_file: Path) -> List[str]:
        """Parse library()/require() calls and plain package names from dependencies.R."""
        packages: List[str] = []
        text = dep_file.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            line = line.split("#")[0].strip()
            if not line:
                continue
            # library("pkg") or require("pkg")
            for keyword in ("library(", "require("):
                if keyword in line:
                    inner = line.split(keyword, 1)[1].split(")")[0]
                    inner = inner.replace('"', "").replace("'", "").strip()
                    if inner:
                        packages.append(inner)
            # Also allow plain package names, one per line
            if line and not any(c in line for c in "()=,;"):
                packages.append(line)
        return packages

    def _install_r_packages(self, packages: List[str], library_path: Path) -> Dict[str, str]:
        """Install missing R packages into a project library."""
        installed: Dict[str, str] = {}
        if not packages:
            return installed

        missing = []
        for pkg in packages:
            check = subprocess.run(
                ["Rscript", "-e", f"cat(requireNamespace('{pkg}', quietly=TRUE))"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=30,
            )
            if check.returncode != 0 or "TRUE" not in check.stdout.decode():
                missing.append(pkg)

        if missing and self.auto_install:
            logger.info("Installing R packages for project library: %s", ", ".join(missing))
            pkg_list = ", ".join(f'"{p}"' for p in missing)
            install_script = f"""
            if (!requireNamespace('pak', quietly = TRUE)) {{
              install.packages('pak', repos = 'https://r-lib.r-universe.dev')
            }}
            dir.create('{library_path}', recursive = TRUE, showWarnings = FALSE)
            pak::pkg_install(c({pkg_list}), lib = '{library_path}', ask = FALSE)
            cat('OK')
            """
            try:
                subprocess.run(
                    ["Rscript", "-e", install_script],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=600,
                )
            except subprocess.CalledProcessError as exc:
                stderr = exc.stderr.decode(errors="replace") if exc.stderr else ""
                raise RuntimeError(f"Failed to install R packages {missing}: {stderr}") from exc
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError(f"Timeout installing R packages {missing}") from exc

        # Record version strings for installed packages
        for pkg in packages:
            try:
                result = subprocess.run(
                    ["Rscript", "-e", f"cat(as.character(packageVersion('{pkg}')))"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=30,
                )
                if result.returncode == 0:
                    installed[pkg] = result.stdout.decode().strip()
            except Exception:
                pass
        return installed

    def prepare(
        self,
        skill_id: str,
        scripts_dir: Path,
        exec_type: str,
    ) -> EnvironmentInfo:
        """Prepare the environment for a skill based on its runtime type."""
        exec_type = exec_type.lower()
        if exec_type == "r":
            return self.prepare_r(skill_id, scripts_dir)
        return self.prepare_python(skill_id, scripts_dir)
