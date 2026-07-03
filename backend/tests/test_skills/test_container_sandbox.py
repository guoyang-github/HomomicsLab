"""Tests for production container sandbox behavior."""

import asyncio
import json
from unittest.mock import patch

import pytest

from homomics_lab.config import settings
from homomics_lab.skills.sandbox import ContainerSandbox


class _MockProcess:
    def __init__(self, returncode=0, stdout=b"", stderr=b""):
        self.returncode = returncode
        self.stdout = asyncio.StreamReader()
        self.stdout.feed_data(stdout)
        self.stdout.feed_eof()
        self.stderr = asyncio.StreamReader()
        self.stderr.feed_data(stderr)
        self.stderr.feed_eof()

    async def wait(self):
        return self.returncode

    async def communicate(self):
        return (b"", b"")


@pytest.mark.asyncio
async def test_container_sandbox_mounts_venv_and_applies_resource_limits(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "skill_container_memory_mb", 512)
    monkeypatch.setattr(settings, "skill_container_cpus", 0.5)
    monkeypatch.setattr(settings, "skill_container_pids_limit", 32)
    monkeypatch.setattr(settings, "skill_container_readonly_root", True)

    sandbox = ContainerSandbox(tmp_path)
    sandbox._engine = "docker"  # force a container engine for the test

    venv_dir = tmp_path / "envs" / "test_skill" / "venv"
    python_path = venv_dir / "bin" / "python"
    python_path.parent.mkdir(parents=True)
    python_path.write_text("")

    result_path = tmp_path / "__skill_result__.json"
    result_path.write_text(json.dumps({"ok": True}))

    captured_args = []

    async def _fake_subprocess(*args, **kwargs):
        captured_args.extend(args)
        return _MockProcess(returncode=0)

    with patch("asyncio.create_subprocess_exec", new=_fake_subprocess):
        result = await sandbox.run_python(
            code="result = {'ok': True}",
            inputs={},
            python_path=str(python_path),
        )

    assert result == {"ok": True}
    assert "docker" in captured_args
    assert "--memory" in captured_args
    assert "512m" in captured_args
    assert "--cpus" in captured_args
    assert "0.5" in captured_args
    assert "--pids-limit" in captured_args
    assert "32" in captured_args
    assert "--init" in captured_args
    assert "--read-only" in captured_args
    venv_mount = next((a for a in captured_args if str(venv_dir) in a and "/skill_venv" in a), None)
    assert venv_mount is not None
    assert "/skill_venv/bin/python" in captured_args


@pytest.mark.asyncio
async def test_container_sandbox_falls_back_to_image_python_without_venv(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "skill_container_readonly_root", False)

    sandbox = ContainerSandbox(tmp_path)
    sandbox._engine = "docker"

    result_path = tmp_path / "__skill_result__.json"
    result_path.write_text(json.dumps({"ok": True}))

    captured_args = []

    async def _fake_subprocess(*args, **kwargs):
        captured_args.extend(args)
        return _MockProcess(returncode=0)

    with patch("asyncio.create_subprocess_exec", new=_fake_subprocess):
        await sandbox.run_python(
            code="result = {'ok': True}",
            inputs={},
            python_path=None,
        )

    assert "python" in captured_args
    assert "/skill_venv/bin/python" not in captured_args
    assert "--read-only" not in captured_args
