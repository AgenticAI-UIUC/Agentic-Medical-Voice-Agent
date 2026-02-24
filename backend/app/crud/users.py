from uuid import UUID

from app.core.security import get_password_hash, verify_password
from app.models import User, UserCreate, UserUpdate, UserUpdateMe

_USERS_BY_ID: dict[UUID, User] = {}


def get_user_by_email(*, email: str) -> User | None:
    return next(
        (u for u in _USERS_BY_ID.values() if u.email.lower() == email.lower()), None
    )


def get_user(*, user_id: UUID) -> User | None:
    return _USERS_BY_ID.get(user_id)


def get_users(*, skip: int = 0, limit: int = 100) -> tuple[list[User], int]:
    users = list(_USERS_BY_ID.values())
    users.sort(key=lambda u: u.created_at, reverse=True)
    total = len(users)
    return users[skip : skip + limit], total


def create_user(*, user_create: UserCreate) -> User:
    user = User(
        email=user_create.email,
        full_name=user_create.full_name,
        is_active=user_create.is_active,
        is_superuser=user_create.is_superuser,
        hashed_password=get_password_hash(user_create.password),
    )
    _USERS_BY_ID[user.id] = user
    return user


def update_user(*, user: User, user_update: UserUpdate) -> User:
    update_data = user_update.model_dump(exclude_unset=True)

    if "email" in update_data and update_data["email"] is not None:
        user.email = update_data["email"]
    if "full_name" in update_data:
        user.full_name = update_data["full_name"]
    if "is_active" in update_data and update_data["is_active"] is not None:
        user.is_active = update_data["is_active"]
    if "is_superuser" in update_data and update_data["is_superuser"] is not None:
        user.is_superuser = update_data["is_superuser"]
    if "password" in update_data and update_data["password"]:
        user.hashed_password = get_password_hash(update_data["password"])

    _USERS_BY_ID[user.id] = user
    return user


def update_user_me(*, user: User, user_update: UserUpdateMe) -> User:
    update_data = user_update.model_dump(exclude_unset=True)

    if "email" in update_data and update_data["email"] is not None:
        user.email = update_data["email"]
    if "full_name" in update_data:
        user.full_name = update_data["full_name"]

    _USERS_BY_ID[user.id] = user
    return user


def update_user_password(*, user: User, new_password: str) -> User:
    user.hashed_password = get_password_hash(new_password)
    _USERS_BY_ID[user.id] = user
    return user


def delete_user(*, user: User) -> None:
    _USERS_BY_ID.pop(user.id, None)


def authenticate(*, email: str, password: str) -> User | None:
    user = get_user_by_email(email=email)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def list_all_users() -> list[User]:
    return list(_USERS_BY_ID.values())
