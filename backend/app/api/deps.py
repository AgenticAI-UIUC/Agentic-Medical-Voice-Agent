from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from supabase_auth.errors import AuthError

from app.config import settings
from app.supabase import get_supabase

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token",
    auto_error=False,
)


class CurrentUser:
    def __init__(
        self,
        *,
        id: str,
        email: str | None,
        full_name: str | None,
        is_active: bool,
        is_superuser: bool,
        created_at: str | None,
        raw: Any,
    ) -> None:
        self.id = id
        self.email = email
        self.full_name = full_name
        self.is_active = is_active
        self.is_superuser = is_superuser
        self.created_at = created_at
        self.raw = raw


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _metadata_bool(
    metadata: dict[str, Any],
    key: str,
    *,
    default: bool = False,
) -> bool:
    value = metadata.get(key)
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _to_iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def user_to_public(user: Any) -> CurrentUser:
    app_metadata = _as_dict(getattr(user, "app_metadata", None))
    user_metadata = _as_dict(getattr(user, "user_metadata", None))

    is_active = _metadata_bool(app_metadata, "is_active", default=True)
    if getattr(user, "deleted_at", None):
        is_active = False
    if getattr(user, "banned_until", None):
        is_active = False

    full_name = user_metadata.get("full_name") or user_metadata.get("name")

    return CurrentUser(
        id=str(getattr(user, "id")),
        email=getattr(user, "email", None),
        full_name=str(full_name) if full_name else None,
        is_active=is_active,
        is_superuser=_metadata_bool(app_metadata, "is_superuser", default=False),
        created_at=_to_iso(getattr(user, "created_at", None)),
        raw=user,
    )


def public_user_dict(user: CurrentUser) -> dict[str, Any]:
    return {
        "id": user.id,
        "email": user.email or "",
        "full_name": user.full_name,
        "is_active": user.is_active,
        "is_superuser": user.is_superuser,
        "created_at": user.created_at or "",
    }


def _credentials_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


TokenDep = Annotated[str | None, Depends(oauth2_scheme)]


def get_current_user(token: TokenDep) -> CurrentUser:
    if not token:
        raise _credentials_exception()

    try:
        response = get_supabase().auth.get_user(token)
    except AuthError as exc:
        raise _credentials_exception() from exc

    user = getattr(response, "user", None)
    if user is None:
        raise _credentials_exception()

    return user_to_public(user)


def get_current_active_user(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CurrentUser:
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    return current_user


def get_current_superuser(
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
) -> CurrentUser:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user does not have enough privileges",
        )
    return current_user
