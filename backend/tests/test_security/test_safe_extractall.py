"""Tests for safe zip extraction."""

import io
import zipfile

import pytest

from homomics_lab.security import PathSecurityError, safe_extractall


def _make_zip(members: dict) -> zipfile.ZipFile:
    """Create an in-memory zip from a dict of filename -> bytes."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in members.items():
            zf.writestr(name, content)
    buf.seek(0)
    return zipfile.ZipFile(buf, "r")


def test_extracts_normal_members(tmp_path):
    zf = _make_zip({"skill/SKILL.md": "# skill", "skill/run.py": "print(1)"})
    safe_extractall(zf, tmp_path)
    assert (tmp_path / "skill" / "SKILL.md").read_text() == "# skill"
    assert (tmp_path / "skill" / "run.py").read_text() == "print(1)"


def test_rejects_parent_reference(tmp_path):
    zf = _make_zip({"../escape.txt": "bad"})
    with pytest.raises(PathSecurityError):
        safe_extractall(zf, tmp_path)


def test_rejects_absolute_path(tmp_path):
    zf = _make_zip({"/etc/passwd": "bad"})
    with pytest.raises(PathSecurityError):
        safe_extractall(zf, tmp_path)


def test_rejects_deep_escape(tmp_path):
    zf = _make_zip({"a/../../escape.txt": "bad"})
    with pytest.raises(PathSecurityError):
        safe_extractall(zf, tmp_path)
