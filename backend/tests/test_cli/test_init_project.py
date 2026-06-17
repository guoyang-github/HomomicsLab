"""Tests for `homomics init-project` CLI command."""

import os
import tempfile

from homomics_lab.cli.main import main


def test_init_project_blank():
    with tempfile.TemporaryDirectory() as tmpdir:
        code = main(["init-project", "--output", tmpdir, "test_project"])
        assert code == 0
        project_dir = os.path.join(tmpdir, "test_project")
        assert os.path.isdir(project_dir)
        assert os.path.isfile(os.path.join(project_dir, "homomics.yaml"))
        assert os.path.isdir(os.path.join(project_dir, "data"))
        assert os.path.isdir(os.path.join(project_dir, "results"))
        assert os.path.isdir(os.path.join(project_dir, "workspace"))
        assert os.path.isfile(os.path.join(project_dir, "MEMORY.md"))


def test_init_project_existing_directory():
    with tempfile.TemporaryDirectory() as tmpdir:
        os.makedirs(os.path.join(tmpdir, "existing"))
        code = main(["init-project", "--output", tmpdir, "existing"])
        assert code == 1


def test_init_project_with_template():
    with tempfile.TemporaryDirectory() as tmpdir:
        code = main(["init-project", "--template", "metagenomics", "--output", tmpdir, "meta"])
        assert code == 0
        yaml_path = os.path.join(tmpdir, "meta", "homomics.yaml")
        content = open(yaml_path, encoding="utf-8").read()
        assert "domain: metagenomics" in content
        assert "qc" in content
