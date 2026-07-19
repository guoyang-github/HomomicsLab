"""Tests for capability-assembler routing with open exploration fixed off."""

import pytest

from homomics_lab.agent.intent import UserIntent
from homomics_lab.agent.plan.capability_assembler import (
    OPEN_EXPLORATION_MODE_ENABLED,
    CapabilityAssembler,
)
from homomics_lab.agent.plan.models import DataState
from homomics_lab.agent.plan.template import AnalysisTemplate


@pytest.fixture
def assembler():
    return CapabilityAssembler()


def test_open_exploration_constant_is_disabled():
    # Open exploration routing is a product decision, not a config knob.
    assert OPEN_EXPLORATION_MODE_ENABLED is False


@pytest.mark.asyncio
async def test_strong_domain_keeps_template(assembler):
    # Full match keeps the request on the domain template path.
    intent = UserIntent(
        intent_type="analysis", interaction_mode="execute", domain="single-cell-transcriptomics",
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

    assembler.template_store = FakeTemplateStore()
    decision = await assembler.assemble(intent, data_state=DataState())
    assert decision.route == "domain_template"


@pytest.mark.asyncio
async def test_weak_domain_does_not_route_to_open_agent(assembler):
    # With open exploration off, a weak domain match must not be rerouted to
    # the open agent by the exploration gate.
    intent = UserIntent(
        intent_type="analysis", interaction_mode="execute", domain="single-cell-transcriptomics",
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

    assembler.template_store = FakeTemplateStore()
    decision = await assembler.assemble(intent, data_state=DataState())
    assert not (
        decision.route == "open_agent" and "Weak domain signal" in (decision.reason or "")
    )
