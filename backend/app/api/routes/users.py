from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, HTTPException, Path, Query, status

from app import crud
from app.api.deps import CurrentSuperuser, CurrentUser
from app.core.security import verify_password
from app.models import (
    Message,
    UpdatePassword,
    UserCreate,
    UserPublic,
    UsersPublic,
    UserUpdate,
    UserUpdateMe,
)

router = APIRouter(prefix="/users", tags=["users"])


# ---------------- Current user endpoints ----------------


@router.get("/me")
def read_user_me(current_user: CurrentUser) -> UserPublic:
    return UserPublic.model_validate(current_user)


@router.patch("/me")
def update_user_me(
    current_user: CurrentUser,
    user_in: Annotated[UserUpdateMe, Body()],
) -> UserPublic:
    if user_in.email and user_in.email.lower() != current_user.email.lower():
        existing = crud.get_user_by_email(email=user_in.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already exists",
            )

    user = crud.update_user_me(user=current_user, user_update=user_in)
    return UserPublic.model_validate(user)


@router.patch("/me/password")
def update_password_me(
    current_user: CurrentUser,
    body: Annotated[UpdatePassword, Body()],
) -> Message:
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect password",
        )

    if body.current_password == body.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password cannot be the same as the current password",
        )

    crud.update_user_password(user=current_user, new_password=body.new_password)
    return Message(message="Password updated successfully")


# ---------------- Superuser endpoints ----------------


@router.get("/")
def read_users(
    current_superuser: CurrentSuperuser,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> UsersPublic:
    _ = current_superuser  # auth gate only

    users, count = crud.get_users(skip=skip, limit=limit)
    return UsersPublic(
        data=[UserPublic.model_validate(u) for u in users],
        count=count,
    )


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_user(
    current_superuser: CurrentSuperuser,
    user_in: Annotated[UserCreate, Body()],
) -> UserPublic:
    _ = current_superuser

    existing = crud.get_user_by_email(email=user_in.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    user = crud.create_user(user_create=user_in)
    return UserPublic.model_validate(user)


@router.get("/{user_id}")
def read_user_by_id(
    current_superuser: CurrentSuperuser,
    user_id: Annotated[UUID, Path()],
) -> UserPublic:
    _ = current_superuser

    user = crud.get_user(user_id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return UserPublic.model_validate(user)


@router.patch("/{user_id}")
def update_user(
    current_superuser: CurrentSuperuser,
    user_id: Annotated[UUID, Path()],
    user_in: Annotated[UserUpdate, Body()],
) -> UserPublic:
    _ = current_superuser

    user = crud.get_user(user_id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if user_in.email and user_in.email.lower() != user.email.lower():
        existing = crud.get_user_by_email(email=user_in.email)
        if existing and existing.id != user.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email already exists",
            )

    user = crud.update_user(user=user, user_update=user_in)
    return UserPublic.model_validate(user)


@router.delete("/{user_id}")
def delete_user(
    current_superuser: CurrentSuperuser,
    user_id: Annotated[UUID, Path()],
) -> Message:
    user = crud.get_user(user_id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Template-like safety guard: prevent deleting yourself
    if user.id == current_superuser.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superusers are not allowed to delete themselves",
        )

    crud.delete_user(user=user)
    return Message(message="User deleted successfully")
