"""API endpoints for LLM provider/model management."""

from __future__ import annotations

from typing import Dict, List

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from homomics_lab.api.auth import require_auth
from homomics_lab.llm.model_catalog import ModelCatalog

router = APIRouter(dependencies=[Depends(require_auth)])


class LegacyModelInfo(BaseModel):
    provider: str
    model: str
    display_name: str


class CatalogModelOut(BaseModel):
    id: str
    provider: str
    name: str
    capabilities: List[str]
    context_window: int
    cost_per_1k_input_usd: float
    cost_per_1k_output_usd: float
    supports_temperature: bool
    enabled: bool


class ModelsResponse(BaseModel):
    models: List[CatalogModelOut]


class PricingEntry(BaseModel):
    input_rate_per_1m: float
    output_rate_per_1m: float


@router.get("/llm/models", response_model=ModelsResponse)
async def list_available_models() -> Dict[str, List[Dict[str, object]]]:
    """Return the full LLM model catalog (API keys are never included)."""
    catalog = ModelCatalog()
    return {
        "models": [
            {
                "id": m.id,
                "provider": m.provider,
                "name": m.name,
                "capabilities": list(m.capabilities),
                "context_window": m.context_window,
                "cost_per_1k_input_usd": m.cost_per_1k_input_usd,
                "cost_per_1k_output_usd": m.cost_per_1k_output_usd,
                "supports_temperature": m.supports_temperature,
                "enabled": m.enabled,
            }
            for m in catalog.list_enabled()
        ]
    }


@router.get("/llm/pricing", response_model=Dict[str, PricingEntry])
async def list_pricing() -> Dict[str, Dict[str, float]]:
    """Return the internal pricing table for known models."""
    from homomics_lab.llm.cost import list_priced_models

    return {
        model: {"input_rate_per_1m": rates[0], "output_rate_per_1m": rates[1]}
        for model, rates in list_priced_models().items()
    }
