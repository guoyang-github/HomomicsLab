"""Authentication and authorization dependencies for HomomicsLab.

Auth is opt-in via ``HOMOMICS_AUTH_ENABLED`` so local development keeps working.
When enabled, requests must carry a valid JWT access token in the
``Authorization: Bearer <token>`` header, or a configured API key in either the
``X-API-Key`` header or ``Authorization: Bearer <key>``.

If ``HOMOMICS_OIDC_DISCOVERY_URL`` is set, JWTs are validated against the
provider's JWKS. Otherwise locally-issued JWTs are validated using
``HOMOMICS_JWT_SECRET_KEY``.
"""

import hmac
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from homomics_lab.config import settings
from homomics_lab.database.connection import get_async_session
from homomics_lab.database.models import User

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)
# Use pbkdf2_sha256 instead of bcrypt because newer ``bcrypt`` releases are
# incompatible with the passlib version currently pinned in this environment.
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserLogin(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: str
    tenant_id: str
    username: str
    role: str
    is_active: bool
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


# ---------------------------------------------------------------------------
# User lookup
# ---------------------------------------------------------------------------

async def get_user_by_username(session: AsyncSession, username: str) -> Optional[User]:
    result = await session.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def authenticate_user(session: AsyncSession, username: str, password: str) -> Optional[User]:
    user = await get_user_by_username(session, username)
    if user is None or not user.hashed_password:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token signed with the local secret key."""
    if not settings.jwt_secret_key:
        raise RuntimeError("jwt_secret_key is not configured")
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


# ---------------------------------------------------------------------------
# OIDC helpers
# ---------------------------------------------------------------------------

_oidc_jwks_cache: Dict[str, Any] = {}


async def _fetch_oidc_jwks(discovery_url: str) -> Optional[Dict[str, Any]]:
    """Fetch JWKS from an OIDC discovery document."""
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(discovery_url)
            resp.raise_for_status()
            config = resp.json()
            jwks_uri = config.get("jwks_uri")
            if not jwks_uri:
                return None
            jwks_resp = await client.get(jwks_uri)
            jwks_resp.raise_for_status()
            return jwks_resp.json()
    except Exception:
        return None


def _get_oidc_jwks(discovery_url: str) -> Optional[Dict[str, Any]]:
    """Synchronous accessor for cached JWKS (used during validation)."""
    return _oidc_jwks_cache.get(discovery_url)


async def refresh_oidc_jwks(discovery_url: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Refresh cached OIDC JWKS. Public so tests can prime the cache."""
    url = discovery_url or settings.oidc_discovery_url
    if not url:
        return None
    jwks = await _fetch_oidc_jwks(url)
    if jwks:
        _oidc_jwks_cache[url] = jwks
    return jwks


def verify_oidc_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify a JWT using the configured OIDC provider's JWKS.

    Returns the decoded payload on success, or ``None`` if validation fails.
    """
    discovery_url = settings.oidc_discovery_url
    if not discovery_url:
        return None

    jwks = _get_oidc_jwks(discovery_url)
    if jwks is None:
        return None

    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError:
        return None

    kid = unverified_header.get("kid")
    if not kid:
        return None

    key = None
    for k in jwks.get("keys", []):
        if k.get("kid") == kid:
            key = k
            break
    if key is None:
        return None

    try:
        payload = jwt.decode(
            token,
            key,
            algorithms=[settings.jwt_algorithm],
            audience=settings.oidc_client_id or None,
        )
    except JWTError:
        return None

    # Extract a stable user identifier from common OIDC claims.
    user_id = payload.get("sub") or payload.get("email") or payload.get("preferred_username")
    if not user_id:
        return None

    return {"user_id": str(user_id), "payload": payload}


# ---------------------------------------------------------------------------
# Token extraction
# ---------------------------------------------------------------------------

def _extract_api_key(
    header_key: Optional[str] = Security(api_key_header),
    bearer: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
) -> Optional[str]:
    """Extract an API key from header or bearer token."""
    if header_key:
        return header_key
    if bearer and bearer.credentials:
        return bearer.credentials
    return None


def _looks_like_jwt(token: str) -> bool:
    """Heuristic: JWTs have three dot-separated base64url segments."""
    parts = token.split(".")
    return len(parts) == 3 and all(len(p) > 0 for p in parts)


def _decode_local_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and validate a locally-issued JWT."""
    if not settings.jwt_secret_key:
        return None
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None

    if "sub" not in payload:
        return None
    return payload


async def _resolve_token_user_id(token: str) -> Optional[str]:
    """Resolve a bearer token to a user id using local JWT or OIDC."""
    if settings.oidc_discovery_url:
        oidc_result = verify_oidc_token(token)
        if oidc_result is None:
            # JWKS may not be cached yet; try once to refresh.
            await refresh_oidc_jwks()
            oidc_result = verify_oidc_token(token)
        if oidc_result:
            return oidc_result["user_id"]

    payload = _decode_local_token(token)
    if payload:
        return str(payload["sub"])

    return None


async def get_current_user(
    request: Request,
    api_key: Optional[str] = Depends(_extract_api_key),
) -> str:
    """Return a user identifier if auth is enabled, otherwise 'anonymous'.

    Resolution order:
      1. If auth is disabled -> 'anonymous'.
      2. Bearer token that looks like a JWT -> validate locally or via OIDC.
      3. Configured API key (via X-API-Key or Authorization Bearer) -> 'authenticated_user'.

    Raises:
        HTTPException 401/403/500 when auth is enabled and no valid credential is found.
    """
    if not settings.auth_enabled:
        request.state.user_id = "anonymous"
        return "anonymous"

    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing credentials. Provide Authorization: Bearer <token> or X-API-Key header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Attempt JWT / OIDC verification first so API keys that happen to have three
    # segments are not accidentally treated as JWTs.
    if _looks_like_jwt(api_key):
        user_id = await _resolve_token_user_id(api_key)
        if user_id:
            request.state.user_id = user_id
            return user_id

    # Fall back to configured single shared API key.
    expected = settings.api_key
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Auth is enabled but no API_KEY or JWT secret is configured",
        )

    if hmac.compare_digest(api_key, expected):
        user_id = "authenticated_user"
        request.state.user_id = user_id
        return user_id

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Invalid API key or token",
    )


