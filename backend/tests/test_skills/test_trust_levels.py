"""Tests for the four-tier skill trust model (P3-1).

Covers:
- resolve_trust_level rules (explicit override, source/trusted fallback)
- policy_for matrix (interactive / non-interactive)
- runtime gate: EXPERIMENTAL refused non-interactively, allowed with HITL
  marker in interactive mode
- allow_local_sandbox differentiation per trust level
- CodeAct cache switch plumbing (generate_code_async / run_code_act / runtime)
- frontmatter ``trust_level`` parsing in the loader
- skill_store.trust_skill clearing explicit trust_level overrides
"""

import pytest

from homomics_lab.config import settings
from homomics_lab.execution import code_act
from homomics_lab.execution.code_act import generate_code_async, run_code_act
from homomics_lab.execution.code_cache import CodeActCache
from homomics_lab.skills.loader import SkillLoader
from homomics_lab.skills.models import SkillDefinition, SkillRuntime
from homomics_lab.skills.registry import SkillRegistry
from homomics_lab.skills.runtime import SkillRuntimeExecutor, UntrustedSkillError
from homomics_lab.skills.skill_store import SkillStore
from homomics_lab.skills.trust import TrustLevel, policy_for, resolve_trust_level
from homomics_lab.tools.approval_store import PersistentApprovalStore


def make_skill(**metadata) -> SkillDefinition:
    return SkillDefinition(
        id="test-skill",
        name="test-skill",
        version="1.0.0",
        category="general",
        runtime=SkillRuntime(type="python"),
        metadata=metadata,
    )


class TestResolveTrustLevel:
    def test_builtin_source_is_official(self):
        skill = make_skill(source="builtin", trusted=True)
        assert resolve_trust_level(skill) is TrustLevel.OFFICIAL

    def test_missing_source_defaults_to_official(self):
        skill = make_skill()
        assert resolve_trust_level(skill) is TrustLevel.OFFICIAL

    def test_trusted_community_source_is_community(self):
        skill = make_skill(source="community", trusted=True)
        assert resolve_trust_level(skill) is TrustLevel.COMMUNITY

    def test_trusted_external_source_is_verified(self):
        skill = make_skill(source="external", trusted=True)
        assert resolve_trust_level(skill) is TrustLevel.VERIFIED

    def test_untrusted_external_source_is_experimental(self):
        skill = make_skill(source="external", trusted=False)
        assert resolve_trust_level(skill) is TrustLevel.EXPERIMENTAL

    def test_untrusted_community_source_is_experimental(self):
        skill = make_skill(source="community", trusted=False)
        assert resolve_trust_level(skill) is TrustLevel.EXPERIMENTAL

    def test_explicit_trust_level_wins(self):
        skill = make_skill(source="builtin", trusted=True, trust_level="experimental")
        assert resolve_trust_level(skill) is TrustLevel.EXPERIMENTAL

    def test_explicit_trust_level_case_insensitive(self):
        skill = make_skill(source="external", trust_level=" Official ")
        assert resolve_trust_level(skill) is TrustLevel.OFFICIAL

    def test_invalid_trust_level_ignored(self):
        skill = make_skill(source="builtin", trusted=True, trust_level="bogus")
        assert resolve_trust_level(skill) is TrustLevel.OFFICIAL


class TestPolicyMatrix:
    @pytest.mark.parametrize(
        "level, can_execute, allow_local, require_hitl, use_cache",
        [
            (TrustLevel.OFFICIAL, True, True, False, True),
            (TrustLevel.VERIFIED, True, True, False, True),
            (TrustLevel.COMMUNITY, True, False, False, True),
            (TrustLevel.EXPERIMENTAL, False, False, True, False),
        ],
    )
    def test_non_interactive_matrix(
        self, level, can_execute, allow_local, require_hitl, use_cache
    ):
        policy = policy_for(level, interactive=False)
        assert policy.can_execute is can_execute
        assert policy.allow_local_sandbox is allow_local
        assert policy.require_hitl is require_hitl
        assert policy.use_code_cache is use_cache

    def test_interactive_allows_experimental_execution(self):
        policy = policy_for(TrustLevel.EXPERIMENTAL, interactive=True)
        assert policy.can_execute is True
        assert policy.require_hitl is True
        assert policy.allow_local_sandbox is False
        assert policy.use_code_cache is False

    def test_interactive_leaves_other_levels_unchanged(self):
        for level in (TrustLevel.OFFICIAL, TrustLevel.VERIFIED, TrustLevel.COMMUNITY):
            interactive = policy_for(level, interactive=True)
            non_interactive = policy_for(level, interactive=False)
            assert interactive == non_interactive


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
    (scripts / "core_analysis.py").write_text("result = {'doubled': value * 2}\n")
    return skill_dir


