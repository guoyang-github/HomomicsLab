import pytest
from homomics_lab.context.relevance_filter import RelevanceFilter, ContextItem


@pytest.fixture
def filter():
    return RelevanceFilter()


def test_high_similarity_retained(filter):
    items = [
        ContextItem(content="单细胞质控结果", type="result"),
        ContextItem(content="今天的天气很好", type="chat"),
    ]
    goal = "分析单细胞数据"

    scored = filter.score_all(items, goal)
    assert scored[0][1] > scored[1][1]


def test_pinned_items_get_bonus(filter):
    item = ContextItem(content="无关内容", type="chat", is_pinned=True)
    score = filter.score(item, "分析数据")
    assert score >= 0.5  # Pinned items get minimum boost


def test_filter_by_budget(filter):
    items = [
        ContextItem(content=f"message {i}", type="chat")
        for i in range(10)
    ]
    # Mark first item as upstream result
    items[0].is_upstream_result = True

    filtered = filter.filter(items, budget=3, current_goal="test")
    assert len(filtered) == 3
