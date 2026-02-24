from app.crud.seed import seed_mock_data
from app.crud.users import (
    authenticate,
    create_user,
    delete_user,
    get_user,
    get_user_by_email,
    get_users,
    list_all_users,
    update_user,
    update_user_me,
    update_user_password,
)

__all__ = [
    "authenticate",
    "create_user",
    "delete_user",
    "get_user",
    "get_user_by_email",
    "get_users",
    "list_all_users",
    "reset_mock_data",
    "seed_mock_data",
    "update_user",
    "update_user_me",
    "update_user_password",
]


def reset_mock_data() -> None:
    from app.crud.users import _USERS_BY_ID

    _USERS_BY_ID.clear()
    seed_mock_data()


seed_mock_data()
