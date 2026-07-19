import pytest

from homomics_lab.cost_control import BudgetExceeded, CostController


@pytest.fixture
def controller(tmp_path, monkeypatch):
    import homomics_lab.cost_control as cost_control_module

    monkeypatch.setattr(cost_control_module, "MONTHLY_BUDGET_USD", 10.0)
    monkeypatch.setattr(cost_control_module, "MAX_LLM_COST_PER_REQUEST_USD", 2.0)
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


def test_check_request_budget_accepts_optional_cap(controller):
    """Router may pass a stricter per-request cap than the global setting."""
    # Global cap is $2; optional cap of $1 should be enforced.
    with pytest.raises(BudgetExceeded):
        controller.check_request_budget(1.5, cap=1.0)
    # Optional cap higher than global should still respect global.
    with pytest.raises(BudgetExceeded):
        controller.check_request_budget(2.5, cap=5.0)


def test_record_llm_cost_with_context(controller):
    """Cost records should preserve request/session/project context."""
    import sqlite3

    controller.record_llm_cost(
        "gpt-4o-mini",
        100,
        50,
        150,
        0.001,
        request_id="req_1",
        session_id="sess_1",
        project_id="proj_1",
    )
    with sqlite3.connect(str(controller.db_path)) as conn:
        row = conn.execute(
            "SELECT request_id, session_id, project_id FROM llm_costs"
        ).fetchone()
    assert row == ("req_1", "sess_1", "proj_1")
