"""Tests for the CLI entry point."""

import pytest

from homomics_lab.cli.main import create_parser, main


class TestCLIMain:
    def test_create_parser_prog(self):
        parser = create_parser()
        assert parser.prog == "homomics"

    def test_main_no_command_prints_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main([])
        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "HomomicsLab CLI" in captured.out

    def test_main_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "HomomicsLab CLI" in captured.out
        assert "init" in captured.out
        assert "validate" in captured.out
        assert "install" in captured.out
        assert "generate" in captured.out
        assert "list" in captured.out

    def test_entry_point_import_path(self):
        """The console script declared in pyproject.toml must be importable."""
        from homomics_lab.cli.main import main as entry_main

        assert callable(entry_main)
