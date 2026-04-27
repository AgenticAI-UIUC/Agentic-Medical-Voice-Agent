from __future__ import annotations

from typing import Annotated, Any, NoReturn

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from supabase_auth import AdminUserAttributes, SignInWithEmailAndPasswordCredentials
from supabase_auth.errors import AuthApiError, AuthError, AuthWeakPasswordError

from app.api.deps import (
    CurrentUser,
    get_current_active_user,
    get_current_superuser,
    public_user_dict,
    user_to_public,
)
from app.supabase import get_supabase

router = APIRouter(prefix="/users", tags=["users"])


class UserPublic(BaseModel):
    id: str
    email: str
    full_name: str | None = None
    is_active: bool
    is_superuser: bool
    created_at: str


class UsersPublic(BaseModel):
    data: list[UserPublic]
    count: int


class UserCreateIn(BaseModel):
    email: str
    password: str = Field(min_length=8)
    full_name: str | None = None
    is_active: bool = True
    is_superuser: bool = False

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        email = value.strip()
        if "@" not in email:
            raise ValueError("Enter a valid email address")
        return email


class UserUpdateIn(BaseModel):
    email: str | None = None
    password: str | None = Field(default=None, min_length=8)
    full_name: str | None = None
    is_active: bool | None = None
    is_superuser: bool | None = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        email = value.strip()
        if "@" not in email:
            raise ValueError("Enter a valid email address")
        return email


class UpdateMeIn(BaseModel):
    email: str | None = None
    full_name: str | None = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        email = value.strip()
        if "@" not in email:
            raise ValueError("Enter a valid email address")
        return email


class ChangeMyPasswordIn(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8)


def _auth_error_detail(exc: AuthError) -> str:
    if isinstance(exc, AuthApiError):
        data = exc.to_dict()
        message = data.get("message")
        if isinstance(message, str) and message:
            if message == "Database error creating new user":
                return (
                    "Supabase Auth could not create the user because a database "
                    "trigger failed. Check triggers on auth.users in Supabase."
                )
            return message
    return str(exc) or "Supabase Auth request failed"


def _raise_auth_error(exc: AuthError) -> NoReturn:
    if isinstance(exc, AuthWeakPasswordError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_auth_error_detail(exc),
        ) from exc
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=_auth_error_detail(exc),
    ) from exc


def _metadata(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _public_user(user: Any) -> UserPublic:
    return UserPublic.model_validate(public_user_dict(user_to_public(user)))


def _user_attributes(
    *,
    email: str | None = None,
    password: str | None = None,
    full_name: str | None = None,
    full_name_provided: bool = False,
    is_active: bool | None = None,
    is_superuser: bool | None = None,
    existing_user: Any | None = None,
) -> AdminUserAttributes:
    attrs: AdminUserAttributes = {}

    if email is not None:
        attrs["email"] = email
    if password is not None:
        attrs["password"] = password

    user_metadata = _metadata(getattr(existing_user, "user_metadata", None)).copy()
    if full_name_provided:
        normalized_full_name = (full_name or "").strip()
        if normalized_full_name:
            user_metadata["full_name"] = normalized_full_name
        else:
            user_metadata.pop("full_name", None)
    if full_name_provided or existing_user is None:
        attrs["user_metadata"] = user_metadata

    app_metadata = _metadata(getattr(existing_user, "app_metadata", None)).copy()
    if is_active is not None:
        app_metadata["is_active"] = is_active
        if is_active and getattr(existing_user, "banned_until", None):
            attrs["ban_duration"] = "none"
    if is_superuser is not None:
        app_metadata["is_superuser"] = is_superuser
    if is_active is not None or is_superuser is not None or existing_user is None:
        attrs["app_metadata"] = app_metadata

    return attrs


@router.get("/me", response_model=UserPublic)
def read_me(
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
) -> UserPublic:
    return UserPublic.model_validate(public_user_dict(current_user))


@router.patch("/me", response_model=UserPublic)
def update_me(
    payload: UpdateMeIn,
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
) -> UserPublic:
    attrs = _user_attributes(
        email=str(payload.email) if payload.email is not None else None,
        full_name=payload.full_name,
        full_name_provided="full_name" in payload.model_fields_set,
        existing_user=current_user.raw,
    )
    if not attrs:
        return UserPublic.model_validate(public_user_dict(current_user))

    try:
        response = get_supabase().auth.admin.update_user_by_id(current_user.id, attrs)
    except AuthError as exc:
        _raise_auth_error(exc)

    return _public_user(response.user)


@router.patch("/me/password")
def change_my_password(
    payload: ChangeMyPasswordIn,
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
) -> dict[str, str]:
    if not current_user.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current user does not have an email address",
        )

    sb = get_supabase()
    credentials: SignInWithEmailAndPasswordCredentials = {
        "email": current_user.email,
        "password": payload.current_password,
    }
    try:
        sb.auth.sign_in_with_password(credentials)
    except AuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        ) from exc

    try:
        sb.auth.admin.update_user_by_id(
            current_user.id,
            {"password": payload.new_password},
        )
    except AuthError as exc:
        _raise_auth_error(exc)

    return {"message": "Password updated"}