class RecordingScheduler:
    """Fake scheduler capturing the allow_local_sandbox flag."""

    def __init__(self):
        self.allow_local_sandbox_calls = []

    async def execute(
        self,
        skill,
        code,
        inputs,
        timeout_seconds=None,
        parent_job_id=None,
        allow_local_sandbox=False,
    ):
        self.allow_local_sandbox_calls.append(allow_local_sandbox)
        return {"ok": True}


def build_executor(external_skill_dir, tmp_path, monkeypatch, interactive=False, approval_store=None, **metadata):
    monkeypatch.setattr(settings, "interactive_mode", interactive)
    registry = SkillRegistry()
    loader = SkillLoader(registry=registry)
    skill = loader.load_discovery(external_skill_dir)
    skill.metadata.update(metadata)
    registry.register(skill)
    executor = SkillRuntimeExecutor(
        registry=registry, working_dir=tmp_path, approval_store=approval_store
    )
    # These tests assert on dispatch behaviour (scheduler call, HITL tagging);
    # the memoization cache would short-circuit dispatch with cross-test cache
    # hits (same skill content + inputs), so disable it.
    executor.cache = None
    scheduler = RecordingScheduler()
    executor._scheduler = scheduler
    return executor, scheduler


class TestRuntimeTrustGate:
    @pytest.mark.asyncio
    async def test_experimental_rejected_non_interactive(
        self, external_skill_dir, tmp_path, monkeypatch
    ):
        executor, _ = build_executor(
            external_skill_dir, tmp_path, monkeypatch,
            interactive=False, source="external", trusted=False,
        )
        with pytest.raises(UntrustedSkillError, match="experimental"):
            await executor.execute("external-skill", {"value": 5})

    @pytest.mark.asyncio
    async def test_experimental_allowed_interactive_with_hitl_marker(
        self, external_skill_dir, tmp_path, monkeypatch
    ):
        approval_store = PersistentApprovalStore(db_path=tmp_path / "approvals.db")
        executor, scheduler = build_executor(
            external_skill_dir, tmp_path, monkeypatch,
            interactive=True, approval_store=approval_store,
            source="external", trusted=False,
        )
        # Without approval the true HITL gate pauses before dispatch.
        pending = await executor.execute(
            "external-skill", {"value": 5, "_approval_call_id": "hitl-1"}
        )
        assert pending["status"] == "awaiting_human"
        assert pending["mode"] == "awaiting_skill_approval"
        assert scheduler.allow_local_sandbox_calls == []

        # After explicit approval the skill runs and is tagged.
        approval_store.approve(pending["hitl"]["task_id"])
        result = await executor.execute(
            "external-skill", {"value": 5, "_approval_call_id": "hitl-1"}
        )
        assert scheduler.allow_local_sandbox_calls == [False]
        assert result["hitl_required"] is True
        assert result["hitl_approved"] is True
        assert result["trust_level"] == "experimental"

    @pytest.mark.asyncio
    async def test_verified_runs_without_hitl_marker(
        self, external_skill_dir, tmp_path, monkeypatch
    ):
        executor, _ = build_executor(
            external_skill_dir, tmp_path, monkeypatch,
            interactive=False, source="external", trusted=True,
        )
        result = await executor.execute("external-skill", {"value": 5})

        assert "hitl_required" not in result


class TestSandboxAllowLocalByLevel:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "metadata, interactive, expected_allow_local",
        [
            ({"source": "builtin", "trusted": True}, False, True),
            ({"source": "external", "trusted": True}, False, True),
            ({"source": "community", "trusted": True}, False, False),
            ({"source": "external", "trusted": False}, True, False),
        ],
    )
    async def test_allow_local_sandbox_per_level(
        self, external_skill_dir, tmp_path, monkeypatch,
        metadata, interactive, expected_allow_local,
    ):
        approval_store = PersistentApprovalStore(db_path=tmp_path / "approvals.db")
        executor, scheduler = build_executor(
            external_skill_dir, tmp_path, monkeypatch,
            interactive=interactive, approval_store=approval_store, **metadata,
        )
        # EXPERIMENTAL skills in interactive mode must be approved before dispatch.
        if interactive and metadata.get("trusted") is False:
            pending = await executor.execute(
                "external-skill", {"value": 5, "_approval_call_id": "hitl-sandbox"}
            )
            assert pending["status"] == "awaiting_human"
            approval_store.approve(pending["hitl"]["task_id"])

        await executor.execute(
            "external-skill", {"value": 5, "_approval_call_id": "hitl-sandbox"}
        )
        assert scheduler.allow_local_sandbox_calls == [expected_allow_local]


