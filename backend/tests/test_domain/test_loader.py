"""Tests for DomainLoader."""

import tempfile
from pathlib import Path

import pytest
import yaml

from homomics_lab.domain.loader import DomainLoader, DomainLoaderError, DomainValidator
from homomics_lab.domain.models import DomainDefinition
from homomics_lab.agent.plan.strategies import StrategyLibrary
from homomics_lab.skills.registry import SkillRegistry


class TestDomainValidator:
    def test_empty_domain_is_valid(self):
        registry = SkillRegistry()
        lib = StrategyLibrary()
        validator = DomainValidator(registry, lib)
        domain = DomainDefinition(domain="test", description="test")
        errors = validator.validate(domain)
        assert errors == []

    def test_unknown_skill_reference_is_warning(self):
        registry = SkillRegistry()
        lib = StrategyLibrary()
        validator = DomainValidator(registry, lib)
        domain = DomainDefinition(
            domain="test",
            phases=[
                {"id": "qc", "skills": ["nonexistent_skill"]},
            ],
        )
        issues = validator.validate(domain)
        assert any("nonexistent_skill" in i.message for i in issues)
        assert all(i.severity == "warning" for i in issues if "nonexistent_skill" in i.message)

    def test_unknown_phase_target_is_error(self):
        registry = SkillRegistry()
        lib = StrategyLibrary()
        validator = DomainValidator(registry, lib)
        domain = DomainDefinition(
            domain="test",
            phases=[{"id": "qc"}],
            state_checks=[
                {"condition": "x > 1", "action": "skip", "target": "unknown_phase"},
            ],
        )
        issues = validator.validate(domain)
        assert any("unknown_phase" in i.message for i in issues)
        assert any(i.severity == "error" and "unknown_phase" in i.message for i in issues)


