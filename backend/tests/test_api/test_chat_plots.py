"""Tests for plot embedding in the chat HTTP API."""

from unittest.mock import patch, AsyncMock

from fastapi.testclient import TestClient

from homomics_lab.main import app
from homomics_lab.agent.turn_runner import TurnResult, ExecutionMode
from homomics_lab.models.common import ChatMessage, MessageType


client = TestClient(app)


def _make_turn_result(attachment_type: MessageType, content: dict, response_text: str = "done") -> TurnResult:
    """Build a TurnResult with a plot attachment for mocking."""
    attachment = ChatMessage(
        id="msg_attach_1",
        type=attachment_type,
        content=content,
        sender="agent",
        task_id="task_1",
        skill_id="viz",
    )
    agent_msg = ChatMessage(
        id="msg_agent_1",
        type=MessageType.TODO_LIST,
        content={"text": response_text, "tasks": []},
        sender="agent",
    )
    return TurnResult(
        mode=ExecutionMode.SINGLE_STEP,
        response_text=response_text,
        agent_message=agent_msg,
        attachments=[attachment],
    )


def test_send_message_returns_plot_data_attachments():
    """HTTP /send should return plot_data attachments when skills emit plots."""
    result = _make_turn_result(
        MessageType.PLOT_DATA,
        {
            "plot_type": "umap",
            "title": "UMAP Plot",
            "data": {"data": [{"x": [1, 2, 3]}], "layout": {"title": "UMAP"}},
        },
    )

    with patch("homomics_lab.api.chat.TurnRunner") as mock_runner_cls:
        instance = mock_runner_cls.return_value
        instance.run_turn = AsyncMock(return_value=result)

        response = client.post("/api/chat/send", json={
            "project_id": "proj_1",
            "session_id": "sess_plots",
            "message": "帮我画一个UMAP图",
        })

    assert response.status_code == 200
    data = response.json()
    assert "attachments" in data
    assert len(data["attachments"]) == 1
    attachment = data["attachments"][0]
    assert attachment["type"] == "plot_data"
    assert attachment["content"]["plot_type"] == "umap"
    assert attachment["content"]["title"] == "UMAP Plot"
    assert "data" in attachment["content"]


def test_send_message_with_static_plot_attachment():
    """HTTP /send should return static plot attachments."""
    result = _make_turn_result(
        MessageType.PLOT,
        {
            "plot_type": "qc",
            "title": "QC Plot",
            "image_base64": "base64string",
        },
    )

    with patch("homomics_lab.api.chat.TurnRunner") as mock_runner_cls:
        instance = mock_runner_cls.return_value
        instance.run_turn = AsyncMock(return_value=result)

        response = client.post("/api/chat/send", json={
            "project_id": "proj_1",
            "session_id": "sess_static_plots",
            "message": "帮我画一个QC图",
        })

    assert response.status_code == 200
    data = response.json()
    assert len(data["attachments"]) == 1
    attachment = data["attachments"][0]
    assert attachment["type"] == "plot"
    assert attachment["content"]["image_base64"] == "base64string"
