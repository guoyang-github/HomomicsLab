"""Tests for OpenClaw-style progressive disclosure of skills."""

import pytest

from homomics_lab.skills.loader import DisclosureLevel, SkillLoader
from homomics_lab.skills.models import SkillDefinition
from homomics_lab.skills.registry import SkillRegistry
from homomics_lab.skills.runtime import SkillRuntimeExecutor
from homomics_lab.skills.skill_store import SkillStore


@pytest.fixture
def sample_skill_dir(tmp_path):
    """Create a skill directory with frontmatter, body, scripts, and requirements."""
    skill_dir = tmp_path / "demo-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        """\
---
name: demo-skill
description: A demonstration skill for progressive disclosure.
version: 2.0.0
tool_type: python
primary_tool: test
keywords: ["test", "demo"]
inputs:
  value:
    type: integer
    required: true
---

# Demo Skill

This is the full body that should only appear after activation.

## Steps
1. Read input.
2. Return doubled value.
""",
        encoding="utf-8",
    )
    scripts = skill_dir / "scripts" / "python"
    scripts.mkdir(parents=True)
    (scripts / "core_analysis.py").write_text("result = {'doubled': value * 2}\n")
    (skill_dir / "requirements.txt").write_text("numpy\n")
    return skill_dir


class TestSkillLoaderProgressiveDisclosure:
    def test_load_discovery_reads_only_frontmatter(self, sample_skill_dir):
        loader = SkillLoader()
        skill = loader.load_discovery(sample_skill_dir)

        assert skill.id == "demo-skill"
        assert skill.name == "demo-skill"
        assert skill.description == "A demonstration skill for progressive disclosure."
        assert skill.version == "2.0.0"
        assert skill.runtime.type == "python"
        assert skill.metadata["disclosure_level"] == DisclosureLevel.DISCOVERY
        assert skill.metadata["instructions"] == ""
        assert skill.metadata["scripts_dir"] is None
        assert skill.metadata["source_path"] == str(sample_skill_dir.resolve())
        # Frontmatter-only input schema may be parsed at discovery time; the body
        # and scripts are the only things withheld.
        assert "value" in skill.input_schema.properties

    def test_load_skill_is_fully_activated(self, sample_skill_dir):
        loader = SkillLoader()
        skill = loader.load_skill(sample_skill_dir)

        assert skill.metadata["disclosure_level"] == DisclosureLevel.ACTIVATED
        assert "full body" in skill.metadata["instructions"].lower()
        assert skill.metadata["scripts_dir"] == str(sample_skill_dir / "scripts" / "python")
        assert "numpy" in skill.runtime.dependencies
        assert "value" in skill.input_schema.properties

    def test_activate_mutates_skill_in_place(self, sample_skill_dir):
        loader = SkillLoader()
        skill = loader.load_discovery(sample_skill_dir)
        original_id = id(skill)

        loader.activate(skill)

        assert id(skill) == original_id
        assert skill.metadata["disclosure_level"] == DisclosureLevel.ACTIVATED
        assert "Steps" in skill.metadata["instructions"]
        assert skill.metadata["scripts_dir"] is not None


class TestSkillRegistryActivation:
    def test_registry_activate_loads_full_body(self, sample_skill_dir):
        registry = SkillRegistry()
        loader = SkillLoader(registry=registry)
        skill = loader.load_discovery(sample_skill_dir)
        registry.register(skill)

        activated = registry.activate("demo-skill")

        assert activated is skill
        assert skill.metadata["disclosure_level"] == DisclosureLevel.ACTIVATED
        assert "full body" in skill.metadata["instructions"].lower()

    def test_registry_activate_preserves_id_and_source_overrides(self, sample_skill_dir):
        registry = SkillRegistry()
        loader = SkillLoader()
        skill = loader.load_discovery(sample_skill_dir)
        skill.id = "demo_skill_builtin"
        skill.metadata["source"] = "builtin"
        skill.metadata["namespace"] = "production"
        registry.register(skill)

        registry.activate("demo_skill_builtin")

        assert skill.id == "demo_skill_builtin"
        assert skill.metadata["source"] == "builtin"
        assert skill.metadata["namespace"] == "production"
        assert skill.metadata["disclosure_level"] == DisclosureLevel.ACTIVATED

    def test_registry_activate_programmatic_skill_without_source(self):
        registry = SkillRegistry()
        skill = SkillDefinition(
            id="programmatic",
            name="Programmatic",
            version="1.0",
            category="test",
            metadata={},
        )
        registry.register(skill)

        activated = registry.activate("programmatic")

        assert activated is skill
        assert skill.metadata.get("disclosure_level") == DisclosureLevel.ACTIVATED


class TestSkillRuntimeExecutorActivation:
    @pytest.mark.asyncio
    async def test_executor_auto_activates_discovery_skill(self, sample_skill_dir, tmp_path):
        registry = SkillRegistry()
        loader = SkillLoader(registry=registry)
        skill = loader.load_discovery(sample_skill_dir)
        # Mark as trusted so the executor does not reject the external skill.
        skill.metadata["trusted"] = True
        registry.register(skill)

        executor = SkillRuntimeExecutor(registry=registry, working_dir=tmp_path)
        result = await executor.execute("demo-skill", {"value": 21})

        assert result["doubled"] == 42
        activated = registry.get("demo-skill")
        assert activated.metadata["disclosure_level"] == DisclosureLevel.ACTIVATED
        assert "full body" in activated.metadata["instructions"].lower()


class TestClaudeCodeSkillRendering:
    def test_shell_command_placeholder_replaced(self, tmp_path):
        from homomics_lab.config import settings

        skill_dir = tmp_path / "inject-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            """\
