"""Tests for the natural-language visualization edit fast path."""

import pytest
from unittest.mock import MagicMock

from homomics_lab.agent.intent_analyzer import IntentAnalyzer
from homomics_lab.agent.turn_runner import ExecutionMode, TurnRunner
from homomics_lab.context.working_memory import WorkingMemory
from homomics_lab.models.common import ChatMessage, MessageType


def _make_bar_plot_data() -> dict:
    return {
        "plot_type": "bar",
        "title": "Sample Counts",
        "caption": "",
        "data": [
            {
                "type": "bar",
                "x": ["A", "B", "C"],
                "y": [10, 20, 15],
                "marker": {"color": "#4682b4"},
            }
        ],
        "layout": {"yaxis": {"title": "Count"}},
    }


def _make_violin_plot_data() -> dict:
    return {
        "plot_type": "violin",
        "title": "Group distributions",
        "caption": "",
        "data": [
            {
                "type": "violin",
                "y": [1, 2, 3, 4, 5],
                "name": "Group A",
                "box": {"visible": True},
                "meanline": {"visible": True},
            },
            {
                "type": "violin",
                "y": [2, 4, 6, 8, 10],
                "name": "Group B",
                "box": {"visible": True},
                "meanline": {"visible": True},
            },
        ],
        "layout": {"yaxis": {"title": "Value"}},
    }


def _add_plot_message(working_memory: WorkingMemory, content: dict) -> None:
    working_memory.add_message(
        ChatMessage(
            id=f"msg_{len(working_memory.messages)}",
            type=MessageType.PLOT_DATA,
            content=content,
            sender="agent",
            task_id="viz_task",
            skill_id="viz",
        )
    )


@pytest.fixture
def analyzer():
    return IntentAnalyzer(use_domain_registry=False)


@pytest.mark.asyncio
async def test_detect_visualization_edit_intent_color(analyzer):
    intent = await analyzer.analyze("把颜色改成蓝色")
    assert intent.target == "visualization_edit"
    assert intent.scope == "single_step"
    assert intent.interaction_mode == "modify"


@pytest.mark.asyncio
async def test_detect_visualization_edit_intent_boxplot(analyzer):
    intent = await analyzer.analyze("换成箱线图")
    assert intent.target == "visualization_edit"
    assert intent.scope == "single_step"


@pytest.mark.asyncio
async def test_visualization_edit_changes_color():
    runner = TurnRunner()
    wm = WorkingMemory()
    _add_plot_message(wm, _make_bar_plot_data())

    result = await runner._route_by_intent(
        intent=MagicMock(
            intent_type="analysis",
            interaction_mode="modify",
            scope="single_step",
            metadata={},
            domain=None,
            target="visualization_edit",
        ),
        user_message="把颜色改成蓝色",
        working_memory=wm,
        project_id="proj_1",
        session_id="sess_1",
        plan_store=None,
        job_service=None,
        enqueue_skills=False,
        plan_mode=False,
    )

    assert result.mode == ExecutionMode.DIRECT_RESPONSE
    assert len(result.attachments) == 1
    plot_msg = result.attachments[0]
    assert plot_msg.type == MessageType.PLOT_DATA
    assert plot_msg.content["data"][0]["marker"]["color"] == "#377eb8"
    assert any(m.type == MessageType.PLOT_DATA for m in wm.messages)


@pytest.mark.asyncio
async def test_visualization_edit_converts_violin_to_box():
    runner = TurnRunner()
    wm = WorkingMemory()
    _add_plot_message(wm, _make_violin_plot_data())

    result = await runner._route_by_intent(
        intent=MagicMock(
            intent_type="analysis",
            interaction_mode="modify",
            scope="single_step",
            metadata={},
            domain=None,
            target="visualization_edit",
        ),
        user_message="换成箱线图",
        working_memory=wm,
        project_id="proj_1",
        session_id="sess_1",
        plan_store=None,
        job_service=None,
        enqueue_skills=False,
        plan_mode=False,
    )

    assert result.mode == ExecutionMode.DIRECT_RESPONSE
    plot_msg = result.attachments[0]
    assert plot_msg.type == MessageType.PLOT_DATA
    assert all(trace["type"] == "box" for trace in plot_msg.content["data"])


@pytest.mark.asyncio
async def test_visualization_edit_adds_error_bars():
    runner = TurnRunner()
    wm = WorkingMemory()
    _add_plot_message(wm, _make_bar_plot_data())

    result = await runner._route_by_intent(
        intent=MagicMock(
            intent_type="analysis",
            interaction_mode="modify",
            scope="single_step",
            metadata={},
            domain=None,
            target="visualization_edit",
        ),
        user_message="加误差线",
        working_memory=wm,
        project_id="proj_1",
        session_id="sess_1",
        plan_store=None,
        job_service=None,
        enqueue_skills=False,
        plan_mode=False,
    )

    assert result.mode == ExecutionMode.DIRECT_RESPONSE
    plot_msg = result.attachments[0]
    assert "error_y" in plot_msg.content["data"][0]


@pytest.mark.asyncio
async def test_visualization_edit_fallback_without_recent_plot():
    runner = TurnRunner()
    wm = WorkingMemory()

    result = await runner._route_by_intent(
        intent=MagicMock(
            intent_type="analysis",
            interaction_mode="modify",
            scope="single_step",
            metadata={},
            domain=None,
            target="visualization_edit",
        ),
        user_message="把颜色改成蓝色",
        working_memory=wm,
        project_id="proj_1",
        session_id="sess_1",
        plan_store=None,
        job_service=None,
        enqueue_skills=False,
        plan_mode=False,
    )

    assert result.mode == ExecutionMode.DIRECT_RESPONSE
    assert result.agent_message.type == MessageType.TEXT
    assert "找不到" in result.response_text
