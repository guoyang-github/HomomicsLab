"""Tests for skill runtime requirements.txt handling."""

import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest

from homomics_lab.skills.runtime import SkillRuntimeExecutor


def _executor() -> SkillRuntimeExecutor:
    return SkillRuntimeExecutor()


def test_ensure_requirements_no_file(tmp_path):
    executor = _executor()
    # Should be a no-op when requirements.txt is absent.
    executor._ensure_requirements(tmp_path)


def test_ensure_requirements_installed_package(tmp_path):
    executor = _executor()
    req_file = tmp_path / "requirements.txt"
    # pytest is installed in the test environment.
    req_file.write_text("pytest\n", encoding="utf-8")
    executor._ensure_requirements(tmp_path)


def test_ensure_requirements_missing_package_raises(tmp_path):
    executor = _executor()
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("this_package_definitely_does_not_exist_12345\n", encoding="utf-8")

    with pytest.raises(RuntimeError) as exc_info:
        executor._ensure_requirements(tmp_path)
    assert "Missing required packages" in str(exc_info.value)


def test_ensure_requirements_interactive_install(tmp_path, monkeypatch):
    executor = _executor()
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("missing_pkg\n", encoding="utf-8")

    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)

    check_call = MagicMock()
    monkeypatch.setattr(subprocess, "check_call", check_call)

    with patch("builtins.input", return_value="y"):
        executor._ensure_requirements(tmp_path)

    check_call.assert_called_once()
    args = check_call.call_args[0][0]
    assert args[:2] == [sys.executable, "-m"]
    assert "-r" in args
    assert str(req_file) in args


def test_ensure_requirements_interactive_decline(tmp_path, monkeypatch):
    executor = _executor()
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("missing_pkg\n", encoding="utf-8")

    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)

    with patch("builtins.input", return_value="n"):
        with pytest.raises(RuntimeError) as exc_info:
            executor._ensure_requirements(tmp_path)
    assert "Missing required packages" in str(exc_info.value)
