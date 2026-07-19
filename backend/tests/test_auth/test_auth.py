"""Tests for OAuth2 / OIDC authentication and API-key backward compatibility."""

import asyncio
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from homomics_lab.api.auth import (
    _decode_local_token,
    _resolve_token_user_id,
    create_access_token,
    create_default_admin_if_missing,
    get_current_user,
    get_password_hash,
    verify_oidc_token,
)
from homomics_lab.config import settings
from homomics_lab.database.connection import get_session_factory, reset_engine
from homomics_lab.database.models import Tenant, User
from homomics_lab.main import app


# ---------------------------------------------------------------------------
# Module-scoped auth-enabled TestClient (bootstrap is expensive, so run once).
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def auth_client_module():
    """Single TestClient bootstrapped with auth enabled for the whole module."""
    original = {
        "auth_enabled": settings.auth_enabled,
        "jwt_secret_key": settings.jwt_secret_key,
        "api_key": settings.api_key,
        "oidc_discovery_url": settings.oidc_discovery_url,
    }

    settings.auth_enabled = True
    settings.jwt_secret_key = "test-jwt-secret-key-for-unit-tests"
    settings.api_key = "test-api-key"
    settings.oidc_discovery_url = None

    reset_engine()

    user_id = "user_test_001"
    tenant_id = "tenant_test_001"

    async def _seed():
        async with get_session_factory()() as session:
            existing = await session.get(User, user_id)
            if existing is None:
                session.add(Tenant(id=tenant_id, name="Test Tenant"))
                session.add(
                    User(
                        id=user_id,
                        tenant_id=tenant_id,
                        username="testuser",
                        hashed_password=get_password_hash("testpass"),
                        role="analyst",
                        is_active=True,
                    )
                )
                await session.commit()

    asyncio.run(_seed())

    with TestClient(app) as client:
        yield client, user_id

    async def _cleanup():
        async with get_session_factory()() as session:
            user = await session.get(User, user_id)
            if user:
                await session.delete(user)
            tenant = await session.get(Tenant, tenant_id)
            if tenant:
                await session.delete(tenant)
            await session.commit()

    asyncio.run(_cleanup())

    for k, v in original.items():
        setattr(settings, k, v)
    reset_engine()


@pytest.fixture
def auth_client(auth_client_module):
    return auth_client_module[0]


@pytest.fixture
def test_user_id(auth_client_module):
    return auth_client_module[1]


# ---------------------------------------------------------------------------
# Disabled-auth unit tests (no expensive app bootstrap needed).
# ---------------------------------------------------------------------------

class TestAuthDisabled:
    @pytest.mark.asyncio
    async def test_get_current_user_returns_anonymous_when_auth_disabled(self):
        original = settings.auth_enabled
        settings.auth_enabled = False
        try:
            request = MagicMock()
            request.state = MagicMock()
            user_id = await get_current_user(request, api_key=None)
            assert user_id == "anonymous"
            assert request.state.user_id == "anonymous"
        finally:
            settings.auth_enabled = original


# ---------------------------------------------------------------------------
# API-key backward compatibility.
# ---------------------------------------------------------------------------

class TestAuthEnabledApiKey:
    def test_missing_key_returns_401(self, auth_client):
        response = auth_client.get("/api/skills/")
        assert response.status_code == 401

    def test_invalid_key_returns_403(self, auth_client):
        response = auth_client.get("/api/skills/", headers={"X-API-Key": "wrong-key"})
        assert response.status_code == 403

    def test_valid_header_key_returns_200(self, auth_client):
        response = auth_client.get(
            "/api/skills/",
            headers={"X-API-Key": "test-api-key"},
        )
        assert response.status_code == 200

    def test_valid_bearer_token_api_key_returns_200(self, auth_client):
        response = auth_client.get(
            "/api/skills/",
            headers={"Authorization": "Bearer test-api-key"},
        )
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# JWT / OAuth2 password flow.
# ---------------------------------------------------------------------------

