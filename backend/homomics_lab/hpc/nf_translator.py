"""Translate a PlanResult into a DSL2 Nextflow workflow."""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from homomics_lab.agent.plan.models import Phase, PlanResult
from homomics_lab.config import settings
from homomics_lab.skills.models import SkillDefinition


class SimpleNFTranslator:
    """Generate a linear DSL2 Nextflow script from a PlanResult.

    Each required phase becomes a process. Processes are wired sequentially via
    channels. When a phase has a selected skill with a script entrypoint, the
    generated process stages the script and its inputs and executes it. Otherwise
    a placeholder process is emitted so the workflow can still be validated.
    """

    def __init__(self, working_dir: Path = None):
        self.working_dir = working_dir or Path.cwd()
        self.working_dir.mkdir(parents=True, exist_ok=True)

    def translate(
        self,
        plan: PlanResult,
        inputs: Dict[str, Any],
        output_path: Path = None,
    ) -> Path:
        """Translate a plan into a Nextflow DSL2 script.

        Args:
            plan: The analysis plan.
            inputs: User inputs passed to the workflow and to each phase.
            output_path: Optional destination for the generated script.

        Returns:
            Path to the generated main.nf file.
        """
        phases = [p for p in plan.phases if p.required]
        if not phases:
            phases = plan.phases

        if output_path is None:
            output_path = self.working_dir / "main.nf"

        # Prepare per-phase scripts and inputs before emitting the workflow.
        phase_dirs = self._prepare_phase_directories(phases, inputs)

        lines: List[str] = [
            "#!/usr/bin/env nextflow",
            "",
            "nextflow.enable.dsl = 2",
            "",
        ]

        lines.extend(self._emit_params(inputs))
        lines.append("")

        for idx, phase in enumerate(phases):
            phase_dir = phase_dirs[idx]
            lines.extend(self._emit_process(phase, idx, phase_dir))
            lines.append("")

        lines.extend(self._emit_workflow(phases, phase_dirs, inputs))
        lines.append("")

        output_path.write_text("\n".join(lines), encoding="utf-8")
        return output_path

    def _prepare_phase_directories(
        self,
        phases: List[Phase],
        inputs: Dict[str, Any],
    ) -> List[Path]:
        """Write a script + inputs.json for each phase and return their dirs."""
        phase_dirs: List[Path] = []
        for idx, phase in enumerate(phases):
            phase_dir = self.working_dir / f"phase_{idx}_{self._sanitize_process_name(phase.phase_type)}"
            phase_dir.mkdir(parents=True, exist_ok=True)
            phase_dirs.append(phase_dir)

            skill = self._get_skill(phase)
            phase_inputs = dict(inputs)
            phase_inputs.update(phase.parameters or {})
            phase_inputs["_phase"] = phase.phase_type
            phase_inputs["_phase_index"] = idx
            (phase_dir / "inputs.json").write_text(
                json.dumps(phase_inputs, indent=2, default=str), encoding="utf-8"
            )

            script_path, exec_type = self._write_phase_script(phase, skill, phase_dir)
            if script_path is not None:
                (phase_dir / ".exec_type").write_text(exec_type, encoding="utf-8")

        return phase_dirs

    def _write_phase_script(
        self,
        phase: Phase,
        skill: Optional[SkillDefinition],
        phase_dir: Path,
    ) -> tuple[Optional[Path], str]:
        """Write the executable script for a phase.

        Returns:
            Tuple of (script_path, exec_type) or (None, "") when no entrypoint
            could be resolved.
        """
        if skill is None or skill.source_dir is None or not skill.has_entrypoint:
            return None, ""

        entrypoint = self._resolve_entrypoint_path(skill)
        if entrypoint is None:
            return None, ""

        code = entrypoint.read_text(encoding="utf-8")
        exec_type = "python" if entrypoint.suffix.lower() == ".py" else "r"

        if exec_type == "python":
            script_path = phase_dir / "script.py"
            wrapper = (
                "import json, sys\n"
                "__inputs__ = json.load(open('inputs.json', encoding='utf-8'))\n"
                "\n"
                f"{code}\n"
                "\n"
                "if __name__ == '__main__':\n"
                "    if 'main' in dir() and callable(main):\n"
                "        result = main(__inputs__)\n"
                "    else:\n"
                "        result = {'phase': __inputs__.get('_phase'), 'status': 'ok'}\n"
                "    with open('result.json', 'w', encoding='utf-8') as f:\n"
                "        json.dump(result, f, indent=2, default=str)\n"
            )
            script_path.write_text(wrapper, encoding="utf-8")
            return script_path, exec_type

        # R support: inject inputs as a JSON file and call a main() if defined.
        script_path = phase_dir / "script.R"
        wrapper = (
            f"# Phase: {phase.phase_type}\n"
            "inputs <- jsonlite::fromJSON('inputs.json')\n"
            "\n"
            f"{code}\n"
            "\n"
            "if (exists('main') && is.function(main)) {\n"
            "    result <- main(inputs)\n"
            "} else {\n"
            "    result <- list(phase = inputs[['_phase']], status = 'ok')\n"
            "}\n"
            "jsonlite::write_json(result, 'result.json', auto_unbox = TRUE)\n"
        )
        script_path.write_text(wrapper, encoding="utf-8")
        return script_path, exec_type

    @staticmethod
    def _resolve_entrypoint_path(skill: SkillDefinition) -> Optional[Path]:
        """Resolve the single executable script for a skill."""
        source_dir = skill.source_dir
        if source_dir is None:
            return None

        entrypoint = skill.metadata.get("entrypoint")
        if isinstance(entrypoint, (str, Path)):
            candidate = source_dir / entrypoint
            if candidate.is_file():
                return candidate

        for candidate in (
            source_dir / "scripts" / "run.py",
            source_dir / "scripts" / "python" / "run.py",
            source_dir / "scripts" / "r" / "run.R",
        ):
            if candidate.is_file():
                return candidate

        return None

    @staticmethod
    def _sanitize_process_name(skill_id: str) -> str:
        """Make a valid Nextflow process name from a skill id."""
        name = re.sub(r"[^a-zA-Z0-9_]", "_", skill_id)
        if name[0].isdigit():
            name = "_" + name
        return name

    def _emit_params(self, inputs: Dict[str, Any]) -> List[str]:
        """Emit Nextflow params for top-level inputs."""
        lines: List[str] = []
        for key, value in inputs.items():
            if isinstance(value, bool):
                lines.append(f"params.{key} = {str(value).lower()}")
            elif isinstance(value, str):
                escaped = value.replace('"', '\\"')
                lines.append(f'params.{key} = "{escaped}"')
            elif isinstance(value, (list, tuple)):
                lines.append(f"params.{key} = {json.dumps(value)}")
            elif isinstance(value, dict):
                # Groovy map syntax: [k: v, ...]
                items = ", ".join(
                    f"{k}: {json.dumps(v)}" for k, v in value.items()
                )
                lines.append(f"params.{key} = [{items}]")
            else:
                lines.append(f"params.{key} = {value}")
        return lines

    def _emit_process(self, phase: Phase, idx: int, phase_dir: Path) -> List[str]:
        """Emit a single Nextflow process for a phase."""
        skill = self._get_skill(phase)
        process_name = self._sanitize_process_name(
            skill.id if skill is not None else phase.phase_type
        )

        lines = [f"process {process_name} {{"]

        # Resource directives derived from skill metadata when available.
        if skill is not None:
            resources = skill.runtime.resources
            container = self._container_for_skill(skill)
            if container:
                lines.append(f'    container "{container}"')
            lines.append(f"    memory '{resources.memory}'")
            lines.append(f"    cpus {resources.cpu}")
            lines.append(f"    time '{resources.time}'")

        lines.extend([
            "    input:",
            "        val phase_input",
        ])

        script_path = phase_dir / "script.py"
        r_script_path = phase_dir / "script.R"
        if script_path.exists():
            lines.extend([
                "        path 'script.py'",
                "        path 'inputs.json'",
            ])
            exec_type = "python"
        elif r_script_path.exists():
            lines.extend([
                "        path 'script.R'",
                "        path 'inputs.json'",
            ])
            exec_type = "r"
        else:
            exec_type = "placeholder"

        lines.extend([
            "    output:",
            "        path 'result.json'",
            "    script:",
            '    """',
        ])

        if exec_type == "python":
            lines.extend([
                "    python script.py",
            ])
        elif exec_type == "r":
            lines.extend([
                "    Rscript script.R",
            ])
        else:
            lines.extend([
                f"    echo 'Placeholder process for phase: {phase.phase_type}'",
                "    python << 'PYEOF'",
                "    import json",
                f"    result = {{'phase': '{phase.phase_type}', 'status': 'ok'}}",
                "    with open('result.json', 'w') as f:",
                "        json.dump(result, f)",
                "    PYEOF",
            ])

        lines.extend([
            '    """',
            "}",
        ])
        return lines

    def _container_for_skill(self, skill: SkillDefinition) -> Optional[str]:
        """Return a suitable container image for a skill runtime."""
        explicit = skill.metadata.get("container")
        if isinstance(explicit, str) and explicit:
            return explicit

        if skill.runtime.type.lower() == "r":
            return getattr(settings, "default_r_container", "r-base:4.3.0")
        return getattr(settings, "default_python_container", "python:3.10-slim")

    def _emit_workflow(
        self,
        phases: List[Phase],
        phase_dirs: List[Path],
        inputs: Dict[str, Any],
    ) -> List[str]:
        """Emit the DSL2 workflow wiring processes sequentially."""
        lines = ["workflow {"]

        if not phases:
            lines.append("}")
            return lines

        lines.append("    inputs_ch = Channel.value(params.subMap([" +
                     ", ".join(f"'{k}'" for k in inputs.keys()) + "]))")

        prev_var = "inputs_ch"
        for idx, phase in enumerate(phases):
            skill = self._get_skill(phase)
            process_name = self._sanitize_process_name(
                skill.id if skill is not None else phase.phase_type
            )
            phase_dir = phase_dirs[idx]
            script_file = self._first_existing(phase_dir / "script.py", phase_dir / "script.R")
            if script_file is not None:
                rel_script = script_file.relative_to(self.working_dir).as_posix()
                rel_inputs = (phase_dir / "inputs.json").relative_to(self.working_dir).as_posix()
                script_arg = f", Channel.value(file('{rel_script}'))"
                inputs_arg = f", Channel.value(file('{rel_inputs}'))"
            else:
                script_arg = ""
                inputs_arg = ""

            if idx == 0:
                lines.append(
                    f"    {process_name}({prev_var}{script_arg}{inputs_arg})"
                )
                prev_var = f"{process_name}.out"
            else:
                var_name = f"{process_name}_out"
                lines.append(
                    f"    {var_name} = {process_name}({prev_var}{script_arg}{inputs_arg})"
                )
                prev_var = var_name

        lines.append("}")
        return lines

    @staticmethod
    def _first_existing(*paths: Path) -> Optional[Path]:
        for p in paths:
            if p.exists():
                return p
        return None

    @staticmethod
    def _get_skill(phase: Phase) -> Optional[SkillDefinition]:
        """Return the selected skill for a phase, if it is a SkillDefinition."""
        skill = phase.selected_skill
        if isinstance(skill, SkillDefinition):
            return skill
        return None
