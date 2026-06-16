"""Authentication and authorization dependencies for HomomicsLab.

Auth is opt-in via ``HOMOMICS_AUTH_ENABLED`` so local development keeps working.
When enabled, requests must carry a valid API key in the ``X-API-Key`` header or
``Authorization: Bearer <key>``.

This is intentionally minimal: a single shared key is sufficient for an
individual-user deployment. Multi-user deployments should add a user service
on top of this middleware.
"""

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from homomics_lab.config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)


def _extract_api_key(
    header_key: str | None = Security(api_key_header),
    bearer: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
) -> str | None:
    """Extract an API key from header or bearer token."""
    if header_key:
        return header_key
    if bearer and bearer.credentials:
        return bearer.credentials
    return None


def get_current_user(request: Request, api_key: str | None = Depends(_extract_api_key)) -> str:
    """Return a user identifier if auth is enabled, otherwise 'anonymous'.

    Raises:
        HTTPException 401/403 when auth is enabled and the key is missing/invalid.
    """
    if not settings.auth_enabled:
        request.state.user_id = "anonymous"
        return "anonymous"

    expected = settings.api_key
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Auth is enabled but no API_KEY is configured",
        )

    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Provide X-API-Key header or Authorization: Bearer <key>",
        )

    # Constant-time comparison to avoid timing attacks.
    import hmac
    if not hmac.compare_digest(api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
        )

    # In a multi-user deployment, derive user_id from the key/token here.
    user_id = "authenticated_user"
    request.state.user_id = user_id
    return user_id


class RequireAuth:
    """FastAPI dependency that enforces authentication on a route."""

    def __call__(self, user_id: str = Depends(get_current_user)) -> str:
        return user_id


require_auth = RequireAuth()
