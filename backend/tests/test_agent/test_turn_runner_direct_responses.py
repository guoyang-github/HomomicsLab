"""Tests for LLM-generated direct responses with static-template fallback."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from homomics_lab.agent.intent.models import UserIntent
from homomics_lab.agent.turn_runner import TurnRunner
from homomics_lab.context.working_memory import WorkingMemory
from homomics_lab.models.common import ChatMessage, MessageType


@pytest.fixture
def working_memory():
    return WorkingMemory()


@pytest.fixture
def mock_llm_client():
    client = MagicMock()
    client.chat_completion = AsyncMock(return_value="LLM generated response")
    return client


@pytest.mark.asyncio
async def test_greeting_fallback_when_llm_unavailable(working_memory):
    """Static greeting template is used when no LLM client is configured."""
    runner = TurnRunner(llm_client=None)
    response = await runner._generate_greeting_response(
        "Hello", working_memory, project_id="proj_1"
    )
    assert "HomomicsLab" in response
    assert "bioinformatics" in response


@pytest.mark.asyncio
async def test_qa_fallback_when_llm_unavailable(working_memory):
    """Static QA template is used when no LLM client is configured."""
    runner = TurnRunner(llm_client=None)
    intent = UserIntent(
        analysis_type="qa",
        complexity="direct_response",
        domain="single_cell",
        original_message="什么是单细胞测序？",
    )
    response = await runner._generate_qa_response(
        intent, intent.original_message, working_memory, project_id="proj_1"
    )
    assert "单细胞" in response


@pytest.mark.asyncio
async def test_information_request_fallback_when_llm_unavailable(working_memory):
    """Static information-request template is used when no LLM client is configured."""
    runner = TurnRunner(llm_client=None)
    intent = UserIntent(
        analysis_type="information_request",
        complexity="direct_response",
        domain="single_cell",
        original_message="单细胞分析包括哪些步骤？",
    )
    response = await runner._generate_information_request_response(
        intent, working_memory, project_id="proj_1"
    )
    assert "数据质控" in response


@pytest.mark.asyncio
async def test_greeting_uses_llm_when_available(mock_llm_client, working_memory):
    """LLM response is returned for greetings when the LLM client is available."""
    runner = TurnRunner(llm_client=mock_llm_client)
    response = await runner._generate_greeting_response(
        "Hi there", working_memory, project_id="proj_1"
    )
    assert response == "LLM generated response"
    mock_llm_client.chat_completion.assert_awaited_once()
    call_kwargs = mock_llm_client.chat_completion.await_args.kwargs
    assert call_kwargs.get("temperature") == 0.3
    assert call_kwargs.get("max_tokens") == 800
    messages = call_kwargs.get("messages", [])
    assert any(m.get("role") == "system" and "HomomicsLab" in m.get("content", "") for m in messages)


@pytest.mark.asyncio
async def test_qa_uses_llm_when_available(mock_llm_client, working_memory):
    """LLM response is returned for QA when the LLM client is available."""
    runner = TurnRunner(llm_client=mock_llm_client)
    intent = UserIntent(
        analysis_type="qa",
        complexity="direct_response",
        domain="spatial",
        original_message="什么是空间转录组？",
    )
    response = await runner._generate_qa_response(
        intent, intent.original_message, working_memory, project_id="proj_1"
    )
    assert response == "LLM generated response"
    mock_llm_client.chat_completion.assert_awaited_once()


@pytest.mark.asyncio
async def test_information_request_uses_llm_when_available(mock_llm_client, working_memory):
    """LLM response is returned for information requests when the LLM client is available."""
    runner = TurnRunner(llm_client=mock_llm_client)
    intent = UserIntent(
        analysis_type="information_request",
        complexity="direct_response",
        domain="spatial",
        original_message="空间分析怎么做？",
    )
    response = await runner._generate_information_request_response(
        intent, working_memory, project_id="proj_1"
    )
    assert response == "LLM generated response"
    mock_llm_client.chat_completion.assert_awaited_once()


@pytest.mark.asyncio
async def test_greeting_fallback_when_llm_raises(mock_llm_client, working_memory):
    """Static greeting template is used when the LLM call raises an exception."""
    mock_llm_client.chat_completion = AsyncMock(side_effect=RuntimeError("LLM error"))
    runner = TurnRunner(llm_client=mock_llm_client)
    response = await runner._generate_greeting_response(
        "Hello", working_memory, project_id="proj_1"
    )
    assert "HomomicsLab" in response
    assert "bioinformatics" in response


@pytest.mark.asyncio
async def test_qa_fallback_when_llm_raises(mock_llm_client, working_memory):
    """Static QA template is used when the LLM call raises an exception."""
    mock_llm_client.chat_completion = AsyncMock(side_effect=RuntimeError("LLM error"))
    runner = TurnRunner(llm_client=mock_llm_client)
    intent = UserIntent(
        analysis_type="qa",
        complexity="direct_response",
        domain="metagenomics",
        original_message="什么是宏基因组？",
    )
    response = await runner._generate_qa_response(
        intent, intent.original_message, working_memory, project_id="proj_1"
    )
    assert "宏基因组" in response


@pytest.mark.asyncio
async def test_information_request_fallback_when_llm_raises(mock_llm_client, working_memory):
    """Static information-request template is used when the LLM call raises."""
    mock_llm_client.chat_completion = AsyncMock(side_effect=RuntimeError("LLM error"))
    runner = TurnRunner(llm_client=mock_llm_client)
    intent = UserIntent(
        analysis_type="information_request",
        complexity="direct_response",
        domain="spatial",
        original_message="空间分析有哪些步骤？",
    )
    response = await runner._generate_information_request_response(
        intent, working_memory, project_id="proj_1"
    )
    assert "空间转录组分析" in response


@pytest.mark.asyncio
async def test_direct_response_via_llm_includes_context(
    mock_llm_client, working_memory
):
    """The LLM prompt includes intent, conversation history, and user message."""
    runner = TurnRunner(llm_client=mock_llm_client)
    working_memory.add_message(
        ChatMessage(
            id="msg_0",
            type=MessageType.TEXT,
            content="What is single-cell RNA-seq?",
            sender="user",
        )
    )
    intent = UserIntent(
        analysis_type="qa",
        complexity="direct_response",
        domain="single_cell",
        confidence=0.95,
        original_message="What is single-cell RNA-seq?",
    )
    response = await runner._generate_qa_response(
        intent, intent.original_message, working_memory, project_id="proj_1"
    )
    assert response == "LLM generated response"
    messages = mock_llm_client.chat_completion.await_args.kwargs["messages"]
    content = "\n".join(m.get("content", "") for m in messages)
    assert "single_cell" in content
    assert "0.95" in content
    assert "What is single-cell RNA-seq?" in content
