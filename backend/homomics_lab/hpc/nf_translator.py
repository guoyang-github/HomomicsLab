"""Translate a PlanResult into a DSL2 Nextflow workflow."""

import re
from pathlib import Path
from typing import Any, Dict, List

from homomics_lab.agent.plan.models import Phase, PlanResult
from homomics_lab.skills.models import SkillDefinition


class SimpleNFTranslator:
    """Generate a linear DSL2 Nextflow script from a PlanResult.

    Each required phase becomes a process. Processes are wired sequentially via
    channels. The first process receives the user inputs; subsequent processes
    consume the output channel of the previous process.
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
            inputs: User inputs passed to the first process.
            output_path: Optional destination for the generated script.

        Returns:
            Path to the generated main.nf file.
        """
        phases = [p for p in plan.phases if p.required]
        if not phases:
            phases = plan.phases

        if output_path is None:
            output_path = self.working_dir / "main.nf"

        lines: List[str] = [
            "#!/usr/bin/env nextflow",
            "",
            "nextflow.enable.dsl = 2",
            "",
        ]

        # Emit a params block for inputs so Nextflow can expose them
        lines.extend(self._emit_params(inputs))
        lines.append("")

        for phase in phases:
            lines.extend(self._emit_process(phase))
            lines.append("")

        lines.extend(self._emit_workflow(phases, inputs))
        lines.append("")

        output_path.write_text("\n".join(lines), encoding="utf-8")
        return output_path

    @staticmethod
    def _sanitize_process_name(skill_id: str) -> str:
        """Make a valid Nextflow process name from a skill id."""
        name = re.sub(r"[^a-zA-Z0-9_]", "_", skill_id)
        if name[0].isdigit():
            name = "_" + name
        return name

    def _emit_params(self, inputs: Dict[str, Any]) -> List[str]:
        """Emit Nextflow params for top-level inputs."""
        lines = ["params {"]
        for key, value in inputs.items():
            if isinstance(value, str):
                lines.append(f'    {key} = "{value}"')
            elif isinstance(value, (list, dict, bool)):
                # Keep it simple: serialize JSON-style for complex values
                lines.append(f"    {key} = {value!r}")
            else:
                lines.append(f"    {key} = {value}")
        lines.append("}")
        return lines

    def _emit_process(self, phase: Phase) -> List[str]:
        """Emit a single Nextflow process for a phase."""
        skill = phase.selected_skill
        if skill is None:
            skill_id = phase.phase_type
        elif isinstance(skill, SkillDefinition):
            skill_id = skill.id
        else:
            skill_id = str(skill)
        process_name = self._sanitize_process_name(skill_id)

        lines = [
            f"process {process_name} {{",
            "    input:",
            "        val phase_input",
            "    output:",
            "        path 'result.json'",
            "    script:",
            '    """',
            f"    echo 'Running phase: {phase.phase_type}'",
            "    python << 'PYEOF'",
            "    import json",
            "    result = {'phase': '" + phase.phase_type + "', 'status': 'ok'}",
            "    with open('result.json', 'w') as f:",
            "        json.dump(result, f)",
            "    PYEOF",
            '    """',
            "}",
        ]
        return lines

    def _emit_workflow(
        self,
        phases: List[Phase],
        inputs: Dict[str, Any],
    ) -> List[str]:
        """Emit the DSL2 workflow wiring processes sequentially."""
        lines = ["workflow {"]

        if not phases:
            lines.append("}")
            return lines

        first_skill_id = self._skill_id(phases[0])
        first_process = self._sanitize_process_name(first_skill_id)

        # Initial channel from params
        lines.append("    inputs_ch = Channel.value(params.subMap([" + 
                     ", ".join(f"'{k}'" for k in inputs.keys()) + "]))")
        lines.append(f"    {first_process}(inputs_ch)")

        prev_var = f"{first_process}.out"
        for phase in phases[1:]:
            skill_id = self._skill_id(phase)
            process_name = self._sanitize_process_name(skill_id)
            var_name = f"{process_name}_out"
            lines.append(f"    {var_name} = {process_name}({prev_var})")
            prev_var = var_name

        lines.append("}")
        return lines

    @staticmethod
    def _skill_id(phase: Phase) -> str:
        """Return a string skill id for a phase."""
        if phase.selected_skill is None:
            return phase.phase_type
        skill = phase.selected_skill
        return skill.id if isinstance(skill, SkillDefinition) else str(skill)
