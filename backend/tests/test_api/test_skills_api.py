import pytest
from fastapi.testclient import TestClient

from homomics_lab.main import app
from homomics_lab.skills.models import SkillDefinition, SkillInputSchema


@pytest.fixture
def client_with_skills():
    """Create a test client with pre-registered skills."""
    from homomics_lab.skills.runtime import SkillRuntimeExecutor
    from homomics_lab.skills.builtin import register_builtin_skills

    executor = SkillRuntimeExecutor()
    register_builtin_skills(executor)

    # Register a test skill
    test_skill = SkillDefinition(
        id="test-skill",
        name="Test Skill",
        version="1.0.0",
        category="test",
        description="A test skill for API testing",
        runtime={"type": "python"},
        metadata={
            "primary_tool": "test",
            "supported_tools": ["test"],
            "keywords": ["test", "api"],
            "source": "builtin",
        },
        input_schema=SkillInputSchema(),
    )
    executor.registry.register(test_skill)

    app.state.skill_executor = executor
    return TestClient(app)


def test_list_skills(client_with_skills):
    response = client_with_skills.get("/api/skills")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1

    # Check structure
    skill = data[0]
    assert "id" in skill
    assert "name" in skill
    assert "category" in skill


def test_search_skills(client_with_skills):
    response = client_with_skills.get("/api/skills/search?q=test")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_get_skill_detail(client_with_skills):
    response = client_with_skills.get("/api/skills/test-skill")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "test-skill"
    assert data["name"] == "Test Skill"
    assert "supported_tools" in data
    assert "keywords" in data


def test_get_skill_not_found(client_with_skills):
    response = client_with_skills.get("/api/skills/nonexistent")

    assert response.status_code == 404
