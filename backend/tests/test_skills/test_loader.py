import pytest

from homomics_lab.skills.loader import SkillLoader
from homomics_lab.skills.models import SkillDefinition


@pytest.fixture
def sample_skills_dir(tmp_path):
    """Create a mock NanoResearch-Skills directory structure."""
    # Skill 1: Python-only skill
    skill1_dir = tmp_path / "bio-single-cell-preprocessing"
    skill1_dir.mkdir()
    (skill1_dir / "SKILL.md").write_text("""\
---
name: bio-single-cell-preprocessing
description: Quality control, filtering, and normalization for single-cell RNA-seq.
tool_type: python
primary_tool: scanpy
supported_tools: [scanpy, anndata, numpy]
keywords: ["single-cell", "preprocessing", "QC"]
---

# Single-Cell Preprocessing

Quality control, filtering, and normalization.
""")
    scripts1 = skill1_dir / "scripts" / "python"
    scripts1.mkdir(parents=True)
    (scripts1 / "qc.py").write_text("# QC code")
    (scripts1 / "normalize.py").write_text("# Normalize code")
    (skill1_dir / "requirements.txt").write_text("scanpy>=1.9.0\nanndata>=0.9.0\n")

    # Skill 2: R-only skill
    skill2_dir = tmp_path / "bio-single-cell-clustering-r"
    skill2_dir.mkdir()
    (skill2_dir / "SKILL.md").write_text("""\
---
name: bio-single-cell-clustering-r
description: Clustering with Seurat in R.
tool_type: r
primary_tool: Seurat
supported_tools: [Seurat, ggplot2]
keywords: ["single-cell", "clustering", "Seurat"]
---

# Seurat Clustering

Cluster cells in R.
""")
    scripts2 = skill2_dir / "scripts" / "r"
    scripts2.mkdir(parents=True)
    (scripts2 / "cluster.R").write_text("# R clustering code")

    # Skill 3: Mixed skill with multi_sample
    skill3_dir = tmp_path / "bio-single-cell-data-io"
    skill3_dir.mkdir()
    (skill3_dir / "SKILL.md").write_text("""\
---
name: bio-single-cell-data-io
description: Read and write single-cell data.
tool_type: mixed
primary_tool: Seurat
supported_tools: [scanpy, anndata, Seurat]
keywords: ["single-cell", "data-io", "10X"]
multi_sample:
  supported: true
  input_format: samplesheet.csv
  formats: [10x_mtx, 10x_h5, h5ad]
---

# Data I/O

Read and write single-cell data.
""")
    scripts3_py = skill3_dir / "scripts" / "python"
    scripts3_py.mkdir(parents=True)
    (scripts3_py / "io.py").write_text("# Python IO")
    scripts3_r = skill3_dir / "scripts" / "r"
    scripts3_r.mkdir(parents=True)
    (scripts3_r / "io.R").write_text("# R IO")

    # Non-skill directory (should be ignored)
    (tmp_path / "README.md").write_text("# Skills Collection")

    return tmp_path


class TestSkillLoader:
    def test_load_single_python_skill(self, sample_skills_dir):
        loader = SkillLoader()
        skill_dir = sample_skills_dir / "bio-single-cell-preprocessing"

        skill = loader.load_skill(skill_dir)

        assert isinstance(skill, SkillDefinition)
        assert skill.id == "bio-single-cell-preprocessing"
        assert skill.name == "bio-single-cell-preprocessing"
        assert (
            skill.description
            == "Quality control, filtering, and normalization for single-cell RNA-seq."
        )
        assert skill.runtime.type == "python"
        assert skill.runtime.python_version == "3.10"
        assert skill.runtime.dependencies == ["scanpy>=1.9.0", "anndata>=0.9.0"]
        assert skill.metadata["primary_tool"] == "scanpy"
        assert skill.metadata["supported_tools"] == ["scanpy", "anndata", "numpy"]
        assert skill.metadata["keywords"] == ["single-cell", "preprocessing", "QC"]
        assert skill.metadata["scripts_dir"] == str(skill_dir / "scripts" / "python")
        assert skill.category == "single-cell"

    def test_load_single_r_skill(self, sample_skills_dir):
        loader = SkillLoader()
        skill_dir = sample_skills_dir / "bio-single-cell-clustering-r"

        skill = loader.load_skill(skill_dir)

        assert skill.runtime.type == "r"
        assert skill.metadata["primary_tool"] == "Seurat"
        assert skill.metadata["scripts_dir"] == str(skill_dir / "scripts" / "r")

    def test_load_mixed_skill(self, sample_skills_dir):
        loader = SkillLoader()
        skill_dir = sample_skills_dir / "bio-single-cell-data-io"

        skill = loader.load_skill(skill_dir)

        assert skill.runtime.type == "mixed"
        assert skill.metadata["primary_tool"] == "Seurat"
        # For mixed with R-based primary_tool (Seurat), should prefer R scripts dir
        assert "scripts/r" in skill.metadata["scripts_dir"]
        assert "multi_sample" in skill.metadata
        assert skill.metadata["multi_sample"]["supported"] is True

    def test_load_all_skills(self, sample_skills_dir):
        loader = SkillLoader()

        skills = loader.load_all(sample_skills_dir)

        assert len(skills) == 3
        ids = {s.id for s in skills}
        assert ids == {
            "bio-single-cell-preprocessing",
            "bio-single-cell-clustering-r",
            "bio-single-cell-data-io",
        }

    def test_load_all_skills_with_registry(self, sample_skills_dir):
        from homomics_lab.skills.registry import SkillRegistry

        registry = SkillRegistry()
        loader = SkillLoader(registry=registry)

        loader.load_all(sample_skills_dir)

        assert len(registry.list_all()) == 3
        assert registry.get("bio-single-cell-preprocessing") is not None

    def test_skill_without_scripts_dir(self, tmp_path):
        """Skills without scripts directory should still be loadable but marked."""
        skill_dir = tmp_path / "incomplete-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("""\
