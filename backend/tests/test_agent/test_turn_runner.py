"""Tests for the unified TurnRunner execution loop."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from homomics_lab.agent.turn_runner import TurnRunner, ExecutionMode
from homomics_lab.agent.intent.models import UserIntent
from homomics_lab.context.working_memory import WorkingMemory
from homomics_lab.models.common import MessageType
from homomics_lab.secrets import reset_secrets_manager


@pytest.fixture(autouse=True)
def isolate_secrets(tmp_path, monkeypatch):
    reset_secrets_manager()
    monkeypatch.setattr("homomics_lab.config.settings.data_dir", tmp_path)
    monkeypatch.setattr("homomics_lab.config.settings.secrets_master_key", "test-key")
    yield
    reset_secrets_manager()


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
        user_message="什么是 UMAP？",
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
        ExecutionMode.QUEUED,
        ExecutionMode.AWAITING_PLAN_APPROVAL,
        ExecutionMode.AWAITING_DEBATE,
        ExecutionMode.ERROR,
    }
    assert modes == expected


@pytest.mark.asyncio
async def test_general_help_direct_response_without_llm(runner, working_memory):
    """General help requests return a template when no LLM is configured."""
    result = await runner.run_turn(
        session_id="sess_help_1",
        user_message="帮我写个 Python 脚本过滤 CSV",
        working_memory=working_memory,
        project_id="proj_1",
    )

    assert result.mode == ExecutionMode.DIRECT_RESPONSE
    assert result.task_tree is None or len(result.task_tree.tasks) == 0
    # Should mention configuration or rephrasing in the fallback text.
    assert "OPENAI_API_KEY" in result.response_text or "LLM" in result.response_text


@pytest.mark.asyncio
async def test_general_help_direct_response_with_llm(runner, working_memory):
    """General help requests use the LLM to generate code when configured."""
    with patch("homomics_lab.agent.turn_runner.LLMClient") as MockClient:
        mock_client = MagicMock()
        mock_client.is_configured.return_value = True
        mock_client.chat_completion = AsyncMock(return_value="```python\nprint('hello')\n```")
        MockClient.return_value = mock_client

        result = await runner.run_turn(
            session_id="sess_help_2",
            user_message="generate code to parse a csv",
            working_memory=working_memory,
            project_id="proj_1",
        )

    assert result.mode == ExecutionMode.DIRECT_RESPONSE
    assert "hello" in result.response_text


@pytest.mark.asyncio
async def test_clarification_response(runner, working_memory):
    """Ambiguous requests return a clarification question."""
    result = await runner.run_turn(
        session_id="sess_clarify",
        user_message="分析数据",
        working_memory=working_memory,
        project_id="proj_1",
    )

    assert result.mode == ExecutionMode.DIRECT_RESPONSE
    assert result.task_tree is None or len(result.task_tree.tasks) == 0
    assert "具体" in result.response_text or "什么" in result.response_text


def test_handle_clarification_with_debate(runner, working_memory):
    """Clarification intent carrying debate metadata yields a debate request."""
    intent = UserIntent(
        analysis_type="clarification",
        complexity="direct_response",
        metadata={
            "debate": {
                "topic": "请选择最符合您需求的选项",
                "options": [
                    {"id": "single_cell_analysis", "label": "单细胞分析"},
                    {"id": "spatial_analysis", "label": "空间分析"},
                ],
                "recommendation": None,
            }
        },
    )
    result = runner._handle_clarification(intent, working_memory)

    assert result.mode == ExecutionMode.AWAITING_DEBATE
    assert result.agent_message is not None
    assert result.agent_message.type == MessageType.DEBATE_REQUEST
    assert result.agent_message.content["topic"]
    assert len(result.agent_message.content["options"]) == 2


@pytest.mark.asyncio
async def test_debate_response_resolves_intent(runner, working_memory):
    """A user's debate choice is converted into a concrete intent and executed."""
    result = await runner.run_turn(
        session_id="sess_debate_resolve",
        user_message="我选择 QA",
        working_memory=working_memory,
        project_id="proj_1",
        debate_response={"choice_id": "qa", "parameters": {}},
    )

    assert result.mode == ExecutionMode.DIRECT_RESPONSE
    assert result.agent_message is not None
    assert result.agent_message.type == MessageType.TEXT
