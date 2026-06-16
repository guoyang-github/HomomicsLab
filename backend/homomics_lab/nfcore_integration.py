"""nf-core pipeline integration for HomomicsLab.

Provides discovery, download, caching, and execution of nf-core Nextflow
pipelines. Requires either the ``nf-core`` Python package or a working
``git`` + ``nextflow`` installation for fallback download.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import urllib.request

from homomics_lab.config import settings


@dataclass
class NFCorePipeline:
    """Metadata for an nf-core pipeline."""

    name: str
    description: str
    topics: List[str]
    stars: int
    default_branch: str
    github_url: str
    latest_release: Optional[str] = None


class NFCoreManager:
    """Discover, cache, and run nf-core pipelines."""

    NF_CORE_ORG = "nf-core"
    GITHUB_API = "https://api.github.com"

    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = Path(cache_dir) if cache_dir else (settings.data_dir / "nfcore_pipelines")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._pipelines: Optional[List[NFCorePipeline]] = None

    def list_pipelines(self, use_cache: bool = False) -> List[NFCorePipeline]:
        """Return a list of available nf-core pipelines.

        Args:
            use_cache: If True, only return locally cached pipelines.
        """
        if use_cache:
            return self._list_cached_pipelines()

        if self._pipelines is not None:
            return self._pipelines

        # Prefer nf-core tools if available.
        pipelines = self._list_with_nftools()
        if pipelines is None:
            pipelines = self._list_from_github()

        self._pipelines = pipelines
        return pipelines

    def _list_with_nftools(self) -> Optional[List[NFCorePipeline]]:
        """Use ``nf-core pipelines list`` if installed."""
        if shutil.which("nf-core") is None:
            return None
        try:
            result = subprocess.run(
                ["nf-core", "pipelines", "list", "--json"],
                capture_output=True,
                text=True,
                check=True,
                timeout=60,
            )
            data = json.loads(result.stdout)
            pipelines = []
            for item in data:
                pipelines.append(
                    NFCorePipeline(
                        name=item.get("name", ""),
                        description=item.get("description", ""),
                        topics=item.get("topics", []),
                        stars=item.get("stargazers_count", 0),
                        default_branch=item.get("default_branch", "master"),
                        github_url=item.get("html_url", ""),
                        latest_release=item.get("latest_release", None),
                    )
                )
            return pipelines
        except Exception:
            return None

    def _list_from_github(self) -> List[NFCorePipeline]:
        """Fallback: list repositories from the nf-core GitHub organization."""
        url = f"{self.GITHUB_API}/orgs/{self.NF_CORE_ORG}/repos?per_page=100"
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                repos = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise RuntimeError(f"Failed to fetch nf-core pipeline list: {exc}") from exc

        pipelines = []
        for repo in repos:
            if repo.get("archived") or repo.get("disabled"):
                continue
            name = repo.get("name", "")
            if not name.startswith("nfcore-") and not name.startswith("nf-core-"):
                continue
            pipelines.append(
                NFCorePipeline(
                    name=name,
                    description=repo.get("description", ""),
                    topics=repo.get("topics", []),
                    stars=repo.get("stargazers_count", 0),
                    default_branch=repo.get("default_branch", "master"),
                    github_url=repo.get("html_url", ""),
                    latest_release=repo.get("default_branch", "master"),
                )
            )
        return pipelines

    def _list_cached_pipelines(self) -> List[NFCorePipeline]:
        """List pipelines already downloaded to the local cache."""
        pipelines = []
        for path in self.cache_dir.iterdir():
            if path.is_dir() and (path / "main.nf").exists():
                pipelines.append(
                    NFCorePipeline(
                        name=path.name,
                        description="Cached locally",
                        topics=[],
                        stars=0,
                        default_branch="master",
                        github_url=f"https://github.com/{self.NF_CORE_ORG}/{path.name}",
                    )
                )
        return pipelines

    def download_pipeline(self, name: str, version: Optional[str] = None) -> Path:
        """Download/cache an nf-core pipeline to the local cache directory.

        Args:
            name: Pipeline name (e.g., ``rnaseq`` or ``nf-core-rnaseq``).
            version: Git tag/branch to checkout. Defaults to latest release or master.

        Returns:
            Path to the cached pipeline directory.
        """
        repo_name = self._normalize_name(name)
        target = self.cache_dir / repo_name

        if target.exists():
            shutil.rmtree(target)

        version = version or self._get_default_version(repo_name)

        if shutil.which("nf-core") is not None:
            try:
                subprocess.run(
                    [
                        "nf-core",
                        "pipelines",
                        "download",
                        repo_name,
                        "--revision",
                        version,
                        "--outdir",
                        str(target),
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                return target
            except Exception:
                pass  # Fall back to git.

        if shutil.which("git") is None:
            raise RuntimeError("Neither nf-core tools nor git is available to download pipelines.")

        url = f"https://github.com/{self.NF_CORE_ORG}/{repo_name}.git"
        subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", version, url, str(target)],
            check=True,
            capture_output=True,
            text=True,
            timeout=300,
        )
        return target

    def get_pipeline_path(self, name: str, version: Optional[str] = None) -> Path:
        """Return the path to a cached pipeline, downloading it if necessary."""
        repo_name = self._normalize_name(name)
        target = self.cache_dir / repo_name
        if not target.exists() or not (target / "main.nf").exists():
            target = self.download_pipeline(name, version)
        return target

    def run_pipeline(
        self,
        name: str,
        params: Dict[str, Any],
        version: Optional[str] = None,
        profiles: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Run a cached nf-core pipeline with Nextflow.

        This is a thin wrapper; the caller is responsible for providing a
        Nextflow runner or scheduling the pipeline via the existing HPC layer.
        """
        pipeline_dir = self.get_pipeline_path(name, version)
        return {
            "pipeline": name,
            "version": version,
            "pipeline_dir": str(pipeline_dir),
            "params": params,
            "profiles": profiles or [],
            "nextflow_cmd": self._build_nextflow_cmd(pipeline_dir, params, profiles),
        }

    def _build_nextflow_cmd(
        self,
        pipeline_dir: Path,
        params: Dict[str, Any],
        profiles: Optional[List[str]] = None,
    ) -> str:
        parts = ["nextflow", "run", str(pipeline_dir)]
        if profiles:
            parts.extend(["-profile", ",".join(profiles)])
        for key, value in params.items():
            if isinstance(value, bool):
                if value:
                    parts.append(f"--{key}")
            else:
                parts.append(f"--{key} {value}")
        return " ".join(parts)

    def _normalize_name(self, name: str) -> str:
        """Normalize pipeline name to ``nf-core-<name>``."""
        name = name.strip().lower()
        if name.startswith("nfcore-"):
            return name.replace("nfcore-", "nf-core-")
        if not name.startswith("nf-core-"):
            return f"nf-core-{name}"
        return name

    def _get_default_version(self, repo_name: str) -> str:
        """Try to determine the latest release tag; fall back to master."""
        try:
            url = f"{self.GITHUB_API}/repos/{self.NF_CORE_ORG}/{repo_name}/releases/latest"
            with urllib.request.urlopen(url, timeout=15) as response:
                data = json.loads(response.read().decode("utf-8"))
                return data.get("tag_name", "master")
        except Exception:
            return "master"

    def list_releases(self, name: str) -> List[str]:
        """Return available git tags/releases for a pipeline.

        Uses GitHub releases API; falls back to git ls-remote if available.
        """
        repo_name = self._normalize_name(name)
        releases = []

        # Try GitHub releases API first.
        try:
            url = f"{self.GITHUB_API}/repos/{self.NF_CORE_ORG}/{repo_name}/releases?per_page=100"
            with urllib.request.urlopen(url, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
            releases = [r.get("tag_name") for r in data if r.get("tag_name")]
            if releases:
                return releases
        except Exception:
            pass

        # Fallback: git ls-remote.
        if shutil.which("git") is not None:
            try:
                url = f"https://github.com/{self.NF_CORE_ORG}/{repo_name}.git"
                result = subprocess.run(
                    ["git", "ls-remote", "--tags", url],
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=True,
                )
                for line in result.stdout.splitlines():
                    parts = line.split()
                    if len(parts) >= 2:
                        ref = parts[1]
                        if ref.startswith("refs/tags/"):
                            tag = ref.replace("refs/tags/", "").rstrip("^{}")
                            if tag not in releases:
                                releases.append(tag)
                releases.sort(reverse=True)
            except Exception:
                pass

        if not releases:
            raise RuntimeError(f"Could not list releases for {repo_name}")
        return releases

    def get_default_version(self, name: str) -> str:
        """Return the latest release tag or the default branch."""
        try:
            return self.list_releases(name)[0]
        except Exception:
            return self._get_default_version(self._normalize_name(name))

    def load_schema(self, name: str, version: Optional[str] = None) -> Dict[str, Any]:
        """Load ``nextflow_schema.json`` for a cached pipeline."""
        from homomics_lab.nfcore_schema import load_schema

        pipeline_dir = self.get_pipeline_path(name, version)
        return load_schema(pipeline_dir)

    def detect_profiles(self) -> Tuple[List[str], List[str]]:
        """Detect available execution profiles and return (available, recommended).

        Checks for docker, singularity, conda, mamba in order of preference.
        """
        available = []
        if shutil.which("docker") is not None:
            available.append("docker")
        if shutil.which("singularity") is not None or shutil.which("apptainer") is not None:
            available.append("singularity")
        if shutil.which("conda") is not None:
            available.append("conda")
        if shutil.which("mamba") is not None:
            available.append("mamba")

        # Recommended order: container > conda.
        recommended = []
        for p in ["docker", "singularity"]:
            if p in available:
                recommended.append(p)
                break
        if not recommended and "mamba" in available:
            recommended.append("mamba")
        elif not recommended and "conda" in available:
            recommended.append("conda")

        return available, recommended

    def suggest_pipeline(self, intent_analysis_type: str) -> Optional[str]:
        """Suggest an nf-core pipeline name for a domain intent."""
        mapping = {
            "rnaseq_analysis": "nf-core-rnaseq",
            "rna_seq": "nf-core-rnaseq",
            "single_cell_analysis": "nf-core-scrnaseq",
            "scrnaseq": "nf-core-scrnaseq",
            "atacseq_analysis": "nf-core-atacseq",
            "chipseq_analysis": "nf-core-chipseq",
            "methylation_analysis": "nf-core-methylseq",
            "metagenomics_analysis": "nf-core-mag",
            "proteomics_analysis": "nf-core-proteomicslfq",
            "spatial_analysis": "nf-core-spatialtranscriptomics",
        }
        return mapping.get(intent_analysis_type)


# Singleton.
_nfcore_manager: Optional[NFCoreManager] = None


def get_nfcore_manager() -> NFCoreManager:
    global _nfcore_manager
    if _nfcore_manager is None:
        _nfcore_manager = NFCoreManager()
    return _nfcore_manager