@router.get("", response_model=UsersPublic)
@router.get("/", response_model=UsersPublic, include_in_schema=False)
def read_users(
    current_user: Annotated[CurrentUser, Depends(get_current_superuser)],
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> UsersPublic:
    del current_user

    per_page = min(max(skip + limit, limit), 1000)
    try:
        users = get_supabase().auth.admin.list_users(page=1, per_page=per_page)
    except AuthError as exc:
        _raise_auth_error(exc)

    window = users[skip : skip + limit]
    return UsersPublic(
        data=[_public_user(user) for user in window],
        count=len(users),
    )


@router.post("", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
@router.post(
    "/",
    response_model=UserPublic,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
def create_user(
    payload: UserCreateIn,
    current_user: Annotated[CurrentUser, Depends(get_current_superuser)],
) -> UserPublic:
    del current_user

    attrs = _user_attributes(
        email=str(payload.email),
        password=payload.password,
        full_name=payload.full_name,
        full_name_provided=True,
        is_active=payload.is_active,
        is_superuser=payload.is_superuser,
    )
    attrs["email_confirm"] = True

    try:
        response = get_supabase().auth.admin.create_user(attrs)
    except AuthError as exc:
        _raise_auth_error(exc)

    return _public_user(response.user)


@router.patch("/{user_id}", response_model=UserPublic)
def update_user(
    user_id: str,
    payload: UserUpdateIn,
    current_user: Annotated[CurrentUser, Depends(get_current_superuser)],
) -> UserPublic:
    try:
        existing_response = get_supabase().auth.admin.get_user_by_id(user_id)
    except AuthError as exc:
        _raise_auth_error(exc)

    existing_user = existing_response.user
    requested_active = payload.is_active
    requested_superuser = payload.is_superuser
    if user_id == current_user.id:
        if requested_active is False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot deactivate your own account",
            )
        if requested_superuser is False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot remove your own admin access",
            )

    attrs = _user_attributes(
        email=str(payload.email) if payload.email is not None else None,
        password=payload.password,
        full_name=payload.full_name,
        full_name_provided="full_name" in payload.model_fields_set,
        is_active=requested_active,
        is_superuser=requested_superuser,
        existing_user=existing_user,
    )
    if not attrs:
        return _public_user(existing_user)

    try:
        response = get_supabase().auth.admin.update_user_by_id(user_id, attrs)
    except AuthError as exc:
        _raise_auth_error(exc)

    return _public_user(response.user)


@router.delete("/{user_id}")
def delete_user(
    user_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_superuser)],
) -> dict[str, str]:
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account",
        )

    try:
        get_supabase().auth.admin.delete_user(user_id)
    except AuthError as exc:
        _raise_auth_error(exc)

    return {"message": "User deleted"}
