"""Tests for transient skill promotion."""

from pathlib import Path

import pytest

from homomics_lab.skills.promotion import SkillPromotionError, TransientSkillPromoter
from homomics_lab.skills.registry import SkillRegistry


@pytest.fixture
def codeact_workdir(tmp_path: Path) -> Path:
    workdir = tmp_path / "codeact_run"
    workdir.mkdir()
    (workdir / "__code_act_source__.py").write_text(
        "import scanpy as sc\nadata = sc.read_h5ad('input.h5ad')\nresult = {'cells': 100}\n",
        encoding="utf-8",
    )
    (workdir / "__skill_result__.json").write_text('{"cells": 100}', encoding="utf-8")
    return workdir


def test_create_package_generates_skill_files(codeact_workdir):
    registry = SkillRegistry()
    promoter = TransientSkillPromoter(registry)
    package_dir = promoter.create_package(codeact_workdir)

    assert (package_dir / "SKILL.md").exists()
    assert (package_dir / "scripts" / "run.py").exists()
    assert "scanpy" in (package_dir / "scripts" / "run.py").read_text()


def test_promote_registers_skill(codeact_workdir):
    registry = SkillRegistry()
    promoter = TransientSkillPromoter(registry)

    skill = promoter.promote(codeact_workdir, name="Generated QC")

    assert skill.id == "generated_qc"
    assert skill.metadata["trusted"] is False
    assert "sha256" in skill.metadata
    assert registry.get("generated_qc") is skill


def test_promote_with_explicit_skill_id(codeact_workdir):
    registry = SkillRegistry()
    promoter = TransientSkillPromoter(registry)

    skill = promoter.promote(codeact_workdir, skill_id="my_custom_qc")

    assert skill.id == "my_custom_qc"


def test_promote_fails_without_source_code(tmp_path):
    registry = SkillRegistry()
    promoter = TransientSkillPromoter(registry)

    with pytest.raises(SkillPromotionError, match="No generated code found"):
        promoter.create_package(tmp_path)