---
name: incomplete-skill
description: A skill with no scripts.
tool_type: python
primary_tool: test
keywords: ["test"]
---

# Test
""")

        loader = SkillLoader()
        skill = loader.load_skill(skill_dir)

        assert skill.metadata["scripts_dir"] is None

    def test_skill_without_requirements(self, sample_skills_dir):
        """Skills without requirements.txt should have empty dependencies."""
        skill_dir = sample_skills_dir / "bio-single-cell-clustering-r"

        loader = SkillLoader()
        skill = loader.load_skill(skill_dir)

        assert skill.runtime.dependencies == []

    def test_skip_non_skill_directories(self, sample_skills_dir):
        """Directories without SKILL.md should be skipped."""
        # Add a directory without SKILL.md
        bad_dir = sample_skills_dir / "not-a-skill"
        bad_dir.mkdir()
        (bad_dir / "random.txt").write_text("not a skill")

        loader = SkillLoader()
        skills = loader.load_all(sample_skills_dir)

        assert len(skills) == 3  # Still 3, not 4


class TestMinimalContract:
    """Loader behavior for the minimal, agentskills.org-compatible contract.

    Only ``name`` and ``description`` are required, and even those are
    tolerated at load time: a missing ``name`` is inferred from the directory
    name, a missing ``description`` only logs a warning. ``tool_type`` is
    inferred from ``scripts/`` when absent. Unknown frontmatter fields are
    ignored.
    """

    def _write_skill(self, tmp_path, dirname, content):
        skill_dir = tmp_path / dirname
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(content)
        return skill_dir

    def test_missing_name_inferred_from_directory(self, tmp_path):
        skill_dir = self._write_skill(
            tmp_path,
            "inferred-name",
            "---\ndescription: No name declared.\ntool_type: python\n---\n",
        )

        skill = SkillLoader().load_skill(skill_dir)

        assert skill.id == "inferred-name"
        assert skill.name == "inferred-name"

    def test_missing_description_warns_but_loads(self, tmp_path, caplog):
        skill_dir = self._write_skill(
            tmp_path,
            "no-desc",
            "---\nname: no-desc\ntool_type: python\n---\n",
        )

        with caplog.at_level("WARNING", logger="homomics_lab.skills.loader"):
            skill = SkillLoader().load_skill(skill_dir)

        assert skill.id == "no-desc"
        assert skill.description == ""
        warnings = [r for r in caplog.records if r.levelname == "WARNING"]
        assert any("no description" in r.getMessage() for r in warnings)

    def test_bare_skill_md_without_frontmatter_loads(self, tmp_path):
        skill_dir = self._write_skill(
            tmp_path,
            "bare-skill",
            "# Bare Skill\n\nNo frontmatter at all.\n",
        )

        skill = SkillLoader().load_skill(skill_dir)

        assert skill.id == "bare-skill"
        assert skill.runtime.type == "agent"

    def test_tool_type_inferred_python_scripts(self, tmp_path):
        skill_dir = self._write_skill(
            tmp_path, "py-skill", "---\nname: py-skill\ndescription: x\n---\n"
        )
        scripts = skill_dir / "scripts" / "python"
        scripts.mkdir(parents=True)
        (scripts / "core.py").write_text("# code")

        skill = SkillLoader().load_skill(skill_dir)

        assert skill.runtime.type == "python"

    def test_tool_type_inferred_r_scripts(self, tmp_path):
        skill_dir = self._write_skill(
            tmp_path, "r-skill", "---\nname: r-skill\ndescription: x\n---\n"
        )
        scripts = skill_dir / "scripts" / "r"
        scripts.mkdir(parents=True)
        (scripts / "core.R").write_text("# code")

        skill = SkillLoader().load_skill(skill_dir)

        assert skill.runtime.type == "r"

    def test_tool_type_inferred_mixed_scripts(self, tmp_path):
        skill_dir = self._write_skill(
            tmp_path, "mixed-skill", "---\nname: mixed-skill\ndescription: x\n---\n"
        )
        (skill_dir / "scripts" / "python").mkdir(parents=True)
        (skill_dir / "scripts" / "r").mkdir(parents=True)

        skill = SkillLoader().load_skill(skill_dir)

        assert skill.runtime.type == "mixed"

    def test_tool_type_inferred_flat_scripts(self, tmp_path):
        """Ecosystem skills often keep flat scripts/*.py without subdirs."""
        skill_dir = self._write_skill(
            tmp_path, "flat-skill", "---\nname: flat-skill\ndescription: x\n---\n"
        )
        scripts = skill_dir / "scripts"
        scripts.mkdir()
        (scripts / "helper.py").write_text("# code")

        skill = SkillLoader().load_skill(skill_dir)

        assert skill.runtime.type == "python"

    def test_tool_type_inferred_agent_without_scripts(self, tmp_path):
        skill_dir = self._write_skill(
            tmp_path, "agentic-skill", "---\nname: agentic-skill\ndescription: x\n---\n"
        )

        skill = SkillLoader().load_skill(skill_dir)

        assert skill.runtime.type == "agent"

    def test_explicit_tool_type_wins_over_inference(self, tmp_path):
        skill_dir = self._write_skill(
            tmp_path,
            "explicit-skill",
            "---\nname: explicit-skill\ndescription: x\ntool_type: r\n---\n",
        )
        scripts = skill_dir / "scripts" / "python"
        scripts.mkdir(parents=True)
        (scripts / "core.py").write_text("# code")

        skill = SkillLoader().load_skill(skill_dir)

        assert skill.runtime.type == "r"

    def test_unknown_frontmatter_fields_ignored(self, tmp_path, caplog):
        skill_dir = self._write_skill(
            tmp_path,
            "custom-fields",
            """\
---
name: custom-fields
description: Has custom ecosystem fields.
custom_field: whatever
another-plugin-key:
  nested: true
---
""",
        )

        with caplog.at_level("DEBUG", logger="homomics_lab.skills.loader"):
            skill = SkillLoader().load_skill(skill_dir)

        assert skill.id == "custom-fields"
        assert any(
            "ignoring unknown frontmatter fields" in r.getMessage()
            and "custom_field" in r.getMessage()
            for r in caplog.records
        )

    def test_ecosystem_minimal_skills_end_to_end(self, tmp_path):
        """agentskills.org-style minimal skills load and enter the registry."""
        from homomics_lab.skills.registry import SkillRegistry

        # 1. name + description + body only
        eco1 = tmp_path / "pdf-tools"
        eco1.mkdir()
        (eco1 / "SKILL.md").write_text(
            "---\nname: pdf-tools\ndescription: Extract and merge PDF files.\n---\n\n# PDF Tools\n"
        )
        # 2. name + description + scripts, no tool_type
        eco2 = tmp_path / "data-cleaner"
        eco2.mkdir()
        (eco2 / "SKILL.md").write_text(
            "---\nname: data-cleaner\ndescription: Clean messy CSV files.\n---\n"
        )
        scripts = eco2 / "scripts" / "python"
        scripts.mkdir(parents=True)
        (scripts / "clean.py").write_text("# clean\n")
        # 3. bare SKILL.md with no frontmatter fields at all
        eco3 = tmp_path / "bare-notes"
        eco3.mkdir()
        (eco3 / "SKILL.md").write_text("# Bare Notes\n\nFree-form knowledge.\n")

        registry = SkillRegistry()
        loader = SkillLoader(registry=registry)
        skills = loader.load_all(tmp_path)

        assert {s.id for s in skills} == {"pdf-tools", "data-cleaner", "bare-notes"}
        assert registry.get("pdf-tools").runtime.type == "agent"
        assert registry.get("data-cleaner").runtime.type == "python"
        assert registry.get("bare-notes").runtime.type == "agent"
        assert registry.get("pdf-tools").description == "Extract and merge PDF files."
