"""API endpoints for LLM provider/model management."""

from __future__ import annotations

from typing import Dict, List

from fastapi import APIRouter, Depends

from homomics_lab.api.auth import require_auth
from homomics_lab.llm.router import LLMRouter

router = APIRouter(dependencies=[Depends(require_auth)])


@router.get("/llm/models")
async def list_available_models() -> Dict[str, List[Dict[str, str]]]:
    """Return all LLM models whose providers are currently configured."""
    router = LLMRouter()
    return {"models": router.list_available_models()}


@router.get("/llm/pricing")
async def list_pricing() -> Dict[str, Dict[str, float]]:
    """Return the internal pricing table for known models."""
    from homomics_lab.llm.cost import list_priced_models

    return {
        model: {"input_rate_per_1m": rates[0], "output_rate_per_1m": rates[1]}
        for model, rates in list_priced_models().items()
    }
