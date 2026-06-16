"""API endpoints for managing encrypted secrets."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from homomics_lab.api.auth import require_auth
from homomics_lab.secrets import SecretNotFound, SecretsManager, get_secrets_manager

router = APIRouter(dependencies=[Depends(require_auth)])


class SecretCreate(BaseModel):
    key: str = Field(..., min_length=1, max_length=255)
    value: str = Field(..., min_length=1)
    namespace: str = Field(default="default", min_length=1, max_length=255)
    description: Optional[str] = None


class SecretUpdate(BaseModel):
    value: str = Field(..., min_length=1)
    description: Optional[str] = None


class SecretOut(BaseModel):
    key: str
    namespace: str
    description: Optional[str]
    created_at: str
    updated_at: str


class SecretValueOut(BaseModel):
    key: str
    namespace: str
    value: str


@router.get("/namespaces")
async def list_namespaces(manager: SecretsManager = Depends(get_secrets_manager)) -> List[str]:
    return manager.list_namespaces()


@router.post("/")
async def create_secret(
    body: SecretCreate,
    manager: SecretsManager = Depends(get_secrets_manager),
) -> SecretOut:
    manager.set(
        key=body.key,
        value=body.value,
        namespace=body.namespace,
        description=body.description,
    )
    # Fetch back to return timestamps.
    stored = next(
        (s for s in manager.list(body.namespace) if s.key == body.key),
        None,
    )
    if stored is None:
        raise HTTPException(status_code=500, detail="Failed to store secret")
    return SecretOut(
        key=stored.key,
        namespace=stored.namespace,
        description=stored.description,
        created_at=stored.created_at,
        updated_at=stored.updated_at,
    )


@router.get("/{namespace}")
async def list_secrets(
    namespace: str,
    manager: SecretsManager = Depends(get_secrets_manager),
) -> List[SecretOut]:
    return [
        SecretOut(
            key=s.key,
            namespace=s.namespace,
            description=s.description,
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in manager.list(namespace)
    ]


@router.get("/{namespace}/{key}")
async def get_secret_value(
    namespace: str,
    key: str,
    manager: SecretsManager = Depends(get_secrets_manager),
) -> SecretValueOut:
    try:
        value = manager.get_required(key, namespace)
    except SecretNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SecretValueOut(key=key, namespace=namespace, value=value)


@router.put("/{namespace}/{key}")
async def update_secret(
    namespace: str,
    key: str,
    body: SecretUpdate,
    manager: SecretsManager = Depends(get_secrets_manager),
) -> SecretOut:
    # Ensure secret exists.
    if manager.get(key, namespace) is None:
        raise HTTPException(status_code=404, detail=f"Secret '{key}' not found")
    manager.set(key, body.value, namespace, body.description)
    stored = next(
        (s for s in manager.list(namespace) if s.key == key),
        None,
    )
    return SecretOut(
        key=stored.key,
        namespace=stored.namespace,
        description=stored.description,
        created_at=stored.created_at,
        updated_at=stored.updated_at,
    )


@router.delete("/{namespace}/{key}")
async def delete_secret(
    namespace: str,
    key: str,
    manager: SecretsManager = Depends(get_secrets_manager),
) -> dict:
    deleted = manager.delete(key, namespace)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Secret '{key}' not found")
    return {"deleted": True}
