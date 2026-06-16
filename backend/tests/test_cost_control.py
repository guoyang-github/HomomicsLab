import pytest

from homomics_lab.config import settings
from homomics_lab.cost_control import BudgetExceeded, CostController


@pytest.fixture
def controller(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "monthly_budget_usd", 10.0)
    monkeypatch.setattr(settings, "max_llm_cost_per_request_usd", 2.0)
    return CostController(db_path=tmp_path / "costs.db")


def test_record_llm_cost(controller):
    controller.record_llm_cost("gpt-4o-mini", 1000, 500, 1500, 0.003)
    assert controller.get_monthly_llm_cost() == pytest.approx(0.003, rel=1e-3)


def test_monthly_budget_enforcement(controller):
    controller.record_llm_cost("gpt-4o-mini", 1_000_000, 500_000, 1_500_000, 9.0)
    # Still under $10 total.
    controller.check_request_budget(0.5)
    # Push over budget.
    controller.record_llm_cost("gpt-4o-mini", 1_000_000, 500_000, 1_500_000, 2.0)
    with pytest.raises(BudgetExceeded):
        controller.check_request_budget(0.1)


def test_per_request_cap(controller):
    with pytest.raises(BudgetExceeded):
        controller.check_request_budget(5.0)


def test_snapshot(controller):
    controller.record_llm_cost("gpt-4o-mini", 1000, 500, 1500, 0.003)
    snapshot = controller.get_snapshot()
    assert snapshot.total_cost_usd == pytest.approx(0.003, rel=1e-3)
    assert snapshot.remaining_monthly_budget_usd == pytest.approx(9.997, rel=1e-3)
