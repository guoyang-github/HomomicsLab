"""Tests for the specialist + critic sub-agent layer."""

from dataclasses import dataclass
from types import SimpleNamespace
from typing import List

import pytest

from homomics_lab.agent.agent_loop import AgentLoopResult
from homomics_lab.agent.subagents import (
    CriticAgent,
    SpecialistAgent,
    SpecialistCriticOrchestrator,
    filter_tools_by_role,
    read_only_tools,
)


class FakeTool:
    def __init__(self, name, risk_level="low"):
        self.name = name
        self.risk_level = risk_level


class FakeRegistry:
    def __init__(self, tools):
        self._tools = tools

    def list_all(self):
        return self._tools


@dataclass
class FakeRole:
    role_id: str
    name: str
    allowed_tools: List[str]
    allowed_skills: List[str]


class FakeLoop:
    def __init__(self, response_text: str):
        self.response_text = response_text

    async def run(self, **kwargs):
        return AgentLoopResult(response_text=self.response_text)


def fake_loop_factory(response_text: str):
    def _factory(*args, **kwargs):
        return FakeLoop(response_text)
    return _factory


def test_filter_tools_by_role_allows_skills_and_tools():
    registry = FakeRegistry([
        FakeTool("file_read"),
        FakeTool("bio-single-cell-annotation-celltypist"),
        FakeTool("bio-spatial-transcriptomics-preprocessing"),
        FakeTool("shell_exec", "high"),
    ])
    role = FakeRole(
        role_id="sc",
        name="Single-Cell Specialist",
        allowed_tools=["file_read"],
        allowed_skills=["bio-single-cell-*"],
    )
    names = filter_tools_by_role(registry, role)
    assert "file_read" in names
    assert "bio-single-cell-annotation-celltypist" in names
    assert "bio-spatial-transcriptomics-preprocessing" not in names
    assert "shell_exec" not in names  # role restrictions do not include shell_exec


def test_read_only_tools_exclude_writes():
    registry = FakeRegistry([
        FakeTool("file_read"),
        FakeTool("web_search"),
        FakeTool("file_write"),
        FakeTool("shell_exec", "high"),
        FakeTool("bio-x", "medium"),
    ])
    names = read_only_tools(registry)
    assert set(names) == {"file_read", "web_search"}


@pytest.mark.asyncio
async def test_specialist_returns_loop_output():
    agent = SpecialistAgent(
        llm_client=None,
        tool_registry=FakeRegistry([FakeTool("file_read"), FakeTool("bio-x")]),
        role=FakeRole("sc", "SC", ["file_read"], ["bio-*"]),
        loop_factory=fake_loop_factory("Looks good."),
    )
    result = await agent.review_plan("do QC", {"phases": []})
    assert result.response_text == "Looks good."
    assert result.metadata["role"] == "sc"


@pytest.mark.asyncio
async def test_critic_parses_json_review():
    response = (
        '{"action": "revise", "summary": "Missing QC", '
        '"concerns": ["no QC step"], "suggestions": ["add QC"]}'
    )
    agent = CriticAgent(
        llm_client=None,
        tool_registry=FakeRegistry([FakeTool("file_read"), FakeTool("file_write")]),
        loop_factory=fake_loop_factory(response),
    )
    review = await agent.review(
        specialist_output=SimpleNamespace(response_text="Plan A"),
        plan={"phases": []},
        request="analyze",
    )
    assert review.action == "revise"
    assert review.summary == "Missing QC"
    assert review.concerns == ["no QC step"]
    assert review.suggestions == ["add QC"]


@pytest.mark.asyncio
async def test_critic_handles_non_json():
    agent = CriticAgent(
        llm_client=None,
        tool_registry=FakeRegistry([FakeTool("file_read")]),
        loop_factory=fake_loop_factory("I think this is wrong."),
    )
    review = await agent.review(
        specialist_output=SimpleNamespace(response_text="Plan A"),
        plan={"phases": []},
    )
    assert review.action == "ask_user"
    assert review.concerns


@pytest.mark.asyncio
async def test_orchestrator_chains_specialist_and_critic():
    registry = FakeRegistry([FakeTool("file_read"), FakeTool("file_write")])
    orchestrator = SpecialistCriticOrchestrator(
        llm_client=None,
        tool_registry=registry,
        role=FakeRole("sc", "SC", ["file_read"], []),
    )

    def make_loop(response_text: str):
        return fake_loop_factory(response_text)

    orchestrator.specialist.loop_factory = make_loop("Specialist says add QC.")
    orchestrator.critic.loop_factory = make_loop(
        '{"action": "approve", "summary": "Good after QC", "concerns": [], "suggestions": []}'
    )
    review = await orchestrator.review("analyze", {"phases": []})
    assert review.action == "approve"
    assert review.specialist_output.response_text == "Specialist says add QC."
