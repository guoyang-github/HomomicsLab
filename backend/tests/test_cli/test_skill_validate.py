"""Tests for ``homomics skill validate``."""

import pytest

from homomics_lab.cli.main import main
from homomics_lab.skills.loader import validate_skill_contract


@pytest.fixture
def skills_tree(tmp_path):
    """A directory tree with one OK, one warning-only, and one broken skill."""
    ok = tmp_path / "good-skill"
    ok.mkdir()
    (ok / "SKILL.md").write_text("""\
---
name: good-skill
description: Fully specified.
tool_type: python
keywords: [demo]
inputs:
  x:
    type: integer
outputs:
  y:
    type: integer
---

# Good Skill
""")

    warn = tmp_path / "minimal-skill"
    warn.mkdir()
    (warn / "SKILL.md").write_text(
        "---\nname: minimal-skill\ndescription: Only the required fields.\n---\n"
    )

    bad = tmp_path / "bad-skill"
    bad.mkdir()
    (bad / "SKILL.md").write_text("---\nname: bad-skill\n---\n")

    return tmp_path


class TestValidateSkillContract:
    def test_ok_skill_has_no_issues(self, skills_tree):
        result = validate_skill_contract(skills_tree / "good-skill")

        assert result.ok
        assert result.errors == []
        assert result.warnings == []
        assert result.name == "good-skill"

    def test_missing_recommended_fields_are_warnings(self, skills_tree):
        result = validate_skill_contract(skills_tree / "minimal-skill")

        assert result.errors == []
        assert len(result.warnings) == 4
        assert any("tool_type" in w for w in result.warnings)
        assert any("keywords" in w for w in result.warnings)
        assert any("inputs" in w for w in result.warnings)
        assert any("outputs" in w for w in result.warnings)

    def test_missing_required_fields_are_errors(self, skills_tree):
        result = validate_skill_contract(skills_tree / "bad-skill")

        assert any("description" in e for e in result.errors)

    def test_missing_name_is_an_error(self, tmp_path):
        skill_dir = tmp_path / "no-name"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\ndescription: No name.\n---\n")

        result = validate_skill_contract(skill_dir)

        assert any("name" in e for e in result.errors)

    def test_invalid_yaml_frontmatter_is_an_error(self, tmp_path):
        skill_dir = tmp_path / "broken-yaml"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\nname: [unclosed\n---\n")

        result = validate_skill_contract(skill_dir)

        assert any("frontmatter" in e.lower() for e in result.errors)

    def test_unclosed_frontmatter_is_an_error(self, tmp_path):
        skill_dir = tmp_path / "unclosed"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: unclosed\n\nbody without closing\n"
        )

        result = validate_skill_contract(skill_dir)

        assert any("malformed frontmatter" in e for e in result.errors)

    def test_missing_skill_md_is_an_error(self, tmp_path):
        skill_dir = tmp_path / "empty-dir"
        skill_dir.mkdir()

        result = validate_skill_contract(skill_dir)

        assert any("SKILL.md" in e for e in result.errors)


class TestSkillValidateCLI:
    def test_ok_skill_exit_zero(self, skills_tree, capsys):
        rc = main(["skill", "validate", str(skills_tree / "good-skill")])

        assert rc == 0
        out = capsys.readouterr().out
        assert "OK" in out
        assert "good-skill" in out

    def test_warnings_do_not_fail_without_strict(self, skills_tree, capsys):
        rc = main(["skill", "validate", str(skills_tree / "minimal-skill")])

        assert rc == 0
        assert "WARNINGS" in capsys.readouterr().out

    def test_warnings_fail_with_strict(self, skills_tree, capsys):
        rc = main(["skill", "validate", str(skills_tree / "minimal-skill"), "--strict"])

        assert rc == 1
        assert "WARNINGS" in capsys.readouterr().out

    def test_errors_fail(self, skills_tree, capsys):
        rc = main(["skill", "validate", str(skills_tree / "bad-skill")])

        assert rc == 1
        assert "ERRORS" in capsys.readouterr().out

    def test_directory_tree_reports_one_line_per_skill(self, skills_tree, capsys):
        rc = main(["skill", "validate", str(skills_tree)])

        assert rc == 1
        out = capsys.readouterr().out
        assert "OK       good-skill" in out
        assert "WARNINGS minimal-skill" in out
        assert "ERRORS   bad-skill" in out
        assert "3 skill(s)" in out

    def test_skill_md_file_path_accepted(self, skills_tree, capsys):
        rc = main(["skill", "validate", str(skills_tree / "good-skill" / "SKILL.md")])

        assert rc == 0
        assert "good-skill" in capsys.readouterr().out

    def test_missing_path_fails(self, tmp_path, capsys):
        rc = main(["skill", "validate", str(tmp_path / "nope")])

        assert rc == 1
        assert "not found" in capsys.readouterr().err.lower()

    def test_directory_without_skills_fails(self, tmp_path, capsys):
        rc = main(["skill", "validate", str(tmp_path)])

        assert rc == 1
        assert "No SKILL.md" in capsys.readouterr().err
