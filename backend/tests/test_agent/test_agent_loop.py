import pytest

from homomics_lab.agent.agent_loop import AgentLoop, TurnBudget
from homomics_lab.tools.models import ToolDefinition, ToolResult
from homomics_lab.tools.registry import ToolRegistry


class _FakeMessage:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []


class _FakeToolCall:
    def __init__(self, id, name, arguments):
        self.id = id
        self.function = _FakeFunction(name, arguments)


class _FakeFunction:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


class _FakeLLM:
    def __init__(self, responses):
        self._responses = list(responses)
        self._idx = 0

    async def chat_completion_message(self, **kwargs):
        if self._idx >= len(self._responses):
            raise RuntimeError("No more fake responses")
        resp = self._responses[self._idx]
        self._idx += 1
        return resp, {"cost_usd": 0.001, "prompt_tokens": 10, "completion_tokens": 10}


@pytest.fixture
def registry():
    reg = ToolRegistry()
    reg.register(
        ToolDefinition(
            name="pubmed_search",
            description="Search PubMed",
            input_schema={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
            risk_level="low",
            handler=lambda query, retmax=10: {"count": 2, "articles": [{"title": f"Article about {query}"}]},
        )
    )
    reg.register(
        ToolDefinition(
            name="shell_exec",
            description="Run shell command",
            input_schema={
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
            risk_level="high",
        )
    )
    return reg


@pytest.mark.asyncio
async def test_agent_loop_executes_tool_and_returns_summary(registry):
    llm = _FakeLLM([
        _FakeMessage(tool_calls=[_FakeToolCall("tc1", "pubmed_search", '{"query": "scRNA-seq"}')]),
        _FakeMessage(content="Found articles about scRNA-seq."),
    ])
    loop = AgentLoop(llm_client=llm, tool_registry=registry, max_rounds=2)
    result = await loop.run(user_message="search pubmed for scRNA-seq", history=[])

    assert "Found articles" in result.response_text
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].tool_name == "pubmed_search"
    assert result.tool_calls[0].success is True
    assert result.stopped_reason == "complete"


@pytest.mark.asyncio
async def test_agent_loop_no_tool_call_when_not_needed(registry):
    llm = _FakeLLM([_FakeMessage(content="I can answer directly.")])
    loop = AgentLoop(llm_client=llm, tool_registry=registry, max_rounds=2)
    result = await loop.run(user_message="hello", history=[])

    assert result.response_text == "I can answer directly."
    assert result.tool_calls == []


@pytest.mark.asyncio
async def test_agent_loop_respects_high_risk_gate(registry):
    llm = _FakeLLM([
        _FakeMessage(tool_calls=[_FakeToolCall("tc1", "shell_exec", '{"command": "rm -rf /"}')]),
        _FakeMessage(content="I cannot run that command."),
    ])
    loop = AgentLoop(llm_client=llm, tool_registry=registry, max_rounds=2)
    result = await loop.run(user_message="delete everything", history=[])

    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].tool_name == "shell_exec"
    assert result.tool_calls[0].success is False
    assert "高风险" in result.tool_calls[0].output_summary


@pytest.mark.asyncio
async def test_agent_loop_budget_stops_execution(registry):
    llm = _FakeLLM([
        _FakeMessage(tool_calls=[_FakeToolCall("tc1", "pubmed_search", '{"query": "x"}')]),
    ])
    loop = AgentLoop(
        llm_client=llm,
        tool_registry=registry,
        max_rounds=3,
        budget=TurnBudget(max_llm_calls=1, max_tool_calls=5),
    )
    result = await loop.run(user_message="search", history=[])

    assert result.stopped_reason == "llm_call_budget"
    assert "预算" in result.response_text
