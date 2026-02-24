import os

from app.core.security import get_password_hash
from app.crud.users import _USERS_BY_ID
from app.models import User


def seed_mock_data() -> None:
    if _USERS_BY_ID:
        return

    if os.getenv("ENVIRONMENT", "local") != "local":
        return

    admin = User(
        email="admin@example.com",
        full_name="Admin User",
        is_active=True,
        is_superuser=True,
        hashed_password=get_password_hash(
            os.getenv("SEED_ADMIN_PASSWORD", "changethis123")
        ),
    )
    alice = User(
        email="alice@example.com",
        full_name="Alice",
        is_active=True,
        is_superuser=False,
        hashed_password=get_password_hash(
            os.getenv("SEED_USER_PASSWORD", "password123")
        ),
    )

    _USERS_BY_ID[admin.id] = admin
    _USERS_BY_ID[alice.id] = alice
