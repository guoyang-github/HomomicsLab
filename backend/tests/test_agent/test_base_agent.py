import pytest
from homomics_lab.agent.base_agent import BaseAgent


class FakeAgent(BaseAgent):
    agent_type = "test"
    capabilities = ["test"]

    async def run(self, task, context):
        return {"result": f"processed {task.name}"}


@pytest.mark.asyncio
async def test_base_agent_run():
    agent = FakeAgent()
    task = type("Task", (), {"name": "test_task"})()
    result = await agent.run(task, {})
    assert result["result"] == "processed test_task"

def test_agent_can_handle():
    agent = FakeAgent()
    assert agent.can_handle("test") is True
    assert agent.can_handle("other") is False