class TestDomainLoader:
    def test_load_minimal_domain_yaml(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            domain_path = Path(tmpdir) / "domain.yaml"
            domain_data = {
                "domain": "test_domain",
                "description": "Test domain",
                "version": "1.0.0",
                "phases": [{"id": "qc", "required": True}],
                "intents": [
                    {
                        "analysis_type": "test_analysis",
                        "keywords": ["test"],
                    }
                ],
            }
            with open(domain_path, "w") as f:
                yaml.dump(domain_data, f)

            registry = SkillRegistry()
            lib = StrategyLibrary()
            loader = DomainLoader(registry, lib)
            domain = loader.load(domain_path)

            assert domain.domain == "test_domain"
            assert len(domain.phases) == 1
            assert domain.phases[0].id == "qc"

    def test_load_invalid_yaml_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            domain_path = Path(tmpdir) / "domain.yaml"
            domain_path.write_text("invalid: yaml: [")

            registry = SkillRegistry()
            lib = StrategyLibrary()
            loader = DomainLoader(registry, lib)

            with pytest.raises(DomainLoaderError):
                loader.load(domain_path)

    def test_load_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create two domain directories
            for name in ["domain_a", "domain_b"]:
                d = Path(tmpdir) / name
                d.mkdir()
                with open(d / "domain.yaml", "w") as f:
                    yaml.dump(
                        {"domain": name, "description": f"{name} desc"}, f
                    )

            registry = SkillRegistry()
            lib = StrategyLibrary()
            loader = DomainLoader(registry, lib)
            domains = loader.load_directory(Path(tmpdir))

            assert len(domains) == 2
            domain_names = {d.domain for d in domains}
            assert domain_names == {"domain_a", "domain_b"}

    def test_build_strategy_from_domain(self):
        domain = DomainDefinition(
            domain="metagenomics",
            description="Test metagenomics",
            phases=[
                {"id": "qc", "required": True},
                {"id": "denoising", "required": True},
            ],
            state_checks=[
                {
                    "condition": "n_samples < 3",
                    "action": "skip",
                    "target": "diversity",
                },
            ],
            intents=[
                {
                    "analysis_type": "metagenomics_analysis",
                    "keywords": ["16S"],
                }
            ],
        )

        registry = SkillRegistry()
        lib = StrategyLibrary()
        loader = DomainLoader(registry, lib)
        strategy = loader._build_strategy(domain)

        assert strategy.name == "metagenomics"
        assert len(strategy.skeleton) == 2
        assert strategy.skeleton[0].phase_type == "qc"
        assert "metagenomics_analysis" in strategy.applicable_intents
        assert "16S" in strategy.applicable_intents

    def test_compile_state_condition(self):
        from homomics_lab.agent.plan.models import DataState

        registry = SkillRegistry()
        lib = StrategyLibrary()
        loader = DomainLoader(registry, lib)

        # Simple condition
        cond = loader._compile_state_condition("batch_detected")
        ds_true = DataState(batch_detected=True)
        ds_false = DataState(batch_detected=False)
        assert cond(ds_true) is True
        assert cond(ds_false) is False

        # Comparison condition
        cond2 = loader._compile_state_condition("n_samples < 3")
        ds_small = DataState(n_samples=2)
        ds_large = DataState(n_samples=10)
        assert cond2(ds_small) is True
        assert cond2(ds_large) is False

    def test_generate_intent_config(self):
        domain = DomainDefinition(
            domain="test",
            intents=[
                {
                    "analysis_type": "type_a",
                    "keywords": ["kw1"],
                    "complexity_indicators": ["complex"],
                }
            ],
        )

        registry = SkillRegistry()
        lib = StrategyLibrary()
        loader = DomainLoader(registry, lib)
        config = loader.generate_intent_config(domain)

        assert config["domain"] == "test"
        assert "type_a" in config["analysis_types"]
        assert config["analysis_types"]["type_a"]["keywords"] == ["kw1"]


    def test_lenient_load_keeps_domain_when_skill_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            domain_path = Path(tmpdir) / "domain.yaml"
            domain_data = {
                "domain": "soft_domain",
                "description": "Domain with missing skill",
                "phases": [
                    {"id": "qc", "skills": ["known_skill", "missing_skill"]},
                    {"id": "analysis", "skills": ["missing_skill"]},
                ],
            }
            with open(domain_path, "w") as f:
                yaml.dump(domain_data, f)

            registry = SkillRegistry()
            lib = StrategyLibrary()
            loader = DomainLoader(registry, lib, strict=False)
            domain = loader.load(domain_path)

            assert domain.domain == "soft_domain"
            assert len(domain.phases) == 2
            qc_phase = next(p for p in domain.phases if p.id == "qc")
            analysis_phase = next(p for p in domain.phases if p.id == "analysis")

            # known_skill is not in registry either, so both phases lose skills
            assert qc_phase.skills == []
            assert qc_phase.unresolvable is True
            assert analysis_phase.unresolvable is True
            assert any("missing_skill" in w for w in domain.warnings)

    def test_strict_load_fails_on_missing_skill(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            domain_path = Path(tmpdir) / "domain.yaml"
            domain_data = {
                "domain": "strict_domain",
                "phases": [
                    {"id": "qc", "skills": ["missing_skill"]},
                ],
            }
            with open(domain_path, "w") as f:
                yaml.dump(domain_data, f)

            registry = SkillRegistry()
            lib = StrategyLibrary()
            loader = DomainLoader(registry, lib, strict=True)

            with pytest.raises(DomainLoaderError):
                loader.load(domain_path)

    def test_hard_errors_still_fail_in_lenient_mode(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            domain_path = Path(tmpdir) / "domain.yaml"
            domain_data = {
                "domain": "bad_domain",
                "phases": [{"id": "qc"}],
                "state_checks": [
                    {"condition": "x > 1", "action": "skip", "target": "missing_phase"},
                ],
            }
            with open(domain_path, "w") as f:
                yaml.dump(domain_data, f)

            registry = SkillRegistry()
            lib = StrategyLibrary()
            loader = DomainLoader(registry, lib, strict=False)

            with pytest.raises(DomainLoaderError):
                loader.load(domain_path)
