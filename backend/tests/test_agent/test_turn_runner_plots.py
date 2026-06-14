"""Tests for plot extraction inside TurnRunner."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from homomics_lab.agent.turn_runner import TurnRunner
from homomics_lab.context.working_memory import WorkingMemory
from homomics_lab.models.common import ChatMessage, MessageType
from homomics_lab.tasks.models import TaskNode
from homomics_lab.tasks.task_tree import TaskTree


def _make_tree(task_id: str = "task_1", skill_id: str = "viz") -> TaskTree:
    return TaskTree(
        tasks=[
            TaskNode(
                id=task_id,
                name="visualize",
                description="Visualization step",
                skills_required=[skill_id],
            )
        ]
    )


@pytest.mark.asyncio
async def test_turn_runner_extracts_plot_data_message():
    """TurnRunner should surface interactive plot_data as a chat message."""
    tree = _make_tree()
    orchestrator = MagicMock()
    orchestrator.run_tree = AsyncMock(return_value={
        "task_1": {
            "agent_type": "viz",
            "task": "visualize",
            "role_id": "visualization",
            "skill": "viz",
            "result": {
                "plot_data": {"data": [{"x": [1, 2]}], "layout": {"title": "Test"}},
                "plot_type": "umap",
                "title": "UMAP Plot",
            },
        }
    })
    orchestrator.get_progress = MagicMock(return_value={"completed": 1, "total": 1})

    runner = TurnRunner(orchestrator=orchestrator)
    wm = WorkingMemory()

    result = await runner._handle_single_step(tree, wm, "proj_1")

    assert result.mode.value == "single_step"
    assert len(result.attachments) == 1
    plot_msg = result.attachments[0]
    assert plot_msg.type == MessageType.PLOT_DATA
    assert plot_msg.content["plot_type"] == "umap"
    assert plot_msg.content["title"] == "UMAP Plot"
    assert plot_msg.skill_id == "viz"
    assert plot_msg.task_id == "task_1"


@pytest.mark.asyncio
async def test_turn_runner_extracts_static_plot_message():
    """TurnRunner should surface static image paths as plot messages."""
    tree = _make_tree()
    orchestrator = MagicMock()
    orchestrator.run_tree = AsyncMock(return_value={
        "task_1": {
            "skill": "viz",
            "result": {
                "plot_path": "/tmp/qc.png",
                "plot_type": "qc",
                "title": "QC Plot",
            },
        }
    })
    orchestrator.get_progress = MagicMock(return_value={"completed": 1, "total": 1})

    runner = TurnRunner(orchestrator=orchestrator)
    wm = WorkingMemory()

    result = await runner._handle_single_step(tree, wm, "proj_1")

    assert len(result.attachments) == 1
    plot_msg = result.attachments[0]
    assert plot_msg.type == MessageType.PLOT
    assert plot_msg.content["plot_type"] == "qc"
    assert "image_base64" in plot_msg.content
    assert "data" not in plot_msg.content


@pytest.mark.asyncio
async def test_turn_runner_adds_plot_messages_to_working_memory():
    """Plot messages should be persisted in working memory."""
    tree = _make_tree()
    orchestrator = MagicMock()
    orchestrator.run_tree = AsyncMock(return_value={
        "task_1": {
            "skill": "viz",
            "result": {
                "image_base64": "base64string",
                "plot_type": "heatmap",
            },
        }
    })
    orchestrator.get_progress = MagicMock(return_value={"completed": 1, "total": 1})

    runner = TurnRunner(orchestrator=orchestrator)
    wm = WorkingMemory()

    await runner._handle_single_step(tree, wm, "proj_1")

    plot_messages = [m for m in wm.messages if m.type == MessageType.PLOT]
    assert len(plot_messages) == 1
    assert plot_messages[0].content["image_base64"] == "base64string"


@pytest.mark.asyncio
async def test_turn_runner_no_plots_returns_empty_attachments():
    """When no plots are produced, attachments should remain empty."""
    tree = _make_tree()
    orchestrator = MagicMock()
    orchestrator.run_tree = AsyncMock(return_value={
        "task_1": {
            "skill": "convert",
            "result": {"output_path": "/tmp/out.h5ad"},
        }
    })
    orchestrator.get_progress = MagicMock(return_value={"completed": 1, "total": 1})

    runner = TurnRunner(orchestrator=orchestrator)
    wm = WorkingMemory()

    result = await runner._handle_single_step(tree, wm, "proj_1")

    assert result.attachments == []
