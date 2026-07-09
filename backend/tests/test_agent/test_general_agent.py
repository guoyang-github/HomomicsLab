"""Tests for the general scientific agent mode."""

import pytest

from homomics_lab.agent.general_agent import GeneralScientificAgent
from homomics_lab.agent.intent import UserIntent
from homomics_lab.agent.turn_runner import ExecutionMode
from homomics_lab.context.working_memory import WorkingMemory


class FakeLLM:
    def is_configured(self):
        return True

    async def chat_completion(self, **kwargs):
        return "Fake answer"


@pytest.fixture
def agent():
    return GeneralScientificAgent(llm_client=FakeLLM())


@pytest.mark.asyncio
async def test_qa_returns_direct_response(agent):
    intent = UserIntent(
        analysis_type="qa",
        complexity="direct_response",
        original_message="什么是 UMAP？",
    )
    wm = WorkingMemory()

    result = await agent.answer(intent, wm)

    assert result.mode == ExecutionMode.DIRECT_RESPONSE
    assert result.response_text == "Fake answer"


@pytest.mark.asyncio
async def test_information_request_returns_direct_response(agent):
    intent = UserIntent(
        analysis_type="information_request",
        complexity="direct_response",
        original_message="单细胞有哪些分析内容？",
    )
    wm = WorkingMemory()

    result = await agent.answer(intent, wm)

    assert result.mode == ExecutionMode.DIRECT_RESPONSE


@pytest.mark.asyncio
async def test_general_help_returns_direct_response(agent):
    intent = UserIntent(
        analysis_type="general_help",
        complexity="single_step",
        original_message="帮我写个 Python 脚本过滤 CSV",
    )
    wm = WorkingMemory()

    result = await agent.answer(intent, wm)

    assert result.mode == ExecutionMode.DIRECT_RESPONSE


@pytest.mark.asyncio
async def test_unconfigured_llm_returns_fallback_message():
    class UnconfiguredLLM:
        def is_configured(self):
            return False

    agent = GeneralScientificAgent(llm_client=UnconfiguredLLM())
    intent = UserIntent(
        analysis_type="qa",
        complexity="direct_response",
        original_message="什么是 UMAP？",
    )
    wm = WorkingMemory()

    result = await agent.answer(intent, wm)

    assert result.mode == ExecutionMode.DIRECT_RESPONSE
    assert "未配置 LLM" in result.response_text