class RequireAuth:
    """FastAPI dependency that enforces authentication on a route."""

    async def __call__(self, user_id: str = Depends(get_current_user)) -> str:
        return user_id


require_auth = RequireAuth()


# ---------------------------------------------------------------------------
# Auth router (OAuth2 token endpoint + current user)
# ---------------------------------------------------------------------------

auth_router = APIRouter(prefix="/auth", tags=["auth"])


@auth_router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_async_session),
):
    """OAuth2 password flow: exchange credentials for a JWT access token."""
    if not settings.auth_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authentication is disabled",
        )

    user = await authenticate_user(session, form_data.username, form_data.password)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token({"sub": user.id, "tenant_id": user.tenant_id, "role": user.role})
    return {"access_token": access_token, "token_type": "bearer"}


@auth_router.get("/me", response_model=UserOut)
async def read_current_user(
    request: Request,
    user_id: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Return the currently authenticated user profile."""
    if user_id == "anonymous":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    if user_id == "authenticated_user":
        # API-key authentication does not map to a database user.
        return UserOut(
            id=user_id,
            tenant_id="",
            username=user_id,
            role="admin",
            is_active=True,
        )

    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


# ---------------------------------------------------------------------------
# Bootstrap helpers
# ---------------------------------------------------------------------------

async def create_default_admin_if_missing(session: AsyncSession) -> Optional[User]:
    """Create a default admin user/tenant when auth is enabled and no users exist.

    This is intended for first-boot convenience only. In production, users and
    tenants should be provisioned through an admin CLI or onboarding flow.
    """
    result = await session.execute(select(User))
    if result.scalars().first() is not None:
        return None

    from homomics_lab.database.models import Tenant

    tenant_id = f"tenant_{uuid.uuid4().hex[:8]}"
    user_id = f"user_{uuid.uuid4().hex[:8]}"
    tenant = Tenant(id=tenant_id, name="Default")
    user = User(
        id=user_id,
        tenant_id=tenant_id,
        username="admin",
        hashed_password=get_password_hash("admin"),
        role="admin",
        is_active=True,
    )
    session.add(tenant)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user
