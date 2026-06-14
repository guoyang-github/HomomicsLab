"""Tests for context-aware intent analysis."""

import pytest

from homomics_lab.agent.intent.analyzer import CascadeIntentAnalyzer
from homomics_lab.agent.intent.models import IntentDefinition
from homomics_lab.context.working_memory import WorkingMemory
from homomics_lab.models.common import ChatMessage, MessageType


@pytest.fixture
def analyzer():
    return CascadeIntentAnalyzer(
        definitions=[
            IntentDefinition(
                analysis_type="single_cell_analysis",
                keywords=["单细胞"],
                examples=["分析单细胞数据"],
                domain="single_cell",
            ),
        ],
        use_domain_registry=False,
        llm_classifier=None,
    )


@pytest.mark.asyncio
async def test_analyzer_accepts_working_memory(analyzer):
    wm = WorkingMemory()
    wm.add_message(ChatMessage(id="m1", type=MessageType.TEXT, content="加载了 PBMC 数据", sender="user"))
    intent = await analyzer.analyze("帮我分析它", working_memory=wm)
    # Should not crash; context is passed through.
    assert intent.analysis_type in ("single_cell_analysis", "general", "clarification")


def test_build_context_includes_recent_messages(analyzer):
    wm = WorkingMemory()
    wm.add_message(ChatMessage(id="m1", type=MessageType.TEXT, content="msg1", sender="user"))
    wm.add_message(ChatMessage(id="m2", type=MessageType.TEXT, content="msg2", sender="agent"))
    context = analyzer._build_context(wm)
    assert "recent_messages" in context
    assert len(context["recent_messages"]) == 2
