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


class StreamingFakeLLM(FakeLLM):
    """Fake LLM that also supports token streaming."""

    def __init__(self, chunks=("Fake", " answer")):
        self.chunks = list(chunks)
        self.one_shot_called = False

    async def chat_completion(self, **kwargs):
        self.one_shot_called = True
        return "Fake answer"

    async def chat_completion_stream(self, **kwargs):
        for chunk in self.chunks:
            yield chunk


class FailingStreamFakeLLM(StreamingFakeLLM):
    """Stream raises immediately; one-shot completion still works."""

    async def chat_completion_stream(self, **kwargs):
        raise RuntimeError("stream unsupported")
        yield  # pragma: no cover - keeps this an async generator


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


@pytest.mark.asyncio
async def test_direct_answer_streams_tokens_via_event_callback():
    """With an event callback, tokens stream live and the full text is returned."""
    llm = StreamingFakeLLM()
    agent = GeneralScientificAgent(llm_client=llm)
    intent = UserIntent(
        analysis_type="qa",
        complexity="direct_response",
        original_message="什么是 UMAP？",
    )
    wm = WorkingMemory()
    events = []

    async def cb(payload):
        events.append(payload)

    result = await agent.answer(intent, wm, event_callback=cb)

    assert result.mode == ExecutionMode.DIRECT_RESPONSE
    assert result.response_text == "Fake answer"
    # Tokens were forwarded in order, then a single done marker.
    token_events = [e["token"] for e in events if e["type"] == "answer_token"]
    assert token_events == ["Fake", " answer"]
    assert [e["type"] for e in events][-1] == "answer_done"
    # The one-shot completion was NOT used.
    assert llm.one_shot_called is False
    # The persisted agent message carries the complete text.
    assert wm.messages[-1].content == "Fake answer"


@pytest.mark.asyncio
async def test_direct_answer_stream_failure_falls_back_to_one_shot():
    """A failing stream falls back to the classic one-shot completion."""
    llm = FailingStreamFakeLLM()
    agent = GeneralScientificAgent(llm_client=llm)
    intent = UserIntent(
        analysis_type="qa",
        complexity="direct_response",
        original_message="什么是 UMAP？",
    )
    wm = WorkingMemory()
    events = []

    async def cb(payload):
        events.append(payload)

    result = await agent.answer(intent, wm, event_callback=cb)

    assert result.response_text == "Fake answer"
    assert llm.one_shot_called is True
    # Listeners were told to discard any partial tokens.
    assert any(e["type"] == "answer_reset" for e in events)
    assert not any(e["type"] == "answer_token" for e in events)


@pytest.mark.asyncio
async def test_direct_answer_without_callback_keeps_one_shot_path():
    """No event callback: behaviour is byte-identical to the classic path."""
    llm = StreamingFakeLLM()
    agent = GeneralScientificAgent(llm_client=llm)
    intent = UserIntent(
        analysis_type="qa",
        complexity="direct_response",
        original_message="什么是 UMAP？",
    )
    wm = WorkingMemory()

    result = await agent.answer(intent, wm)

    assert result.response_text == "Fake answer"
    assert llm.one_shot_called is True
