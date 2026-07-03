"""Tests for /api/execution/webhook/nextflow authentication."""

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport

from homomics_lab.api.execution import router
from homomics_lab.config import Settings
from homomics_lab.hpc.pubsub import ExecutionPubSub


@pytest_asyncio.fixture
async def client(monkeypatch):
    from fastapi import FastAPI

    app = FastAPI()
    app.state.execution_pubsub = ExecutionPubSub()
    app.include_router(router, prefix="/api/execution")
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.mark.asyncio
async def test_webhook_without_secret_dev_mode(client, monkeypatch):
    """In dev mode (auth disabled, no secret) the webhook is accepted with a warning."""
    monkeypatch.setattr(
        "homomics_lab.api.execution.settings",
        Settings(auth_enabled=False, nextflow_webhook_secret=None),
    )
    response = await client.post(
        "/api/execution/webhook/nextflow",
        json={"runName": "run-1", "event": "started"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_webhook_missing_secret_when_auth_enabled(client, monkeypatch):
    """With auth enabled but no secret, the endpoint must refuse the call."""
    monkeypatch.setattr(
        "homomics_lab.api.execution.settings",
        Settings(auth_enabled=True, nextflow_webhook_secret=None),
    )
    response = await client.post(
        "/api/execution/webhook/nextflow",
        json={"runName": "run-1", "event": "started"},
    )
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_webhook_missing_header_when_secret_configured(client, monkeypatch):
    monkeypatch.setattr(
        "homomics_lab.api.execution.settings",
        Settings(auth_enabled=False, nextflow_webhook_secret="super-secret"),
    )
    response = await client.post(
        "/api/execution/webhook/nextflow",
        json={"runName": "run-1", "event": "started"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_webhook_invalid_secret(client, monkeypatch):
    monkeypatch.setattr(
        "homomics_lab.api.execution.settings",
        Settings(auth_enabled=False, nextflow_webhook_secret="super-secret"),
    )
    response = await client.post(
        "/api/execution/webhook/nextflow",
        json={"runName": "run-1", "event": "started"},
        headers={"X-Nextflow-Webhook-Secret": "wrong-secret"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_webhook_valid_secret(client, monkeypatch):
    monkeypatch.setattr(
        "homomics_lab.api.execution.settings",
        Settings(auth_enabled=False, nextflow_webhook_secret="super-secret"),
    )
    response = await client.post(
        "/api/execution/webhook/nextflow",
        json={"runName": "run-1", "event": "started"},
        headers={"X-Nextflow-Webhook-Secret": "super-secret"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
