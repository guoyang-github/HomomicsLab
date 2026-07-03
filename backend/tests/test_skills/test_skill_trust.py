"""Tests for skill trust model and sandbox-based dynamic context injection."""

import pytest

from homomics_lab.config import settings
from homomics_lab.skills.loader import SkillLoader
from homomics_lab.skills.registry import SkillRegistry
from homomics_lab.skills.runtime import SkillRuntimeExecutor, UntrustedSkillError
from homomics_lab.skills.sandbox import (
    BubblewrapSandbox,
    ContainerSandbox,
    LocalSandbox,
    Sandbox,
)
from homomics_lab.skills.skill_store import SkillStore


class TestSandboxFactory:
    def test_factory_creates_local_when_requested(self, tmp_path):
        sandbox = Sandbox.create("local", tmp_path)
        assert isinstance(sandbox, LocalSandbox)

    def test_container_sandbox_availability_matches_docker(self, tmp_path):
        sandbox = ContainerSandbox(tmp_path)
        import shutil

        has_docker = (
            shutil.which("docker") is not None or shutil.which("podman") is not None
        )
        assert sandbox.is_available() == has_docker

    def test_bubblewrap_sandbox_availability_matches_bwrap(self, tmp_path):
        sandbox = BubblewrapSandbox(tmp_path)
        import shutil

        has_bwrap = shutil.which("bwrap") is not None
        assert sandbox.is_available() == has_bwrap


@pytest.fixture
def external_skill_dir(tmp_path):
    skill_dir = tmp_path / "external-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        """\
---
name: external-skill
description: An external skill.
tool_type: python
---

# Instructions
Return doubled value.
""",
        encoding="utf-8",
    )
    scripts = skill_dir / "scripts" / "python"
    scripts.mkdir(parents=True)
    (scripts / "run.py").write_text("result = {'doubled': value * 2}\n")
    return skill_dir


class TestSkillTrustEnforcement:
    @pytest.mark.asyncio
    async def test_external_skill_rejected_without_trust(
        self, external_skill_dir, tmp_path
    ):
        registry = SkillRegistry()
        loader = SkillLoader(registry=registry)
        skill = loader.load_discovery(external_skill_dir)
        skill.metadata["source"] = "external"
        registry.register(skill)

        executor = SkillRuntimeExecutor(registry=registry, working_dir=tmp_path)
        with pytest.raises(UntrustedSkillError):
            await executor.execute("external-skill", {"value": 5})

    @pytest.mark.asyncio
    async def test_external_skill_runs_after_trust(self, external_skill_dir, tmp_path):
        registry = SkillRegistry()
        loader = SkillLoader(registry=registry)
        skill = loader.load_discovery(external_skill_dir)
        skill.metadata["source"] = "external"
        skill.metadata["trusted"] = True
        registry.register(skill)

        executor = SkillRuntimeExecutor(registry=registry, working_dir=tmp_path)
        result = await executor.execute("external-skill", {"value": 5})

        assert result["doubled"] == 10

    def test_untrusted_external_skill_disables_shell_injection(
        self, external_skill_dir
    ):
        skill_dir = external_skill_dir
        (skill_dir / "SKILL.md").write_text(
            """\
---
name: external-skill
description: External skill with shell injection.
tool_type: agent
---

## Status
!`echo should-not-run`
""",
            encoding="utf-8",
        )

        # Ensure shell execution is globally enabled; only trust should block.
        settings.skills_shell_execution_enabled = True

        loader = SkillLoader()
        skill = loader.load_discovery(skill_dir)
        skill.metadata["source"] = "external"
        # Leave trusted False
        loader.activate(skill)

        assert "should-not-run" not in skill.metadata["instructions"]
        assert "untrusted skill" in skill.metadata["instructions"].lower()

    def test_trusted_external_skill_allows_shell_injection(self, external_skill_dir):
        skill_dir = external_skill_dir
        (skill_dir / "SKILL.md").write_text(
            """\
---
name: external-skill
description: External skill with shell injection.
tool_type: agent
---

## Status
!`echo runs-after-trust`
""",
            encoding="utf-8",
        )

        settings.skills_shell_execution_enabled = True

        loader = SkillLoader()
        skill = loader.load_discovery(skill_dir)
        skill.metadata["source"] = "external"
        skill.metadata["trusted"] = True
        loader.activate(skill)

        assert "runs-after-trust" in skill.metadata["instructions"]


class TestSkillStoreTrust:
    def test_import_marks_external_untrusted_and_records_sha256(
        self, external_skill_dir, tmp_path
    ):
        store = SkillStore(store_dir=tmp_path / "store", skills_dir=tmp_path / "skills")
        skill = store.import_skill(str(external_skill_dir), enable=True)

        assert skill.metadata["trusted"] is False
        assert skill.metadata["sha256"] is not None
        assert len(skill.metadata["sha256"]) == 64

        meta = store.get_meta(skill.id, namespace="default")
        assert meta["trusted"] is False
        assert meta["sha256"] == skill.metadata["sha256"]

    def test_trust_skill_persists_and_updates_registry(
        self, external_skill_dir, tmp_path
    ):
        store = SkillStore(store_dir=tmp_path / "store", skills_dir=tmp_path / "skills")
        skill = store.import_skill(str(external_skill_dir), enable=True)

        store.trust_skill(skill.id, trusted=True)

        assert store.get_meta(skill.id)["trusted"] is True
        assert store.registry.get(skill.id).metadata["trusted"] is True

        store.trust_skill(skill.id, trusted=False)
        assert store.get_meta(skill.id)["trusted"] is False
