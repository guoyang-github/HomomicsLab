import pytest
from pathlib import Path

from homomics_lab.skills.external_loader import ExternalSkillLoader
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


class TestExternalSkillLoader:
    def test_load_single_python_skill(self, sample_skills_dir):
        loader = ExternalSkillLoader()
        skill_dir = sample_skills_dir / "bio-single-cell-preprocessing"

        skill = loader.load_skill(skill_dir)

        assert isinstance(skill, SkillDefinition)
        assert skill.id == "bio-single-cell-preprocessing"
        assert skill.name == "bio-single-cell-preprocessing"
        assert skill.description == "Quality control, filtering, and normalization for single-cell RNA-seq."
        assert skill.runtime.type == "python"
        assert skill.runtime.python_version == "3.10"
        assert skill.runtime.dependencies == ["scanpy>=1.9.0", "anndata>=0.9.0"]
        assert skill.metadata["primary_tool"] == "scanpy"
        assert skill.metadata["supported_tools"] == ["scanpy", "anndata", "numpy"]
        assert skill.metadata["keywords"] == ["single-cell", "preprocessing", "QC"]
        assert skill.metadata["scripts_dir"] == str(skill_dir / "scripts" / "python")
        assert skill.category == "single-cell"

    def test_load_single_r_skill(self, sample_skills_dir):
        loader = ExternalSkillLoader()
        skill_dir = sample_skills_dir / "bio-single-cell-clustering-r"

        skill = loader.load_skill(skill_dir)

        assert skill.runtime.type == "r"
        assert skill.metadata["primary_tool"] == "Seurat"
        assert skill.metadata["scripts_dir"] == str(skill_dir / "scripts" / "r")

    def test_load_mixed_skill(self, sample_skills_dir):
        loader = ExternalSkillLoader()
        skill_dir = sample_skills_dir / "bio-single-cell-data-io"

        skill = loader.load_skill(skill_dir)

        assert skill.runtime.type == "mixed"
        assert skill.metadata["primary_tool"] == "Seurat"
        # For mixed with R-based primary_tool (Seurat), should prefer R scripts dir
        assert "scripts/r" in skill.metadata["scripts_dir"]
        assert "multi_sample" in skill.metadata
        assert skill.metadata["multi_sample"]["supported"] is True

    def test_load_all_skills(self, sample_skills_dir):
        loader = ExternalSkillLoader()

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
        loader = ExternalSkillLoader(registry=registry)

        skills = loader.load_all(sample_skills_dir)

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

        loader = ExternalSkillLoader()
        skill = loader.load_skill(skill_dir)

        assert skill.metadata["scripts_dir"] is None

    def test_skill_without_requirements(self, sample_skills_dir):
        """Skills without requirements.txt should have empty dependencies."""
        skill_dir = sample_skills_dir / "bio-single-cell-clustering-r"

        loader = ExternalSkillLoader()
        skill = loader.load_skill(skill_dir)

        assert skill.runtime.dependencies == []

    def test_skip_non_skill_directories(self, sample_skills_dir):
        """Directories without SKILL.md should be skipped."""
        # Add a directory without SKILL.md
        bad_dir = sample_skills_dir / "not-a-skill"
        bad_dir.mkdir()
        (bad_dir / "random.txt").write_text("not a skill")

        loader = ExternalSkillLoader()
        skills = loader.load_all(sample_skills_dir)

        assert len(skills) == 3  # Still 3, not 4
