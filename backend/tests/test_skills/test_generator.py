"""Tests for skill generator."""


from homomics_lab.skills.generator.generator import SkillGenerator
from homomics_lab.skills.generator.templates import SkillTemplateBuilder


class TestSkillTemplateBuilder:
    def test_build_skill_md(self):
        builder = SkillTemplateBuilder()
        md = builder.build_skill_md(
            name="test-skill",
            description="A test skill",
            category="single-cell",
            tool_type="python",
            primary_tool="scanpy",
            supported_tools=["scanpy", "anndata"],
            keywords=["qc", "filtering"],
            inputs=[{"name": "input_file", "description": "Input data", "required": True}],
            outputs=["filtered_data", "qc_plots"],
            dependencies=["scanpy", "anndata"],
        )
        assert "name: test-skill" in md
        assert "tool_type: python" in md
        assert "primary_tool: scanpy" in md
        assert "single-cell" in md
        assert "Input data" in md
        assert "filtered_data" in md
        assert "scanpy" in md

    def test_build_python_script(self):
        builder = SkillTemplateBuilder()
        script = builder.build_python_script(
            name="test-skill",
            description="A test skill",
            inputs=[{"name": "input_file"}, {"name": "n_neighbors", "default": "15"}],
            outputs=["result"],
        )
        assert "def main(skill_inputs: dict)" in script
        assert 'input_file = skill_inputs["input_file"]' in script
        assert 'n_neighbors = skill_inputs.get("n_neighbors", 15)' in script
        assert "json.dumps" in script

    def test_build_r_script(self):
        builder = SkillTemplateBuilder()
        script = builder.build_r_script(
            name="test-skill",
            description="A test skill",
            inputs=[{"name": "input_file"}],
            outputs=["result"],
        )
        assert "main <- function(skill_inputs)" in script
        assert "library(jsonlite)" in script
        assert 'result$' in script

    def test_build_requirements_txt(self):
        builder = SkillTemplateBuilder()
        req = builder.build_requirements_txt(["scanpy", "anndata"])
        assert "scanpy" in req
        assert "anndata" in req


class TestSkillGenerator:
    def test_normalize_name(self):
        assert SkillGenerator._normalize_name("Hello World") == "hello-world"
        assert SkillGenerator._normalize_name("Test_Skill-Name!") == "test-skill-name"
        assert SkillGenerator._normalize_name("  spaces  ") == "spaces"

    def test_generate_python_skill(self):
        gen = SkillGenerator()
        files = gen.generate(
            name="QC Analysis",
            description="Perform QC on single cell data",
            category="single-cell",
            tool_type="python",
            supported_tools=["scanpy"],
            keywords=["qc"],
            inputs=[{"name": "input_file", "description": "Input h5ad"}],
            outputs=["filtered_data"],
            dependencies=["scanpy", "anndata"],
        )
        assert "qc-analysis/SKILL.md" in files
        assert "qc-analysis/scripts/python/run.py" in files
        assert "qc-analysis/scripts/python/requirements.txt" in files
        assert "scanpy" in files["qc-analysis/scripts/python/requirements.txt"]

    def test_generate_r_skill(self):
        gen = SkillGenerator()
        files = gen.generate(
            name="Seurat Clustering",
            description="Cluster cells with Seurat",
            tool_type="r",
            supported_tools=["Seurat"],
            inputs=[{"name": "input_file"}],
            outputs=["clusters"],
        )
        assert "seurat-clustering/SKILL.md" in files
        assert "seurat-clustering/scripts/r/run.R" in files

    def test_generate_mixed_skill(self):
        gen = SkillGenerator()
        files = gen.generate(
            name="Mixed Analysis",
            description="Mixed tool analysis",
            tool_type="mixed",
            inputs=[{"name": "input_file"}],
            outputs=["result"],
        )
        assert "mixed-analysis/scripts/python/run.py" in files
        assert "mixed-analysis/scripts/r/run.R" in files

    def test_suggest_from_description_python(self):
        gen = SkillGenerator()
        result = gen.suggest_from_description("Analyze single cell data with scanpy")
        assert result["tool_type"] == "python"
        assert result["category"] == "single-cell"
        assert "analysis" in result["keywords"]

    def test_suggest_from_description_r(self):
        gen = SkillGenerator()
        result = gen.suggest_from_description("Use Seurat for clustering cells")
        assert result["tool_type"] == "r"
        assert result["category"] == "single-cell"
        assert "cluster" in result["keywords"]

    def test_suggest_from_description_spatial(self):
        gen = SkillGenerator()
        result = gen.suggest_from_description("Spatial transcriptomics analysis")
        assert result["category"] == "spatial-transcriptomics"

    def test_save(self, tmp_path):
        gen = SkillGenerator(output_dir=tmp_path)
        files = {
            "test-skill/SKILL.md": "# Test",
            "test-skill/scripts/python/run.py": "print('hello')",
        }
        base = gen.save(files)
        assert (base / "test-skill" / "SKILL.md").exists()
        assert (base / "test-skill" / "scripts" / "python" / "run.py").exists()
