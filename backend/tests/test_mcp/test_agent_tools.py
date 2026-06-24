"""Tests for MCP tool invocation from the agent TurnRunner."""

import pytest

from homomics_lab.agent.intent.analyzer import CascadeIntentAnalyzer
from homomics_lab.agent.turn_runner import ExecutionMode, TurnRunner
from homomics_lab.context.working_memory import WorkingMemory
from homomics_lab.tools.registry import ToolRegistry


@pytest.fixture
def tool_registry(monkeypatch):
    """Registry with MCP tool handlers bound to a mocked client."""
    registry = ToolRegistry()

    async def fake_pubmed_search(query: str, retmax: int = 10):
        return {"count": "1", "ids": ["12345"], "articles": [{"title": f"Result for {query}"}]}

    registry.register_builtin(
        name="pubmed_search",
        description="Search PubMed",
        handler=fake_pubmed_search,
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "retmax": {"type": "integer"},
            },
            "required": ["query"],
        },
    )
    return registry


@pytest.mark.asyncio
async def test_intent_recognizes_pubmed_search():
    analyzer = CascadeIntentAnalyzer(use_domain_registry=False)
    intent = await analyzer.analyze("帮我搜索 PubMed 单细胞 RNA-seq")
    assert intent.analysis_type == "pubmed_search"
    assert intent.complexity == "direct_response"
    assert intent.metadata["tool_name"] == "pubmed_search"
    assert "单细胞" in intent.metadata["tool_inputs"]["query"]


@pytest.mark.asyncio
async def test_intent_recognizes_pubmed_fetch():
    analyzer = CascadeIntentAnalyzer(use_domain_registry=False)
    intent = await analyzer.analyze("查一下 pmid 12345 的摘要")
    assert intent.analysis_type == "pubmed_fetch"
    assert intent.metadata["tool_inputs"]["pmid"] == "12345"


@pytest.mark.asyncio
async def test_turn_runner_invokes_mcp_tool(tool_registry):
    runner = TurnRunner(tool_registry=tool_registry)
    wm = WorkingMemory()

    result = await runner.run_turn(
        session_id="sess_mcp",
        user_message="搜索 PubMed 单细胞",
        working_memory=wm,
        project_id="proj_1",
    )

    assert result.mode == ExecutionMode.DIRECT_RESPONSE
    assert result.agent_message is not None
    assert result.agent_message.type == "result_preview"
    # The response text should be a human-readable summary, not the raw tool name.
    assert "PubMed" in result.response_text or "找到" in result.response_text


@pytest.mark.asyncio
async def test_turn_runner_mcp_tool_missing_input(tool_registry):
    runner = TurnRunner(tool_registry=tool_registry)
    wm = WorkingMemory()

    result = await runner.run_turn(
        session_id="sess_mcp_missing",
        user_message="pubmed搜索",
        working_memory=wm,
        project_id="proj_1",
    )

    # The registry validates required 'query'; the handler is not called.
    assert result.mode == ExecutionMode.DIRECT_RESPONSE
    assert result.agent_message is not None
