"""Tests for sandbox default container image selection by exec_type."""

from unittest.mock import patch

from homomics_lab.skills.sandbox import R_CONTAINER_IMAGE, SKILL_CONTAINER_IMAGE
from homomics_lab.skills.sandbox import ContainerSandbox, Sandbox


def test_container_sandbox_defaults_to_python_image(tmp_path):
    sandbox = ContainerSandbox(tmp_path)
    assert sandbox.container_image == SKILL_CONTAINER_IMAGE


def test_container_sandbox_uses_r_image_for_exec_type_r(tmp_path):
    sandbox = ContainerSandbox(tmp_path, exec_type="r")
    assert sandbox.container_image == R_CONTAINER_IMAGE


def test_container_sandbox_respects_explicit_image(tmp_path):
    sandbox = ContainerSandbox(tmp_path, container_image="custom:latest", exec_type="r")
    assert sandbox.container_image == "custom:latest"


def test_sandbox_create_passes_exec_type(tmp_path):
    with patch.object(ContainerSandbox, "_detect_engine", return_value="docker"):
        sandbox = Sandbox.create("container", tmp_path, exec_type="r")
        assert isinstance(sandbox, ContainerSandbox)
        assert sandbox.container_image == R_CONTAINER_IMAGE
