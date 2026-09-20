"""
app/api/routes/auth.py
Authentication routes:
  POST  /auth/login  — exchange email+password for a Supabase JWT
  GET   /auth/me      — return identity of the currently authenticated user
  PATCH /auth/me      — update editable profile fields (currently: full_name)
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.database import get_supabase
from app.core.security import get_current_user
from app.schemas.user import UpdateProfileRequest, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


# ── Request / response schemas (local, not shared) ────────────────────────────

class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/login", response_model=LoginResponse, status_code=status.HTTP_200_OK)
async def login(body: LoginRequest) -> LoginResponse:
    """
    Authenticate with Supabase using email + password.
    Returns the Supabase-issued JWT on success.
    """
    from supabase import create_client  # lazy import — avoid top-level side-effects

    settings = get_settings()
    try:
        client = create_client(settings.supabase_url, settings.supabase_anon_key)
        response = client.auth.sign_in_with_password(
            {"email": body.email, "password": body.password}
        )
        return LoginResponse(access_token=response.session.access_token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {exc}",
        )


@router.get("/me", response_model=UserOut)
async def me(
    current_user: Annotated[UserOut, Depends(get_current_user)],
) -> UserOut:
    """Return the identity of the currently authenticated user."""
    return current_user


@router.patch("/me", response_model=UserOut)
async def update_me(
    body: UpdateProfileRequest,
    current_user: Annotated[UserOut, Depends(get_current_user)],
) -> UserOut:
    """
    Update the caller's own display name.

    Writes to Supabase Auth's user_metadata via the service-role admin API
    (the anon/user JWT alone cannot change other users, but every caller here
    is only ever touching their own `sub`, taken from their verified token —
    never a client-supplied id).
    """
    name = body.full_name.strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Name cannot be empty")

    try:
        get_supabase().auth.admin.update_user_by_id(
            current_user.id, {"user_metadata": {"full_name": name}}
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not update profile: {exc}",
        )

    return UserOut(id=current_user.id, email=current_user.email, role=current_user.role, full_name=name)
