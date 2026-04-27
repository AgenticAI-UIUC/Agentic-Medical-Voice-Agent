from __future__ import annotations

from typing import Annotated
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from supabase_auth import SignInWithEmailAndPasswordCredentials
from supabase_auth.errors import AuthError

from app.api.deps import (
    CurrentUser,
    get_current_active_user,
    user_to_public,
)
from app.supabase import get_supabase

router = APIRouter(prefix="/login", tags=["login"])


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: str | None = None
    expires_in: int | None = None


async def _read_login_form(request: Request) -> tuple[str, str]:
    body = (await request.body()).decode("utf-8")
    form = parse_qs(body, keep_blank_values=True)
    username = (form.get("username") or [""])[0].strip()
    password = (form.get("password") or [""])[0]
    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Email and password are required",
        )
    return username, password


@router.post("/access-token", response_model=TokenResponse)
async def login_access_token(request: Request) -> TokenResponse:
    email, password = await _read_login_form(request)
    credentials: SignInWithEmailAndPasswordCredentials = {
        "email": email,
        "password": password,
    }

    try:
        response = get_supabase().auth.sign_in_with_password(credentials)
    except AuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        ) from exc

    session = getattr(response, "session", None)
    if session is None or not getattr(session, "access_token", None):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    user = getattr(response, "user", None) or getattr(session, "user", None)
    if user is not None and not user_to_public(user).is_active:
        try:
            get_supabase().auth.admin.sign_out(session.access_token)
        except AuthError:
            pass
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is pending admin approval",
        )

    return TokenResponse(
        access_token=session.access_token,
        token_type=getattr(session, "token_type", "bearer") or "bearer",
        refresh_token=getattr(session, "refresh_token", None),
        expires_in=getattr(session, "expires_in", None),
    )


@router.post("/logout")
def logout(
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
    request: Request,
) -> dict[str, str]:
    auth_header = request.headers.get("authorization", "")
    scheme, _, token = auth_header.partition(" ")

    if scheme.lower() == "bearer" and token:
        try:
            get_supabase().auth.admin.sign_out(token)
        except AuthError:
            pass

    return {"message": f"Signed out {current_user.email or current_user.id}"}
