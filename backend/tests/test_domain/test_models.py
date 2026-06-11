"""Tests for domain declaration models."""

import pytest
from pydantic import ValidationError

from homomics_lab.domain.models import (
    DomainDAGSeed,
    DomainDefinition,
    DomainIntent,
    DomainPhase,
    DomainRole,
    DomainSOP,
    DomainStateCheck,
)


class TestDomainPhase:
    def test_basic_phase(self):
        phase = DomainPhase(id="qc", required=True, description="Quality control")
        assert phase.id == "qc"
        assert phase.required is True
        assert phase.description == "Quality control"

    def test_phase_with_skills(self):
        phase = DomainPhase(
            id="denoising",
            skills=["metagenomics_denoise", "metagenomics_dada2"],
            default_skill="metagenomics_denoise",
        )
        assert phase.skills == ["metagenomics_denoise", "metagenomics_dada2"]
        assert phase.default_skill == "metagenomics_denoise"


class TestDomainStateCheck:
    def test_basic_check(self):
        check = DomainStateCheck(
            condition="host_contamination > 0.1",
            action="insert",
            target="dehost",
            after="qc",
        )
        assert check.condition == "host_contamination > 0.1"
        assert check.action == "insert"
        assert check.target == "dehost"
        assert check.after == "qc"

    def test_skip_check(self):
        check = DomainStateCheck(
            condition="n_samples < 3",
            action="skip",
            target="diversity",
        )
        assert check.action == "skip"
        assert check.value is None

    def test_modify_param_check(self):
        check = DomainStateCheck(
            condition="low_quality",
            action="modify_param",
            target="denoising",
            value={"max_ee": 1},
        )
        assert check.value == {"max_ee": 1}


class TestDomainIntent:
    def test_basic_intent(self):
        intent = DomainIntent(
            analysis_type="metagenomics_analysis",
            keywords=["宏基因组", "16S", "microbiome"],
            complexity_indicators=["全流程", "pipeline"],
        )
        assert intent.analysis_type == "metagenomics_analysis"
        assert "16S" in intent.keywords


class TestDomainDAGSeed:
    def test_basic_seed(self):
        seed = DomainDAGSeed(
            **{"from": "metagenomics_qc", "to": "metagenomics_denoise",
               "type": "followed_by", "context": "QC → denoising"}
        )
        assert seed.from_skill == "metagenomics_qc"
        assert seed.to_skill == "metagenomics_denoise"
        assert seed.type == "followed_by"


class TestDomainRole:
    def test_basic_role(self):
        role = DomainRole(
            role_id="metagenomicist",
            name="Metagenomicist",
            allowed_skills=["metagenomics_qc"],
            allowed_tools=["file_read", "shell_exec"],
            permissions={"can_execute": True},
            priority=2,
        )
        assert role.role_id == "metagenomicist"
        assert role.priority == 2


class TestDomainDefinition:
    def test_minimal_domain(self):
        domain = DomainDefinition(
            domain="test_domain",
            description="Test domain",
        )
        assert domain.domain == "test_domain"
        assert domain.phases == []
        assert domain.state_checks == []

    def test_full_domain(self):
        domain = DomainDefinition(
            domain="metagenomics_16s",
            description="16S amplicon analysis",
            version="1.0.0",
            phases=[
                DomainPhase(id="qc", required=True),
                DomainPhase(id="denoising", required=True),
            ],
            state_checks=[
                DomainStateCheck(
                    condition="host_contamination > 0.1",
                    action="insert",
                    target="dehost",
                    after="qc",
                ),
            ],
            intents=[
                DomainIntent(
                    analysis_type="metagenomics_analysis",
                    keywords=["16S", "microbiome"],
                ),
            ],
            dag_seeds=[
                DomainDAGSeed(
                    **{"from": "qc", "to": "denoising", "type": "followed_by"}
                ),
            ],
            roles=[
                DomainRole(role_id="metagenomicist", name="Metagenomicist"),
            ],
            sops=[
                DomainSOP(id="sop_1", title="Test SOP"),
            ],
        )
        assert len(domain.phases) == 2
        assert len(domain.state_checks) == 1
        assert len(domain.intents) == 1
        assert len(domain.dag_seeds) == 1
        assert len(domain.roles) == 1
        assert len(domain.sops) == 1

    def test_get_intent_keywords(self):
        domain = DomainDefinition(
            domain="test",
            intents=[
                DomainIntent(
                    analysis_type="type_a",
                    keywords=["kw1", "kw2"],
                ),
                DomainIntent(
                    analysis_type="type_b",
                    keywords=["kw3"],
                ),
            ],
        )
        keywords = domain.get_intent_keywords()
        assert keywords["type_a"] == ["kw1", "kw2"]
        assert keywords["type_b"] == ["kw3"]

    def test_get_phase_types(self):
        domain = DomainDefinition(
            domain="test",
            phases=[
                DomainPhase(id="qc"),
                DomainPhase(id="denoising"),
                DomainPhase(id="taxonomy"),
            ],
        )
        assert domain.get_phase_types() == ["qc", "denoising", "taxonomy"]

    def test_invalid_action_raises(self):
        with pytest.raises(ValidationError):
            DomainStateCheck(
                condition="x > 1",
                action="invalid_action",
                target="phase",
            )
