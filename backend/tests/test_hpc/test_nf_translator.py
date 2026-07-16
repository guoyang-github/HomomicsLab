"""Tests for PlanResult -> Nextflow DSL2 translation."""

import json

from homomics_lab.agent.plan.models import DataState, Phase, PlanResult
from homomics_lab.hpc.nf_translator import SimpleNFTranslator
from homomics_lab.skills.models import SkillDefinition, SkillResources, SkillRuntime


class TestSimpleNFTranslator:
    def test_translates_required_phases(self, tmp_path):
        skill = SkillDefinition(
            id="scanpy_qc",
            name="QC",
            version="1.0",
            category="single-cell",
            author="test",
            description="QC skill",
            runtime=SkillRuntime(
                type="python",
                resources=SkillResources(memory="1GB", cpu=1, time="5m"),
            ),
        )
        plan = PlanResult(
            phases=[
                Phase(phase_type="qc", required=True, selected_skill=skill),
                Phase(phase_type="normalize", required=True, selected_skill=skill),
                Phase(phase_type="optional", required=False),
            ],
            strategy_name="single-cell-transcriptomics",
            data_state=DataState(),
        )

        translator = SimpleNFTranslator(working_dir=tmp_path)
        nf_file = translator.translate(plan, inputs={"input_file": "data.h5ad"})

        assert nf_file.exists()
        script = nf_file.read_text()
        assert "nextflow.enable.dsl = 2" in script
        assert "process scanpy_qc" in script
        assert "workflow {" in script
        # Params are emitted in DSL2 assignment style (params.<key> = ...).
        assert 'params.input_file = "data.h5ad"' in script
        assert 'input_file = "data.h5ad"' in script

        # Both required phases select the same skill: DSL2 forbids defining or
        # invoking a process more than once, so names must be disambiguated.
        assert "process scanpy_qc {" in script
        assert "process scanpy_qc_1 {" in script
        assert "scanpy_qc_1_out = scanpy_qc_1(scanpy_qc.out)" in script

    def test_sanitizes_process_names(self):
        assert SimpleNFTranslator._sanitize_process_name("my-skill.id") == "my_skill_id"
        assert SimpleNFTranslator._sanitize_process_name("123skill") == "_123skill"

    def test_uses_phase_type_when_no_skill(self):
        plan = PlanResult(
            phases=[Phase(phase_type="qc", required=True)],
            strategy_name="test",
            data_state=DataState(),
        )
        translator = SimpleNFTranslator()
        nf_file = translator.translate(plan, inputs={})
        script = nf_file.read_text()
        assert "process qc" in script


    def test_emits_real_python_process_from_skill_scripts(self, tmp_path):
        """A phase with a selected skill that has reference scripts gets a real process."""
        skill_dir = tmp_path / "skills" / "scanpy_qc"
        scripts_dir = skill_dir / "scripts" / "python"
        scripts_dir.mkdir(parents=True)
        (scripts_dir / "core_analysis.py").write_text(
            "def main(inputs):\n"
            "    return {'passed': inputs.get('min_genes', 200)}\n",
            encoding="utf-8",
        )

        skill = SkillDefinition(
            id="scanpy_qc",
            name="QC",
            version="1.0",
            category="single-cell",
            author="test",
            description="QC skill",
            runtime=SkillRuntime(
                type="python",
                resources=SkillResources(memory="1GB", cpu=1, time="5m"),
            ),
            metadata={"source_dir": str(skill_dir)},
        )

        plan = PlanResult(
            phases=[Phase(phase_type="qc", required=True, selected_skill=skill, parameters={"min_genes": 500})],
            strategy_name="single-cell-transcriptomics",
            data_state=DataState(),
        )

        translator = SimpleNFTranslator(working_dir=tmp_path)
        nf_file = translator.translate(plan, inputs={"input_file": "data.h5ad"})
        script = nf_file.read_text()

        assert "process scanpy_qc" in script
        assert "memory '1GB'" in script
        assert "cpus 1" in script
        assert "container \"python:3.10-slim\"" in script
        assert "python script.py" in script

        # Staged script and inputs files are referenced in the workflow.
        assert "Channel.value(file('phase_0_qc/script.py'))" in script
        assert "Channel.value(file('phase_0_qc/inputs.json'))" in script

        # Verify generated helper files exist.
        phase_dir = tmp_path / "phase_0_qc"
        assert (phase_dir / "script.py").exists()
        assert (phase_dir / "inputs.json").exists()
        inputs = json.loads((phase_dir / "inputs.json").read_text())
        assert inputs["min_genes"] == 500
        assert inputs["input_file"] == "data.h5ad"

        wrapper = (phase_dir / "script.py").read_text()
        assert "__inputs__ = json.load" in wrapper
        assert "result = main(__inputs__)" in wrapper
