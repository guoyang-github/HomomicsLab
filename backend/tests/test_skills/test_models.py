from homics_lab.skills.models import SkillDefinition, SkillInputSchema, SkillRuntime


def test_skill_definition_validation():
    skill = SkillDefinition(
        id="scanpy_qc",
        name="Single Cell QC",
        version="1.0.0",
        category="single_cell_analysis",
        runtime=SkillRuntime(type="python", python_version="3.10"),
        input_schema=SkillInputSchema(
            type="object",
            properties={"adata_path": {"type": "string"}},
            required=["adata_path"],
        ),
    )
    assert skill.id == "scanpy_qc"
    assert skill.runtime.type == "python"


def test_input_validation():
    skill = SkillDefinition(
        id="test",
        name="Test",
        version="1.0.0",
        category="test",
        input_schema=SkillInputSchema(
            type="object",
            properties={
                "count": {"type": "integer", "default": 10},
            },
            required=[],
        ),
    )

    validated = skill.validate_input({})
    assert validated["count"] == 10