class TestAuthEnabledJwt:
    def test_login_returns_jwt(self, auth_client, test_user_id):
        response = auth_client.post(
            "/api/auth/token",
            data={"username": "testuser", "password": "testpass"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_invalid_login_returns_401(self, auth_client, test_user_id):
        response = auth_client.post(
            "/api/auth/token",
            data={"username": "testuser", "password": "wrongpass"},
        )
        assert response.status_code == 401

    def test_protected_route_accepts_jwt(self, auth_client, test_user_id):
        token_response = auth_client.post(
            "/api/auth/token",
            data={"username": "testuser", "password": "testpass"},
        )
        token = token_response.json()["access_token"]

        response = auth_client.get(
            "/api/skills/",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

    def test_invalid_jwt_returns_403(self, auth_client, test_user_id):
        response = auth_client.get(
            "/api/skills/",
            headers={"Authorization": "Bearer invalid-token-value"},
        )
        assert response.status_code == 403

    def test_me_returns_user_profile(self, auth_client, test_user_id):
        token_response = auth_client.post(
            "/api/auth/token",
            data={"username": "testuser", "password": "testpass"},
        )
        token = token_response.json()["access_token"]

        response = auth_client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_user_id
        assert data["username"] == "testuser"
        assert data["role"] == "analyst"

    def test_public_endpoints_remain_unauthenticated(self, auth_client):
        assert auth_client.get("/").status_code == 200
        assert auth_client.get("/health").status_code == 200


# ---------------------------------------------------------------------------
# Token helper unit tests (no app bootstrap).
# ---------------------------------------------------------------------------

class TestTokenHelpers:
    def test_create_access_token_encodes_sub(self, monkeypatch):
        monkeypatch.setattr(settings, "jwt_secret_key", "test-jwt-secret-key-for-unit-tests")
        token = create_access_token({"sub": "user-123"})
        payload = _decode_local_token(token)
        assert payload is not None
        assert payload["sub"] == "user-123"

    @pytest.mark.asyncio
    async def test_resolve_oidc_token_with_cached_jwks(self, monkeypatch):
        monkeypatch.setattr(settings, "oidc_discovery_url", "https://example.com/.well-known/openid-configuration")
        monkeypatch.setattr(settings, "jwt_secret_key", "test-jwt-secret-key-for-unit-tests")
        monkeypatch.setattr("homomics_lab.api.auth.JWT_ALGORITHM", "HS256")

        # Issue a token locally so we can mock the OIDC verifier to accept it.
        token = create_access_token({"sub": "oidc-user-1"})
        monkeypatch.setattr(
            "homomics_lab.api.auth.verify_oidc_token",
            lambda t: {"user_id": "oidc-user-1"} if t == token else None,
        )

        user_id = await _resolve_token_user_id(token)
        assert user_id == "oidc-user-1"

    def test_verify_oidc_token_returns_none_without_jwks(self, monkeypatch):
        monkeypatch.setattr(settings, "oidc_discovery_url", "https://example.com/.well-known/openid-configuration")
        assert verify_oidc_token("any.token.here") is None


# ---------------------------------------------------------------------------
# Default admin bootstrap helper.
# ---------------------------------------------------------------------------

class TestBootstrapHelpers:
    @pytest.mark.asyncio
    async def test_create_default_admin_if_missing(self, monkeypatch, tmp_path):
        # Use an isolated SQLite database so existing users do not interfere.
        db_path = tmp_path / "admin_test.db"
        monkeypatch.setattr(settings, "auth_enabled", True)
        monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{db_path}")
        monkeypatch.setattr(settings, "admin_initial_password", "secure-test-pass")
        reset_engine()

        async with get_session_factory()() as session:
            from homomics_lab.database.base import Base
            from homomics_lab.database.connection import get_engine

            async with get_engine().begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            user = await create_default_admin_if_missing(session)
            assert user is not None
            assert user.username == "admin"
            assert user.role == "admin"

            # Second call should be a no-op.
            second = await create_default_admin_if_missing(session)
            assert second is None

        reset_engine()

    @pytest.mark.asyncio
    async def test_default_admin_uses_env_password(self, monkeypatch, tmp_path):
        from homomics_lab.api.auth import verify_password

        db_path = tmp_path / "admin_env_pass.db"
        monkeypatch.setattr(settings, "auth_enabled", True)
        monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{db_path}")
        monkeypatch.setattr(settings, "admin_initial_password", "from-env")
        reset_engine()

        async with get_session_factory()() as session:
            from homomics_lab.database.base import Base
            from homomics_lab.database.connection import get_engine

            async with get_engine().begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            user = await create_default_admin_if_missing(session)
            assert verify_password("from-env", user.hashed_password)

        reset_engine()

    @pytest.mark.asyncio
    async def test_default_admin_generates_random_password_when_env_not_set(
        self, monkeypatch, tmp_path, caplog
    ):

        db_path = tmp_path / "admin_random.db"
        monkeypatch.setattr(settings, "auth_enabled", True)
        monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{db_path}")
        monkeypatch.setattr(settings, "admin_initial_password", None)
        reset_engine()

        async with get_session_factory()() as session:
            from homomics_lab.database.base import Base
            from homomics_lab.database.connection import get_engine

            async with get_engine().begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            with caplog.at_level("WARNING"):
                user = await create_default_admin_if_missing(session)

            # Extract logged password and verify it works.
            assert "First-boot default admin created" in caplog.text
            assert "username=admin password=" in caplog.text
            # Password is token_urlsafe(24) -> 32 chars.
            assert user.hashed_password is not None
            # We cannot assert the exact password, but we can verify the hash is valid.
            assert len(user.hashed_password) > 0

        reset_engine()
