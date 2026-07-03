"""Tests for the prompt registry and loader."""

import pytest

from homomics_lab.agent.core.dynamic_agent import DynamicAgent
from homomics_lab.agent.core.role import RoleDefinition
from homomics_lab.prompts import (
    get_prompt_registry,
    initialize_prompt_registry,
    load_base_templates,
    load_domain_prompts,
    render_prompt,
)
from homomics_lab.prompts.registry import PromptRegistry


@pytest.fixture(autouse=True)
def _clean_registry():
    """Provide a fresh global registry for each test."""
    registry = get_prompt_registry()
    registry._templates.clear()
    yield
    registry._templates.clear()


class TestPromptRegistry:
    def test_register_and_render(self):
        registry = PromptRegistry()
        registry.register("greeting", "Hello, {{ name }}!")
        assert registry.render("greeting", context={"name": "World"}) == "Hello, World!"

    def test_render_missing_returns_none(self):
        registry = PromptRegistry()
        assert registry.render("missing") is None

    def test_domain_override(self):
        registry = PromptRegistry()
        registry.register("system.base", "Base identity")
        registry.register("system.base", "Single-cell add-on", domain="single_cell")

        assert registry.get("system.base") == "Base identity"
        assert registry.get("system.base", domain="single_cell") == "Single-cell add-on"

    def test_get_combined_base_and_domain(self):
        registry = PromptRegistry()
        registry.register("system.base", "Base identity")
        registry.register("system.base", "Domain guidance", domain="genomics")

        combined = registry.get_combined("system.base", domain="genomics")
        assert "Base identity" in combined
        assert "Domain guidance" in combined

    def test_clear_domain_removes_only_domain_templates(self):
        registry = PromptRegistry()
        registry.register("system.base", "Base identity")
        registry.register("system.base", "Domain guidance", domain="genomics")

        registry.clear_domain("genomics")
        assert registry.get("system.base") == "Base identity"
        # After clearing the domain-specific override, get() falls back to base.
        assert registry.get("system.base", domain="genomics") == "Base identity"

    def test_render_prompt_global_shortcut(self):
        registry = get_prompt_registry()
        registry.register("test.hello", "Hi {{ name }}")
        assert render_prompt("test.hello", context={"name": "Ada"}) == "Hi Ada"


class TestPromptLoader:
    def test_load_base_templates_populates_registry(self):
        registry = PromptRegistry()
        load_base_templates(registry)

        assert registry.get("system.base") is not None
        assert registry.get("system.qa") is not None
        assert registry.get("system.analysis") is not None
        assert registry.get("intent.classification") is not None
        assert registry.get("role.analyst") is not None
        assert registry.get("role.worker") is not None

    def test_load_base_templates_idempotent(self):
        registry = PromptRegistry()
        load_base_templates(registry)
        first = registry.get("system.base")
        load_base_templates(registry)
        assert registry.get("system.base") == first

    def test_load_domain_prompts_flattens_nested_dict(self):
        registry = PromptRegistry()
        load_domain_prompts(
            "single_cell",
            {"system": {"analysis": "Single-cell guidance"}},
            registry=registry,
        )
        assert registry.get("system.analysis", domain="single_cell") == "Single-cell guidance"

    def test_load_domain_prompts_clears_previous_domain_templates(self):
        registry = PromptRegistry()
        load_domain_prompts(
            "single_cell",
            {"system": {"analysis": "Old"}},
            registry=registry,
        )
        load_domain_prompts(
            "single_cell",
            {"system": {"analysis": "New"}},
            registry=registry,
        )
        assert registry.get("system.analysis", domain="single_cell") == "New"

    def test_initialize_prompt_registry_uses_global(self):
        registry = initialize_prompt_registry()
        assert registry is get_prompt_registry()
        assert registry.get("system.base") is not None


class TestDynamicAgentRolePrompt:
    def test_uses_prompt_template_when_configured(self):
        registry = get_prompt_registry()
        registry.register("role.test", "Test role prompt for {{ name }}")
        role = RoleDefinition(
            role_id="test",
            name="Test",
            prompt_template="role.test",
            system_prompt="Fallback",
        )
        agent = DynamicAgent(role=role)
        assert agent.get_system_prompt(context={"name": "Homomics"}) == "Test role prompt for Homomics"

    def test_falls_back_to_system_prompt_when_template_missing(self):
        role = RoleDefinition(
            role_id="test",
            name="Test",
            prompt_template="role.does_not_exist",
            system_prompt="Fallback for {name}",
        )
        agent = DynamicAgent(role=role)
        assert agent.get_system_prompt(context={"name": "Homomics"}) == "Fallback for Homomics"

    def test_falls_back_to_system_prompt_when_no_template(self):
        role = RoleDefinition(
            role_id="test",
            name="Test",
            system_prompt="Static fallback",
        )
        agent = DynamicAgent(role=role)
        assert agent.get_system_prompt() == "Static fallback"

    def test_domain_override_for_role_template(self):
        registry = get_prompt_registry()
        registry.register("role.test", "Base role prompt")
        registry.register("role.test", "Domain-specific guidance", domain="single_cell")
        role = RoleDefinition(
            role_id="test",
            name="Test",
            prompt_template="role.test",
            system_prompt="Fallback",
        )
        agent = DynamicAgent(role=role)
        rendered = agent.get_system_prompt(domain="single_cell")
        assert "Base role prompt" in rendered
        assert "Domain-specific guidance" in rendered
