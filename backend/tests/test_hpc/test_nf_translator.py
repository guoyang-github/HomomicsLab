"""Tests for PlanResult -> Nextflow DSL2 translation."""

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
            strategy_name="single_cell",
            data_state=DataState(),
        )

        translator = SimpleNFTranslator(working_dir=tmp_path)
        nf_file = translator.translate(plan, inputs={"input_file": "data.h5ad"})

        assert nf_file.exists()
        script = nf_file.read_text()
        assert "nextflow.enable.dsl = 2" in script
        assert "process scanpy_qc" in script
        assert "workflow {" in script
        assert "params {" in script
        assert 'input_file = "data.h5ad"' in script

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
