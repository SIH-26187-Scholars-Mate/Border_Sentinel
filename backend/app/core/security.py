"""
app/core/security.py
JWT decode/verify helpers and FastAPI dependency for authenticated routes.

Supabase JWTs are HS256-signed with the project's JWT Secret (same value
we store in JWT_SECRET).  We also expose verify_service_key() here for
the AI ingest endpoint (Phase 5) — it checks a static shared secret
instead of a user token.
"""
from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings
from app.schemas.user import TokenPayload, UserOut

_bearer = HTTPBearer(auto_error=True)


# ── JWT helpers ───────────────────────────────────────────────────────────────
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientError

_jwks_client: PyJWKClient | None = None

def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(get_settings().supabase_jwks_url)
    return _jwks_client

def decode_token(token: str) -> TokenPayload:
    try:
        signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256"],
            options={"verify_aud": False},
        )
        return TokenPayload(**payload)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired")
    except (jwt.InvalidTokenError, PyJWKClientError, ValueError) as exc:
        # Malformed/unconfigured JWKS data must not turn an invalid token into
        # a 500. Return the same 401 clients expect for any bad credential.
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {exc}")


# ── FastAPI dependencies ──────────────────────────────────────────────────────

async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> UserOut:
    """
    Dependency: extract Bearer token from Authorization header, verify it,
    and return the resolved UserOut.  Raises 401 on any failure.
    """
    payload = decode_token(credentials.credentials)
    if not payload.sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload missing 'sub'",
        )
    return UserOut(
        id=payload.sub,
        email=payload.email or "",
        role=payload.role or "authenticated",
        full_name=(payload.user_metadata or {}).get("full_name"),
    )


async def verify_service_key(
    x_service_key: Annotated[str, Header(alias="X-Service-Key")],
) -> None:
    """
    Dependency (Phase 5): verify a static shared secret sent by the AI service.
    The key must match the dedicated AI_SERVICE_KEY. It is intentionally
    separate from the Supabase service-role key.
    """
    settings = get_settings()
    if x_service_key != settings.ai_service_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing service key",
        )