---
name: inject-skill
description: Skill with dynamic context injection.
tool_type: agent
---

## Current status
!`echo hello-from-shell`

## Task
Proceed.
""",
            encoding="utf-8",
        )

        # Enable shell execution and mark the skill as trusted for this test.
        settings.skills_shell_execution_enabled = True
        loader = SkillLoader()
        skill = loader.load_discovery(skill_dir)
        skill.metadata["trusted"] = True
        loader.activate(skill)

        assert "hello-from-shell" in skill.metadata["instructions"]
        assert "!`echo" not in skill.metadata["instructions"]

    def test_argument_substitution(self, tmp_path):
        skill_dir = tmp_path / "arg-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            """\
---
name: arg-skill
description: Skill with arguments.
tool_type: agent
arguments: [component, target]
---

Migrate $0 ($component) to $1 ($target).
""",
            encoding="utf-8",
        )

        loader = SkillLoader()
        skill = loader.load_discovery(skill_dir)
        loader.activate(skill, context={"arguments": "SearchBar Vue"})

        instructions = skill.metadata["instructions"]
        assert "Migrate SearchBar (SearchBar) to Vue (Vue)" in instructions

    def test_multiline_shell_block_replaced(self, tmp_path):
        from homomics_lab.config import settings

        skill_dir = tmp_path / "block-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            """\
---
name: block-skill
description: Skill with multiline shell block.
tool_type: agent
---

## Env
```!
echo line1
echo line2
```

Done.
""",
            encoding="utf-8",
        )

        settings.skills_shell_execution_enabled = True
        loader = SkillLoader()
        skill = loader.load_discovery(skill_dir)
        skill.metadata["trusted"] = True
        loader.activate(skill)

        instructions = skill.metadata["instructions"]
        assert "line1" in instructions
        assert "line2" in instructions
        assert "```!" not in instructions


class TestAgentSkillExecutorToolPolicy:
    def test_allowed_tools_restricts_available_tools(self):
        from homomics_lab.skills.agent_executor import AgentSkillExecutor
        from homomics_lab.tools.registry import ToolRegistry
        from homomics_lab.tools.models import ToolDefinition

        tool_registry = ToolRegistry()
        tool_registry.register(
            ToolDefinition(
                name="file_read",
                description="Read a file.",
                handler=lambda _: None,
                input_schema={"type": "object"},
            )
        )
        tool_registry.register(
            ToolDefinition(
                name="shell_exec",
                description="Run a shell command.",
                handler=lambda _: None,
                input_schema={"type": "object"},
            )
        )

        skill = SkillDefinition(
            id="restricted",
            name="Restricted",
            version="1.0",
            category="test",
            runtime={"type": "agent"},
            metadata={"allowed_tools": ["file_read"]},
        )

        executor = AgentSkillExecutor(tool_registry=tool_registry)
        tools = executor._available_tools(skill)

        assert set(tools.keys()) == {"file_read"}

    def test_disallowed_tools_remove_tools(self):
        from homomics_lab.skills.agent_executor import AgentSkillExecutor
        from homomics_lab.tools.registry import ToolRegistry
        from homomics_lab.tools.models import ToolDefinition

        tool_registry = ToolRegistry()
        tool_registry.register(
            ToolDefinition(
                name="file_read",
                description="Read a file.",
                handler=lambda _: None,
                input_schema={"type": "object"},
            )
        )
        tool_registry.register(
            ToolDefinition(
                name="shell_exec",
                description="Run a shell command.",
                handler=lambda _: None,
                input_schema={"type": "object"},
            )
        )

        skill = SkillDefinition(
            id="blocked",
            name="Blocked",
            version="1.0",
            category="test",
            runtime={"type": "agent"},
            metadata={"disallowed_tools": "shell_exec"},
        )

        executor = AgentSkillExecutor(tool_registry=tool_registry)
        tools = executor._available_tools(skill)

        assert "shell_exec" not in tools
        assert "file_read" in tools


class TestSkillStoreValidationScriptsOptional:
    def test_python_skill_without_scripts_is_valid(self, tmp_path):
        skill_dir = tmp_path / "declarative_python"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            """\
---
name: declarative-python
description: A python skill with no scripts.
tool_type: python
---

# Instructions
Just use CodeAct.
""",
            encoding="utf-8",
        )

        report = SkillStore.validate_skill(skill_dir)

        assert report.valid is True
        assert not any("scripts/" in w.lower() for w in report.warnings)


