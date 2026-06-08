import pytest
from homomics_lab.skills.registry import SkillRegistry
from homomics_lab.skills.models import SkillDefinition


@pytest.fixture
def registry():
    return SkillRegistry()


def test_register_skill(registry):
    skill = SkillDefinition(id="s1", name="Skill 1", version="1.0.0", category="test")
    registry.register(skill)
    assert registry.get("s1") == skill


def test_get_unknown_skill(registry):
    assert registry.get("unknown") is None


def test_list_by_category(registry):
    registry.register(SkillDefinition(id="s1", name="A", version="1.0.0", category="cat1"))
    registry.register(SkillDefinition(id="s2", name="B", version="1.0.0", category="cat1"))
    registry.register(SkillDefinition(id="s3", name="C", version="1.0.0", category="cat2"))

    cat1 = registry.list_by_category("cat1")
    assert len(cat1) == 2
