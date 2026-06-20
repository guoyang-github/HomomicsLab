"""Tests for `homomics run` CLI command."""

import argparse
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homomics_lab.cli.commands.run import _parse_run_args, run_run


def test_parse_run_args():
    args = ["task=hello", "count=3", "flag=true", "list=[1,2]"]
    parsed = _parse_run_args(args)
    assert parsed == {
        "task": "hello",
        "count": 3,
        "flag": True,
        "list": [1, 2],
    }


def test_parse_run_args_invalid():
    with pytest.raises(argparse.ArgumentTypeError):
        _parse_run_args(["not_a_kv_pair"])


def test_run_trusted_skill(capsys, tmp_path):
    skill = MagicMock(metadata={"source": "builtin"})
    registry = MagicMock(get=MagicMock(return_value=skill))
    executor = MagicMock(
        registry=registry,
        execute=AsyncMock(return_value={"success": True, "output": "ok"}),
    )
    skill_store = MagicMock()

    context = {"skill_executor": executor, "skill_store": skill_store}

    with patch(
        "homomics_lab.cli.commands.run.bootstrap_worker_context",
        new=AsyncMock(return_value=context),
    ):
        code = run_run(
            argparse.Namespace(
                skill_id="demo_skill",
                args=["task=count"],
                trust=False,
                working_dir=str(tmp_path),
            )
        )

    assert code == 0
    executor.execute.assert_awaited_once_with("demo_skill", {"task": "count"})
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result["success"] is True


def test_run_untrusted_external_skill_without_trust_flag(tmp_path):
    skill = MagicMock(metadata={"source": "external", "trusted": False})
    registry = MagicMock(get=MagicMock(return_value=skill))
    executor = MagicMock(registry=registry)
    skill_store = MagicMock()

    context = {"skill_executor": executor, "skill_store": skill_store}

    with patch(
        "homomics_lab.cli.commands.run.bootstrap_worker_context",
        new=AsyncMock(return_value=context),
    ), patch("sys.stdin.isatty", return_value=False):
        code = run_run(
            argparse.Namespace(
                skill_id="external_skill",
                args=[],
                trust=False,
                working_dir=None,
            )
        )

    assert code == 1
    executor.execute.assert_not_called()


def test_run_skill_not_found():
    registry = MagicMock(get=MagicMock(return_value=None))
    executor = MagicMock(registry=registry)
    skill_store = MagicMock()

    context = {"skill_executor": executor, "skill_store": skill_store}

    with patch(
        "homomics_lab.cli.commands.run.bootstrap_worker_context",
        new=AsyncMock(return_value=context),
    ):
        code = run_run(
            argparse.Namespace(
                skill_id="missing",
                args=[],
                trust=False,
                working_dir=None,
            )
        )

    assert code == 1