class TestCodeActCacheSwitch:
    @pytest.mark.asyncio
    async def test_use_cache_false_bypasses_code_cache(self, tmp_path, monkeypatch):
        import homomics_lab.execution.code_act as code_act_module

        monkeypatch.setattr(code_act_module, "CODEACT_CACHE_ENABLED", True)
        monkeypatch.setattr(code_act_module, "CODEACT_CACHE_DIR", tmp_path / "cache")

        cache = CodeActCache(tmp_path / "cache")
        cache.put("unique task for trust test", "python", "CACHED_CODE", {})

        # With cache enabled, the cached snippet is returned.
        assert await generate_code_async(
            "unique task for trust test", "python", {}, use_cache=True
        ) == "CACHED_CODE"

        # With cache disabled, code is regenerated and the cache is untouched.
        files_before = sorted((tmp_path / "cache").rglob("*.json"))
        regenerated = await generate_code_async(
            "unique task for trust test", "python", {}, use_cache=False
        )
        assert regenerated != "CACHED_CODE"
        assert sorted((tmp_path / "cache").rglob("*.json")) == files_before

    @pytest.mark.asyncio
    async def test_use_cache_none_follows_settings(self, tmp_path, monkeypatch):
        import homomics_lab.execution.code_act as code_act_module

        monkeypatch.setattr(code_act_module, "CODEACT_CACHE_ENABLED", False)
        monkeypatch.setattr(code_act_module, "CODEACT_CACHE_DIR", tmp_path / "cache")
        code = await generate_code_async("another trust task", "python", {})
        assert "CACHED_CODE" not in code
        assert not (tmp_path / "cache").exists() or not list(
            (tmp_path / "cache").rglob("*.json")
        )

    @pytest.mark.asyncio
    async def test_run_code_act_forwards_use_cache(self, monkeypatch):
        captured = {}

        async def fake_generate(task, language, context, llm_client=None,
                                skill_registry=None, retrieval_context=None,
                                use_cache=None, max_tokens=4000):
            captured["use_cache"] = use_cache
            return "result = None"

        async def fake_execute(code, language, working_dir=None, tool_registry=None,
                               save_artifact=True, on_output_line=None):
            return {
                "success": True, "stdout": "", "stderr": "",
                "exit_code": 0, "result": None,
            }

        monkeypatch.setattr(code_act, "generate_code_async", fake_generate)
        monkeypatch.setattr(code_act, "execute_code", fake_execute)

        await run_code_act("task", use_cache=False)
        assert captured["use_cache"] is False

        await run_code_act("task")
        assert captured["use_cache"] is None

    @pytest.mark.asyncio
    async def test_runtime_passes_policy_cache_flag(self, tmp_path, monkeypatch):
        captured = {}

        class FakeRetriever:
            def __init__(self, **kwargs):
                pass

            async def retrieve(self, **kwargs):
                return None

        async def fake_run_code_act(**kwargs):
            captured.update(kwargs)
            return {
                "code": "", "success": True, "stdout": "", "stderr": "",
                "exit_code": 0, "result": None,
            }

        monkeypatch.setattr(
            "homomics_lab.agent.retrieval.SkillRetriever", FakeRetriever
        )
        monkeypatch.setattr(
            "homomics_lab.skills.runtime.run_code_act", fake_run_code_act
        )

        executor = SkillRuntimeExecutor(registry=SkillRegistry(), working_dir=tmp_path)

        experimental = make_skill(
            source="external", trusted=False, code_act=True, category="general"
        )
        await executor._execute_code_act(experimental, {"task": "t"})
        assert captured["use_cache"] is False

        verified = make_skill(
            source="external", trusted=True, code_act=True, category="general"
        )
        await executor._execute_code_act(verified, {"task": "t"})
        assert captured["use_cache"] is True


class TestFrontmatterTrustLevel:
    def test_valid_trust_level_parsed(self, external_skill_dir):
        (external_skill_dir / "SKILL.md").write_text(
            """\
---
name: external-skill
description: An external skill.
tool_type: python
trust_level: community
---

# Instructions
""",
            encoding="utf-8",
        )
        skill = SkillLoader().load_discovery(external_skill_dir)
        assert skill.metadata["trust_level"] == "community"
        assert resolve_trust_level(skill) is TrustLevel.COMMUNITY

    def test_invalid_trust_level_ignored(self, external_skill_dir):
        (external_skill_dir / "SKILL.md").write_text(
            """\
---
name: external-skill
description: An external skill.
tool_type: python
trust_level: bogus
---

# Instructions
""",
            encoding="utf-8",
        )
        skill = SkillLoader().load_discovery(external_skill_dir)
        assert "trust_level" not in skill.metadata


class TestTrustSkillClearsOverride:
    def test_trust_skill_clears_explicit_trust_level(
        self, external_skill_dir, tmp_path
    ):
        store = SkillStore(store_dir=tmp_path / "store", skills_dir=tmp_path / "skills")
        skill = store.import_skill(str(external_skill_dir), enable=True)
        skill.metadata["trust_level"] = "experimental"
        store._meta[store._meta_key(skill.id, "default")]["trust_level"] = "experimental"

        store.trust_skill(skill.id, trusted=True)

        assert "trust_level" not in store.registry.get(skill.id).metadata
        assert "trust_level" not in store.get_meta(skill.id)
        assert resolve_trust_level(store.registry.get(skill.id)) is TrustLevel.VERIFIED
