"""Tests for EpisodicSummarizer throttling and per-session caching."""

import json

import pytest
from unittest.mock import AsyncMock, MagicMock

from homomics_lab.context.episodic_summary import EpisodicSummarizer, EpisodicSummary
from homomics_lab.models.common import ChatMessage, MessageType


def _msgs(n: int):
    return [
        ChatMessage(
            id=str(i),
            type=MessageType.TEXT,
            content=f"user message number {i} about analysis",
            sender="user" if i % 2 == 0 else "agent",
        )
        for i in range(n)
    ]


@pytest.fixture
def llm_client():
    client = MagicMock()
    client.is_configured = MagicMock(return_value=True)
    client.chat_completion = AsyncMock(
        return_value=json.dumps(
            {
                "user_goal": "analyze data",
                "completed_steps": [],
                "pending_steps": [],
                "key_decisions": {},
                "open_questions": [],
                "errors": [],
            }
        )
    )
    return client


@pytest.fixture(autouse=True)
def _default_thresholds(monkeypatch):
    import homomics_lab.context.episodic_summary as episodic_summary_module

    monkeypatch.setattr(episodic_summary_module, "EPISODIC_SUMMARY_MIN_MESSAGES", 6)
    monkeypatch.setattr(episodic_summary_module, "EPISODIC_SUMMARY_MIN_INTERVAL", 3)


@pytest.mark.asyncio
async def test_skips_llm_for_short_sessions(llm_client):
    """Sessions below the min-message threshold must not call the LLM."""
    summarizer = EpisodicSummarizer(llm_client)

    summary = await summarizer.summarize(_msgs(3), session_id="s1", message_count=3)

    assert summary.user_goal == ""
    llm_client.chat_completion.assert_not_called()


@pytest.mark.asyncio
async def test_summarizes_once_threshold_reached(llm_client):
    summarizer = EpisodicSummarizer(llm_client)

    summary = await summarizer.summarize(_msgs(6), session_id="s1", message_count=6)

    assert summary.user_goal == "analyze data"
    assert llm_client.chat_completion.await_count == 1


@pytest.mark.asyncio
async def test_cache_hit_avoids_recompute_until_interval(llm_client):
    """A cached summary is reused until the session grows by >= interval."""
    summarizer = EpisodicSummarizer(llm_client)

    first = await summarizer.summarize(_msgs(6), session_id="s1", message_count=6)
    assert llm_client.chat_completion.await_count == 1

    # +1 and +2 messages: below the interval, reuse the cache.
    second = await summarizer.summarize(_msgs(7), session_id="s1", message_count=7)
    third = await summarizer.summarize(_msgs(8), session_id="s1", message_count=8)
    assert second is first
    assert third is first
    assert llm_client.chat_completion.await_count == 1

    # +3 messages: interval reached, recompute.
    fourth = await summarizer.summarize(_msgs(9), session_id="s1", message_count=9)
    assert llm_client.chat_completion.await_count == 2
    assert fourth.user_goal == "analyze data"


@pytest.mark.asyncio
async def test_cache_is_scoped_per_session(llm_client):
    summarizer = EpisodicSummarizer(llm_client)

    await summarizer.summarize(_msgs(6), session_id="s1", message_count=6)
    await summarizer.summarize(_msgs(6), session_id="s2", message_count=6)

    assert llm_client.chat_completion.await_count == 2


@pytest.mark.asyncio
async def test_short_session_returns_cached_summary(llm_client):
    """After a summary exists, a later read with few windowed messages reuses it."""
    summarizer = EpisodicSummarizer(llm_client)

    computed = await summarizer.summarize(_msgs(6), session_id="s1", message_count=6)
    # Window shrinks below the threshold (e.g. caller passes fewer messages);
    # the cached summary is still returned and the LLM is not called.
    cached = await summarizer.summarize(_msgs(2), session_id="s1", message_count=6)

    assert cached is computed
    assert llm_client.chat_completion.await_count == 1


@pytest.mark.asyncio
async def test_no_llm_client_falls_back_to_rules():
    """Without an injected LLM client the rule-based fallback is used."""
    summarizer = EpisodicSummarizer(None)

    summary = await summarizer.summarize(_msgs(8), session_id="s1", message_count=8)

    assert isinstance(summary, EpisodicSummary)
    assert "user message" in summary.user_goal
