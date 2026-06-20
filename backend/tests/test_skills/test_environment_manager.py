"""Tests for EnvironmentManager conda/environment.yml support."""

import pytest

from homomics_lab.skills.environment_manager import EnvironmentManager


@pytest.fixture
def env_manager(tmp_path):
    return EnvironmentManager(base_dir=tmp_path, auto_install=False)


def test_python_venv_without_dependencies(env_manager, tmp_path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    info = env_manager.prepare_python("test_skill", scripts)
    assert info.language == "python"
    assert info.python_path is not None
    assert info.dependency_files == []


def test_python_uses_requirements_txt(env_manager, tmp_path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    req_file = scripts / "requirements.txt"
    req_file.write_text("requests\n")
    info = env_manager.prepare_python("test_skill", scripts)
    assert info.dependency_files == [str(req_file)]


def test_python_prefers_conda_when_environment_yml_present(env_manager, tmp_path, monkeypatch):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    env_yml = scripts / "environment.yml"
    env_yml.write_text("name: test\ndependencies:\n  - python=3.11\n")

    list_conda_called = False

    def fake_list_conda(self, env_path):
        nonlocal list_conda_called
        list_conda_called = True
        return {"python": "3.11"}

    monkeypatch.setattr(EnvironmentManager, "_conda_available", staticmethod(lambda: True))
    monkeypatch.setattr(EnvironmentManager, "_list_conda_packages", fake_list_conda)

    # Simulate an existing conda prefix by creating it.
    env_hash = env_manager._env_hash("test_skill", env_yml)
    env_path = env_manager.base_dir / "conda" / "test_skill" / env_hash
    env_path.mkdir(parents=True, exist_ok=True)

    info = env_manager.prepare_python("test_skill", scripts)
    assert info.language == "python"
    assert str(env_yml) in info.dependency_files
    assert list_conda_called


def test_conda_not_available_warns(env_manager, tmp_path, monkeypatch):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    env_yml = scripts / "environment.yml"
    env_yml.write_text("name: test\n")
    monkeypatch.setattr(EnvironmentManager, "_conda_available", staticmethod(lambda: False))

    # Without requirements.txt, the manager should warn and return empty packages.
    info = env_manager.prepare_python("test_skill", scripts)
    assert info.language == "python"
    assert info.installed_packages == {}
