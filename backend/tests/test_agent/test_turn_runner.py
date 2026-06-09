"""Tests for the unified TurnRunner execution loop."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from homomics_lab.agent.turn_runner import TurnRunner, TurnResult, ExecutionMode
from homomics_lab.agent.intent_analyzer import UserIntent
from homomics_lab.context.working_memory import WorkingMemory
from homomics_lab.models.common import ChatMessage, MessageType


@pytest.fixture
def runner():
    return TurnRunner()


@pytest.fixture
def working_memory():
    return WorkingMemory()


@pytest.mark.asyncio
async def test_direct_response_mode(runner, working_memory):
    """QA-style questions should bypass skill execution and return directly."""
    result = await runner.run_turn(
        session_id="sess_1",
        user_message="什么是单细胞测序？",
        working_memory=working_memory,
        project_id="proj_1",
    )

    assert result.mode == ExecutionMode.DIRECT_RESPONSE
    assert "单细胞" in result.response_text or "测序" in result.response_text
    assert result.task_tree is None or len(result.task_tree.tasks) == 0


@pytest.mark.asyncio
async def test_single_step_mode(runner, working_memory):
    """Simple file conversion should execute as a single step."""
    result = await runner.run_turn(
        session_id="sess_2",
        user_message="把 data.csv 转成 h5ad 格式",
        working_memory=working_memory,
        project_id="proj_1",
    )

    assert result.mode == ExecutionMode.SINGLE_STEP
    assert result.task_tree is not None
    assert len(result.task_tree.tasks) == 1


@pytest.mark.asyncio
async def test_workflow_mode(runner, working_memory):
    """Complex analysis should decompose into a multi-step workflow."""
    result = await runner.run_turn(
        session_id="sess_3",
        user_message="帮我做一个完整的单细胞分析流程",
        working_memory=working_memory,
        project_id="proj_1",
    )

    # Workflow may pause at HITL checkpoints — both are valid outcomes
    assert result.mode in (ExecutionMode.WORKFLOW, ExecutionMode.AWAITING_HITL)
    assert result.task_tree is not None
    assert len(result.task_tree.tasks) > 1
    if result.mode == ExecutionMode.WORKFLOW:
        assert result.progress is not None


@pytest.mark.asyncio
async def test_resume_hitl_mode(runner, working_memory):
    """Resuming from HITL should continue execution."""
    # First, create a task tree with a HITL checkpoint
    result1 = await runner.run_turn(
        session_id="sess_4",
        user_message="帮我做一个完整的单细胞分析流程",
        working_memory=working_memory,
        project_id="proj_1",
    )

    # If HITL was triggered, resume it
    if result1.mode == ExecutionMode.AWAITING_HITL:
        result2 = await runner.resume_hitl(
            session_id="sess_4",
            task_id=result1.hitl_task_id,
            choice="default",
            parameters={},
            working_memory=working_memory,
            task_tree=result1.task_tree,
        )
        assert result2.mode in (ExecutionMode.WORKFLOW, ExecutionMode.SINGLE_STEP, ExecutionMode.RESUME_HITL)


@pytest.mark.asyncio
async def test_working_memory_accumulates(runner):
    """Messages should accumulate in working memory across turns."""
    wm = WorkingMemory()

    await runner.run_turn(
        session_id="sess_5",
        user_message="第一步",
        working_memory=wm,
        project_id="proj_1",
    )
    await runner.run_turn(
        session_id="sess_5",
        user_message="第二步",
        working_memory=wm,
        project_id="proj_1",
    )

    assert len(wm.messages) >= 4  # user + agent for each turn


@pytest.mark.asyncio
async def test_result_contains_agent_message(runner, working_memory):
    """TurnResult should contain the agent message ready for frontend."""
    result = await runner.run_turn(
        session_id="sess_6",
        user_message="帮我分析单细胞数据",
        working_memory=working_memory,
        project_id="proj_1",
    )

    assert result.agent_message is not None
    assert result.agent_message.sender == "agent"
    assert result.agent_message.type in [
        MessageType.TEXT,
        MessageType.TODO_LIST,
        MessageType.HITL_REQUEST,
    ]


def test_execution_mode_enum():
    """Execution modes cover all conversational scenarios."""
    modes = set(ExecutionMode)
    expected = {
        ExecutionMode.DIRECT_RESPONSE,
        ExecutionMode.SINGLE_STEP,
        ExecutionMode.WORKFLOW,
        ExecutionMode.AWAITING_HITL,
        ExecutionMode.RESUME_HITL,
        ExecutionMode.ERROR,
    }
    assert modes == expected
