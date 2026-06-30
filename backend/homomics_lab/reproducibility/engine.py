"""ReproducibilityEngine — builds and manages ReproducibilityBundles."""

import platform
import subprocess
import sys
from typing import Any, Dict, Optional

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
