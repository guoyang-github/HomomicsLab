"""Tests for DomainRegistry."""

import pytest

from homomics_lab.domain.models import DomainDefinition
from homomics_lab.domain.registry import DomainRegistry


class TestDomainRegistry:
    def test_register_and_get(self):
        registry = DomainRegistry()
        domain = DomainDefinition(domain="test", description="Test domain")
        registry.register(domain)

        retrieved = registry.get("test")
        assert retrieved is not None
        assert retrieved.domain == "test"

    def test_get_nonexistent(self):
        registry = DomainRegistry()
        assert registry.get("nonexistent") is None

    def test_list_all(self):
        registry = DomainRegistry()
        registry.register(DomainDefinition(domain="a"))
        registry.register(DomainDefinition(domain="b"))

        domains = registry.list_all()
        assert len(domains) == 2
        names = {d.domain for d in domains}
        assert names == {"a", "b"}

    def test_unregister(self):
        registry = DomainRegistry()
        registry.register(DomainDefinition(domain="test"))
        assert registry.get("test") is not None

        result = registry.unregister("test")
        assert result is True
        assert registry.get("test") is None

    def test_unregister_nonexistent(self):
        registry = DomainRegistry()
        assert registry.unregister("nonexistent") is False

    def test_get_intent_config(self):
        registry = DomainRegistry()
        registry.register(
            DomainDefinition(
                domain="metagenomics",
                intents=[
                    {
                        "analysis_type": "metagenomics_analysis",
                        "keywords": ["16S"],
                        "complexity_indicators": [],
                        "data_scale_patterns": [],
                    }
                ],
            )
        )

        config = registry.get_intent_config()
        assert "metagenomics_analysis" in config
        assert config["metagenomics_analysis"]["keywords"] == ["16S"]

    def test_get_all_keywords(self):
        registry = DomainRegistry()
        registry.register(
            DomainDefinition(
                domain="test",
                intents=[
                    {"analysis_type": "type_a", "keywords": ["kw1", "kw2"]},
                ],
            )
        )

        keywords = registry.get_all_keywords()
        assert keywords["type_a"] == ["kw1", "kw2"]

    def test_get_phase_types(self):
        registry = DomainRegistry()
        registry.register(
            DomainDefinition(
                domain="test",
                phases=[
                    {"id": "qc"},
                    {"id": "denoising"},
                ],
            )
        )

        phase_types = registry.get_phase_types()
        assert phase_types["test"] == ["qc", "denoising"]

    def test_get_roles(self):
        registry = DomainRegistry()
        registry.register(
            DomainDefinition(
                domain="test",
                roles=[
                    {
                        "role_id": "specialist",
                        "name": "Specialist",
                        "allowed_skills": ["skill1"],
                        "allowed_tools": [],
                        "permissions": {},
                        "priority": 2,
                    }
                ],
            )
        )

        roles = registry.get_roles()
        assert "specialist" in roles
        assert roles["specialist"]["name"] == "Specialist"

    def test_contains(self):
        registry = DomainRegistry()
        registry.register(DomainDefinition(domain="test"))
        assert "test" in registry
        assert "nonexistent" not in registry

    def test_len(self):
        registry = DomainRegistry()
        assert len(registry) == 0
        registry.register(DomainDefinition(domain="a"))
        assert len(registry) == 1

    def test_reload(self):
        import tempfile
        from pathlib import Path

        import yaml
        from homomics_lab.domain.loader import DomainLoader
        from homomics_lab.skills.registry import SkillRegistry
        from homomics_lab.agent.plan.strategies import StrategyLibrary

        with tempfile.TemporaryDirectory() as tmpdir:
            domain_path = Path(tmpdir) / "domain.yaml"
            with open(domain_path, "w") as f:
                yaml.dump({"domain": "reload_test", "description": "v1"}, f)

            registry = DomainRegistry()
            skill_reg = SkillRegistry()
            lib = StrategyLibrary()
            loader = DomainLoader(skill_reg, lib)
            domain = loader.load(domain_path)
            registry.register(domain, loader, domain_path)

            # Modify the file
            with open(domain_path, "w") as f:
                yaml.dump({"domain": "reload_test", "description": "v2"}, f)

            # Reload
            reloaded = registry.reload("reload_test")
            assert reloaded is not None
            assert reloaded.description == "v2"
