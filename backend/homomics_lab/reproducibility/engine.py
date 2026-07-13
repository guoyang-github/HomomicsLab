"""ReproducibilityEngine — builds and manages ReproducibilityBundles."""

import json
import platform
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any, Dict, Optional

from homomics_lab.provenance.env_snapshot import store_env_snapshot
from homomics_lab.reproducibility.bundle import (
    CodeSnippet,
    EnvironmentLock,
    ExecutionSnapshot,
    HITLDecisionRecord,
    ReproducibilityBundle,
    SkillVersionLock,
)
from homomics_lab.workspace.manager import WorkspaceManager


class ReproducibilityEngine:
    """Tracks analysis execution and builds reproducibility bundles.

    Usage:
        engine = ReproducibilityEngine(workspace)
        engine.start_analysis(project_id="proj_1", random_seed=42)

        # During execution:
        engine.record_plan(task_tree, plan_context)
        engine.record_code(phase, agent_code)
        engine.record_hitl_decision(checkpoint, choice)

        # At completion:
        bundle = engine.finalize()
        bundle.save(path)
    """

    def __init__(self, workspace: WorkspaceManager):
        self.workspace = workspace
        self._bundle: Optional[ReproducibilityBundle] = None

    def start_analysis(self, project_id: str, random_seed: int = 42) -> None:
        """Start tracking a new analysis."""
        self._bundle = ReproducibilityBundle(
            project_id=project_id,
            random_seed=random_seed,
            environment_lock=self._capture_environment(),
        )

    def record_plan(
        self,
        task_tree: Dict[str, Any],
        plan_context: Dict[str, Any],
        plan_id: Optional[str] = None,
        plan_result: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record the generated execution plan."""
        if self._bundle is None:
            raise RuntimeError("Analysis not started. Call start_analysis() first.")

        self._bundle.execution_snapshot = ExecutionSnapshot(
            task_tree=task_tree,
            plan_version=plan_context.get("plan_engine_version", "unknown"),
            plan_prompt=plan_context.get("prompt", ""),
            plan_llm_model=plan_context.get("llm_model", ""),
            plan_id=plan_id,
            plan_result=plan_result,
        )

    def record_code(
        self,
        phase: str,
        code: str,
        language: str = "python",
    ) -> None:
        """Record agent-generated code.

        This is the key to reproducibility: the exact code executed is preserved.
        """
        if self._bundle is None:
            raise RuntimeError("Analysis not started. Call start_analysis() first.")

        import uuid

        self._bundle.agent_code_archive.append(
            CodeSnippet(
                snippet_id=str(uuid.uuid4()),
                phase=phase,
                code=code,
                language=language,
            )
        )

    def record_skill_versions(self, skill_versions: Dict[str, str]) -> None:
        """Record the versions of all skills used."""
        if self._bundle is None:
            raise RuntimeError("Analysis not started. Call start_analysis() first.")

        self._bundle.skill_versions = SkillVersionLock(
            locked_skills=skill_versions,
        )

    def record_hitl_decision(
        self,
        checkpoint_id: str,
        choice: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a human-in-the-loop decision.

        HITL choices are part of the analysis and must be recorded for replay.
        """
        if self._bundle is None:
            raise RuntimeError("Analysis not started. Call start_analysis() first.")

        self._bundle.hitl_decisions.append(
            HITLDecisionRecord(
                checkpoint_id=checkpoint_id,
                choice=choice,
                parameters=parameters or {},
            )
        )

    def finalize(
        self,
        cbkb=None,
        job_id: Optional[str] = None,
    ) -> ReproducibilityBundle:
        """Finalize the bundle and save it to the workspace.

        Args:
            cbkb: Optional CBKB instance to auto-index the bundle into the
                Computational Biology Knowledge Base.
            job_id: Optional job identifier used to scope the bundle filename.
        """
        if self._bundle is None:
            raise RuntimeError("Analysis not started. Call start_analysis() first.")

        bundle = self._bundle

        # Capture environment snapshot hash and store the env file.
        metadata_dir = self.workspace.get_path(".metadata")
        bundle.env_snapshot_hash = store_env_snapshot(metadata_dir)

        # Capture latest git snapshot reference.
        try:
            git_snapshots = self.workspace.list_git_snapshots()
            if git_snapshots:
                bundle.git_snapshot = git_snapshots[0]
        except Exception:
            pass

        # Include provenance and runs JSONL files when present.
        metadata_dir = self.workspace.get_path(".metadata")
        for name in ("provenance.jsonl", "runs.jsonl"):
            file_path = metadata_dir / name
            if file_path.exists():
                try:
                    bundle.provenance_files[name] = file_path.read_text(encoding="utf-8")
                except Exception:
                    pass

        # Include version.lock if present.
        version_lock_path = metadata_dir / "version.lock"
        if version_lock_path.exists():
            try:
                bundle.version_lock = json.loads(
                    version_lock_path.read_text(encoding="utf-8")
                )
            except Exception:
                pass

        # Save to workspace. When a job_id is provided, use a job-scoped filename
        # so multiple jobs in the same project do not overwrite each other.
        if job_id:
            filename = f".metadata/reproducibility_bundle_{job_id}.json"
        else:
            filename = ".metadata/reproducibility_bundle.json"
        bundle_path = self.workspace.get_path(filename)
        bundle.save(bundle_path)

        # Auto-index into CBKB if available
        if cbkb is not None:
            self._index_into_cbkb(bundle, cbkb)

        return bundle

    def export_zip(
        self,
        output_path: Path,
        cbkb=None,
        job_id: Optional[str] = None,
    ) -> Path:
        """Export the finalized bundle and supporting files as a zip archive.

        Args:
            output_path: Destination zip file path.
            cbkb: Optional CBKB instance passed to ``finalize``.
            job_id: Optional job identifier used to locate the bundle.

        Returns:
            The path to the created zip archive.
        """
        bundle = self.finalize(cbkb=cbkb, job_id=job_id)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        metadata_dir = self.workspace.get_path(".metadata")

        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # Bundle JSON
            bundle_bytes = bundle.to_json().encode("utf-8")
            zf.writestr("reproducibility_bundle.json", bundle_bytes)

            # Provenance and runs JSONL
            for name in ("provenance.jsonl", "runs.jsonl"):
                file_path = metadata_dir / name
                if file_path.exists():
                    zf.write(file_path, arcname=name)

            # Environment snapshot
            if bundle.env_snapshot_hash:
                env_file = metadata_dir / "env" / f"{bundle.env_snapshot_hash}.json"
                if env_file.exists():
                    zf.write(env_file, arcname=f"env/{bundle.env_snapshot_hash}.json")

            # version.lock
            version_lock_path = metadata_dir / "version.lock"
            if version_lock_path.exists():
                zf.write(version_lock_path, arcname="version.lock")

            # Git snapshot metadata
            if bundle.git_snapshot:
                zf.writestr(
                    "git_snapshot.json",
                    json.dumps(bundle.git_snapshot, ensure_ascii=False, indent=2).encode("utf-8"),
                )

        return output_path

    def _index_into_cbkb(self, bundle, cbkb) -> None:
        """Extract knowledge from bundle and inject into CBKB."""
        from homomics_lab.knowledge.cbkb import ExperimentNode, ParameterLoreEntry
        import uuid

        skills = list(bundle.skill_versions.locked_skills.keys()) if bundle.skill_versions else []
        phases = []
        if bundle.execution_snapshot and bundle.execution_snapshot.task_tree:
            phases = list(bundle.execution_snapshot.task_tree.keys())

        import hashlib
        bundle_id = hashlib.sha256(bundle.to_json().encode()).hexdigest()[:16]
        node = ExperimentNode(
            bundle_id=bundle_id,
            project_id=bundle.project_id,
            created_at=bundle.created_at,
            skills_used=skills,
            phases=phases,
            summary=f"Analysis with {len(skills)} skills, random_seed={bundle.random_seed}",
        )
        cbkb.add_experiment_node(node)

        # Extract parameter lore from HITL decisions
        for decision in bundle.hitl_decisions:
            for param_name, param_value in (decision.parameters or {}).items():
                cbkb.add_parameter_lore(
                    ParameterLoreEntry(
                        id=str(uuid.uuid4()),
                        skill_id="hitl",
                        param_name=param_name,
                        param_value=str(param_value),
                        outcome_metric="human_choice",
                        outcome_value=1.0,
                        project_id=bundle.project_id,
                        context=f"checkpoint={decision.checkpoint_id}, choice={decision.choice}",
                        created_at=bundle.created_at,
                    )
                )

    @staticmethod
    def _capture_environment() -> EnvironmentLock:
        """Capture the current execution environment."""
        # Try pip freeze
        try:
            pip_freeze = subprocess.run(
                [sys.executable, "-m", "pip", "freeze"],
                capture_output=True,
                text=True,
                timeout=30,
            ).stdout
        except Exception:
            pip_freeze = ""

        # Try conda env export
        conda_export = ""
        try:
            conda_export = subprocess.run(
                ["conda", "env", "export"],
                capture_output=True,
                text=True,
                timeout=30,
            ).stdout
        except Exception:
            pass

        return EnvironmentLock(
            python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            pip_freeze=pip_freeze,
            conda_env_export=conda_export,
            system_info={
                "platform": platform.platform(),
                "machine": platform.machine(),
                "processor": platform.processor(),
            },
        )
