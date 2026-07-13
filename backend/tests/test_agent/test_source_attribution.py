"""Tests for source attribution and anti-hallucination helpers."""

import pytest

from homomics_lab.agent.agent_loop import AgentLoopResult, ToolCallRecord
from homomics_lab.agent.open_agent.executor import OpenAgentExecutor
from homomics_lab.agent.plan.models import DataState, Phase, PlanResult
from homomics_lab.agent.source_attribution import (
    ensure_source_section,
    extract_sources,
    format_source_list,
    source_section_present,
)
from homomics_lab.context.working_memory import WorkingMemory
from homomics_lab.tools.models import ToolResult
from homomics_lab.tools.registry import ToolRegistry


class FakeLLM:
    def __init__(self, response: str = "fake response"):
        self.response = response
        self.calls = []

    def is_configured(self):
        return True

    async def chat_completion(self, **kwargs):
        self.calls.append(kwargs)
        return self.response

    async def chat_completion_message(self, **kwargs):
        from types import SimpleNamespace

        return SimpleNamespace(content=self.response, tool_calls=None), {"cost_usd": 0.0}


def _make_phase(step_type: str, params: dict = None) -> Phase:
    return Phase(
        phase_type=step_type,
        parameters={"open_agent_step_type": step_type, **(params or {})},
    )


def _make_plan(*phases: Phase) -> PlanResult:
    return PlanResult(
        phases=list(phases),
        strategy_name="open-agent",
        data_state=DataState(),
        derivation="open-agent",
    )


class TestExtractSources:
    def test_extracts_url_and_title_from_web_search(self):
        outputs = [
            {
                "count": 2,
                "results": [
                    {"title": "Paper A", "url": "https://example.com/a"},
                    {"title": "Paper B", "url": "https://example.com/b"},
                ],
            }
        ]
        sources = extract_sources(outputs)
        assert len(sources) == 2
        assert sources[0]["type"] == "url"
        assert sources[0]["url"] == "https://example.com/a"
        assert sources[0]["title"] == "Paper A"

    def test_extracts_pmid_and_doi(self):
        outputs = [
            {
                "articles": [
                    {"pmid": "12345", "title": "Article One"},
                    {"doi": "10.1000/x", "title": "Article Two"},
                ]
            }
        ]
        sources = extract_sources(outputs)
        assert len(sources) == 2
        assert sources[0]["type"] == "pmid"
        assert sources[0]["id"] == "12345"
        assert sources[1]["type"] == "doi"
        assert sources[1]["id"] == "10.1000/x"

    def test_deduplicates_by_url(self):
        outputs = [
            {"url": "https://same.org/x", "title": "One"},
            {"url": "https://same.org/x", "title": "Two"},
        ]
        sources = extract_sources(outputs)
        assert len(sources) == 1

    def test_skips_entries_without_identifiers(self):
        outputs = [{"snippet": "some text without source"}]
        sources = extract_sources(outputs)
        assert sources == []


class TestFormatSourceList:
    def test_returns_markdown_block(self):
        sources = [
            {"type": "url", "id": "", "url": "https://example.com", "title": "Example"},
            {"type": "pmid", "id": "123", "url": "", "title": "PubMed"},
        ]
        block = format_source_list(sources)
        assert "### 来源 / Sources" in block
        assert "[Example](https://example.com)" in block
        assert "PMID: 123" in block

    def test_returns_empty_when_no_sources(self):
        assert format_source_list([]) == ""


class TestEnsureSourceSection:
    def test_appends_when_missing(self):
        text = "The answer is 42."
        sources = [{"type": "url", "url": "https://x.com", "title": "X", "id": ""}]
        result = ensure_source_section(text, sources)
        assert "The answer is 42." in result
        assert "### 来源 / Sources" in result

    def test_does_not_append_when_present(self):
        text = "Answer.\n\nSources: https://x.com"
        sources = [{"type": "url", "url": "https://y.com", "title": "Y", "id": ""}]
        result = ensure_source_section(text, sources)
        assert result == text

    def test_returns_original_when_no_sources(self):
        text = "Answer."
        assert ensure_source_section(text, []) == text


class TestSourceSectionPresent:
    def test_detects_chinese_and_english_headers(self):
        assert source_section_present("### 来源：...")
        assert source_section_present("Sources: ...")
        assert source_section_present("References: ...")
        assert not source_section_present("Just an answer.")


@pytest.mark.asyncio
async def test_open_agent_executor_appends_sources_from_explore(monkeypatch):
    """Explore-phase tool outputs are extracted and cited in the final answer."""
    tool_output = {
        "count": 1,
        "results": [
            {"title": "Hallmark paper", "url": "https://pubmed.ncbi.nlm.nih.gov/1"}
        ],
    }

    async def fake_loop_run(*args, **kwargs):
        return AgentLoopResult(
            response_text="Found a hallmark paper.",
            llm_calls=1,
            tool_calls_count=1,
            cost_usd=0.01,
            tool_calls=[
                ToolCallRecord(
                    tool_call_id="tc1",
                    tool_name="science_search",
                    inputs={"query": "hallmark"},
                    success=True,
                    output_summary="1 result",
                    raw_output=tool_output,
                )
            ],
        )

    monkeypatch.setattr(
        "homomics_lab.agent.open_agent.executor.AgentLoop.run", fake_loop_run
    )

    tool_registry = ToolRegistry()
    tool_registry.register_builtin(
        name="science_search",
        description="Search scientific literature",
        handler=lambda **kwargs: ToolResult(success=True, output=tool_output),
    )

    executor = OpenAgentExecutor(
        llm_client=FakeLLM("unused"),
        tool_registry=tool_registry,
    )
    plan = _make_plan(
        _make_phase(
            "explore",
            {"tool_intents": [{"tool_name": "science_search", "inputs": {}, "reason": "search"}]},
        )
    )

    result = await executor.execute(plan, "search hallmark genes", WorkingMemory())

    assert "Found a hallmark paper." in result.response_text
    assert "### 来源 / Sources" in result.response_text
    assert "Hallmark paper" in result.response_text
    assert "https://pubmed.ncbi.nlm.nih.gov/1" in result.response_text
