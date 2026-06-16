from fastapi import APIRouter, HTTPException

from homomics_lab.cost_control import BudgetExceeded, get_cost_controller

router = APIRouter()


@router.get("/costs")
async def get_cost_summary():
    """Return current LLM + compute cost summary and budget status."""
    return get_cost_controller().get_usage_report()


@router.post("/costs/check")
async def check_budget():
    """Return 200 if within budget, 402 if budget exceeded."""
    try:
        get_cost_controller().check_request_budget(0.0)
        return {"status": "ok"}
    except BudgetExceeded as exc:
        raise HTTPException(status_code=402, detail=str(exc)) from exc
