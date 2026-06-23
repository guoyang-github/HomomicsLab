"""Runtime settings management API.

This module exposes endpoints for the frontend Settings panel to read and update
LLM configuration securely.  Sensitive values (API keys) are stored in the
encrypted secrets manager; non-sensitive values are stored alongside them in the
same namespace for simplicity and atomicity.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator

from homomics_lab.api.auth import require_auth
from homomics_lab.llm.runtime_config import (
    LLMRuntimeConfig,
    load_llm_runtime_config,
    save_llm_runtime_config,
)
from homomics_lab.llm.router import LLMRouter

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(require_auth)])


class LLMConfigUpdate(BaseModel):
    provider: str
    model: str
    fallback_models: Optional[List[str]] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    temperature: float = 0.2
    max_tokens: int = 4096

    @field_validator("provider")
    @classmethod
    def provider_must_be_nonempty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("provider is required")
        return v.strip()

    @field_validator("model")
    @classmethod
    def model_must_be_nonempty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("model is required")
        return v.strip()


class LLMConfigOut(BaseModel):
    provider: Optional[str]
    model: Optional[str]
    fallback_models: List[str]
    base_url: Optional[str]
    api_key: Optional[str]  # masked, never raw
    temperature: float
    max_tokens: int


class TestConnectionOut(BaseModel):
    ok: bool
    provider: Optional[str]
    model: Optional[str]
    error: Optional[str] = None


def _normalize_base_url(provider: Optional[str], base_url: Optional[str]) -> Optional[str]:
    """Normalize OpenAI-compatible base URLs."""
    if not base_url:
        return base_url
    base_url = base_url.strip().rstrip("/")
    # Frontend uses 'local' to mean Ollama; the backend normalizes it to 'ollama'.
    if provider in ("ollama", "local") and not base_url.endswith("/v1"):
        base_url = f"{base_url}/v1"
    return base_url


@router.get("/llm")
async def get_llm_config() -> LLMConfigOut:
    """Return the currently effective LLM configuration.

    The API key is masked and never returned to the frontend.
    """
    config = load_llm_runtime_config()
    return LLMConfigOut(**config.to_frontend_dict())


@router.put("/llm")
async def update_llm_config(
    request: Request,
    body: LLMConfigUpdate,
) -> LLMConfigOut:
    """Persist LLM configuration and reload it in the running process."""
    provider = body.provider.strip().lower()
    model = body.model.strip()
    base_url = _normalize_base_url(provider, body.base_url)
    api_key = body.api_key.strip() if body.api_key else None

    if provider == "custom":
        if not base_url:
            raise HTTPException(status_code=422, detail="Custom provider requires a base URL")
        if not api_key:
            raise HTTPException(status_code=422, detail="Custom provider requires an API key")

    # If the frontend did not send a new API key (e.g. it masks it after load),
    # keep the existing key so a subsequent model-only save does not erase it.
    if not api_key:
        existing = load_llm_runtime_config()
        api_key = existing.api_key or api_key

    config = LLMRuntimeConfig(
        provider=provider,
        model=model,
        fallback_models=body.fallback_models or [],
        base_url=base_url,
        api_key=api_key,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
    )

    save_llm_runtime_config(config)

    llm_client = request.app.state.llm_client
    await llm_client.reload_config()

    user_id = getattr(request.state, "user_id", "anonymous")
    logger.info(
        "LLM configuration updated via UI",
        extra={
            "provider": provider,
            "model": model,
            "base_url": base_url,
            "user_id": user_id,
        },
    )

    effective = load_llm_runtime_config()
    return LLMConfigOut(**effective.to_frontend_dict())


@router.post("/llm/test")
async def test_llm_connection(
    request: Request,
    body: Optional[LLMConfigUpdate] = None,
) -> TestConnectionOut:
    """Make a minimal LLM call to verify the configuration works.

    If a payload is supplied, the endpoint tests those values without
    persisting them, so the user can validate a new provider/key before saving.
    """
    from homomics_lab.llm_client import LLMClient

    if body is not None:
        provider = body.provider.strip().lower()
        model = body.model.strip()
        base_url = _normalize_base_url(provider, body.base_url)
        api_key = body.api_key.strip() if body.api_key else None
        if provider == "custom":
            if not base_url:
                raise HTTPException(status_code=422, detail="Custom provider requires a base URL")
            if not api_key:
                raise HTTPException(status_code=422, detail="Custom provider requires an API key")
        config = LLMRuntimeConfig(
            provider=provider,
            model=model,
            fallback_models=body.fallback_models or [],
            base_url=base_url,
            api_key=api_key,
            temperature=body.temperature,
            max_tokens=body.max_tokens,
        )
        llm_client = LLMClient(
            model=model,
            api_key=api_key,
            base_url=base_url,
            router=LLMRouter(runtime_config=config),
        )
    else:
        config = load_llm_runtime_config()
        llm_client = request.app.state.llm_client

    if not config.is_configured:
        return TestConnectionOut(
            ok=False,
            provider=config.provider,
            model=config.model,
            error="LLM is not configured. Set provider, model, and API key.",
        )

    try:
        await llm_client.chat_completion(
            messages=[{"role": "user", "content": "hi"}],
            model=config.model,
            temperature=0.0,
            max_tokens=5,
        )
        return TestConnectionOut(
            ok=True,
            provider=config.provider,
            model=config.model,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM connection test failed", exc_info=True)
        return TestConnectionOut(
            ok=False,
            provider=config.provider,
            model=config.model,
            error=f"{type(exc).__name__}: {exc}",
        )
