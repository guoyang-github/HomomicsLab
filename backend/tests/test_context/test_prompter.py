import pytest
from homomics_lab.context.prompter import Prompter
from homomics_lab.context.working_memory import WorkingMemory
from homomics_lab.models.common import ChatMessage, MessageType


@pytest.fixture
def prompter():
    return Prompter(token_budget=200)


def test_build_prompt_with_messages(prompter):
    wm = WorkingMemory()
    wm.add_message(ChatMessage(id="m1", type=MessageType.TEXT, content="hello", sender="user"))

    prompt = prompter.build_prompt(
        user_message="analyze this",
        working_memory=wm,
        task=None,
    )

    assert "analyze this" in prompt
    assert "hello" in prompt


def test_prompt_respects_token_budget(prompter):
    wm = WorkingMemory()
    long_message = "word " * 100
    wm.add_message(ChatMessage(id="m1", type=MessageType.TEXT, content=long_message, sender="user"))

    prompt = prompter.build_prompt(
        user_message="short",
        working_memory=wm,
        task=None,
    )

    # Budget should trigger truncation
    assert len(prompt.split()) <= 250  # Allow some overhead
