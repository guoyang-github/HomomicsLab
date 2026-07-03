from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from homomics_lab.api.responses import StatusResponse
from homomics_lab.cost_control import BudgetExceeded, get_cost_controller

router = APIRouter()


class CostUsageReport(BaseModel):
    """LLM + compute cost summary and budget status."""

    llm_cost_usd: float
    compute_cost_usd: float
    total_cost_usd: float
    monthly_budget_usd: Optional[float]
    max_request_cost_usd: Optional[float]
    remaining_monthly_budget_usd: Optional[float]


@router.get("/costs", response_model=CostUsageReport)
async def get_cost_summary():
    """Return current LLM + compute cost summary and budget status."""
    return get_cost_controller().get_usage_report()


@router.post("/costs/check", response_model=StatusResponse)
async def check_budget():
    """Return 200 if within budget, 402 if budget exceeded."""
    try:
        get_cost_controller().check_request_budget(0.0)
        return {"status": "ok"}
    except BudgetExceeded as exc:
        raise HTTPException(status_code=402, detail=str(exc)) from exc
