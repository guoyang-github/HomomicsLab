"""Tests for open exploration mode routing and settings."""

import pytest

from homomics_lab.agent.intent import UserIntent
from homomics_lab.agent.plan.capability_assembler import CapabilityAssembler
from homomics_lab.agent.plan.models import DataState
from homomics_lab.agent.plan.template import AnalysisTemplate
from homomics_lab.config import Settings


@pytest.fixture
def assembler_open():
    settings = Settings()
    settings.open_exploration_mode_enabled = True
    return CapabilityAssembler(settings=settings)


@pytest.fixture
def assembler_closed():
    settings = Settings()
    settings.open_exploration_mode_enabled = False
    return CapabilityAssembler(settings=settings)


@pytest.mark.asyncio
async def test_open_exploration_routes_weak_domain_to_open_agent(assembler_open):
    # Coverage is 0.5 (two of four applicable tokens match), below the normal
    # 0.7 threshold but above the open-exploration 0.45 threshold.
    intent = UserIntent(
        analysis_type="analysis",
        domain="single-cell-transcriptomics",
        complexity="multi_step",
        original_message="single-cell analysis",
    )

    class FakeTemplateStore:
        def list_templates(self):
            return [
                AnalysisTemplate(
                    template_id="sc",
                    name="Single-cell",
                    domain="single-cell-transcriptomics",
                    applicable_intents=["single-cell analysis clustering annotation"],
                )
            ]

    assembler_open.template_store = FakeTemplateStore()
    decision = await assembler_open.assemble(intent, data_state=DataState())
    assert decision.route == "open_agent"
    assert "Weak domain signal" in decision.reason


@pytest.mark.asyncio
async def test_closed_mode_keeps_strong_domain_template(assembler_closed):
    # Full match keeps the request on the domain template path.
    intent = UserIntent(
        analysis_type="analysis",
        domain="single-cell-transcriptomics",
        complexity="multi_step",
        original_message="single-cell analysis clustering annotation",
    )

    class FakeTemplateStore:
        def list_templates(self):
            return [
                AnalysisTemplate(
                    template_id="sc",
                    name="Single-cell",
                    domain="single-cell-transcriptomics",
                    applicable_intents=["single-cell analysis clustering annotation"],
                )
            ]

    assembler_closed.template_store = FakeTemplateStore()
    decision = await assembler_closed.assemble(intent, data_state=DataState())
    assert decision.route == "domain_template"


@pytest.mark.asyncio
async def test_open_exploration_prefers_open_agent_for_uncertain_standalone(assembler_open):
    intent = UserIntent(
        analysis_type="general_help",
        domain=None,
        complexity="direct_response",
        original_message="run some tool",
    )
    decision = await assembler_open.assemble(intent, data_state=DataState())
    assert decision.route == "open_agent"


def test_config_default_is_disabled():
    settings = Settings()
    assert settings.open_exploration_mode_enabled is False


def test_settings_runtime_whitelist(monkeypatch, tmp_path):
    from homomics_lab.settings_store import save_runtime_settings

    monkeypatch.setattr("homomics_lab.config.settings.data_dir", tmp_path)
    validated = save_runtime_settings({"open_exploration_mode_enabled": True})
    assert validated.open_exploration_mode_enabled is True
