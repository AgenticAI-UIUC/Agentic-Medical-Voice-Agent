from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient
from supabase_auth.errors import AuthError

from app.api import deps, login, users


def _make_user(
    *,
    user_id: str = "user-1",
    email: str = "staff@example.com",
    full_name: str | None = "Staff Member",
    is_active: bool = True,
    is_superuser: bool = False,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=user_id,
        email=email,
        created_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        app_metadata={
            "is_active": is_active,
            "is_superuser": is_superuser,
        },
        user_metadata={"full_name": full_name} if full_name else {},
        banned_until=None,
        deleted_at=None,
    )


class FakeAdminAuth:
    def __init__(self, auth: FakeAuth) -> None:
        self.auth = auth
        self.created_attrs: dict[str, Any] | None = None
        self.signed_out_token: str | None = None

    def list_users(self, page: int | None = None, per_page: int | None = None):
        del page, per_page
        return list(self.auth.admin_users)

    def create_user(self, attrs: dict[str, Any]):
        self.created_attrs = attrs
        user = _make_user(
            user_id="created-user",
            email=attrs["email"],
            full_name=attrs.get("user_metadata", {}).get("full_name"),
            is_active=attrs.get("app_metadata", {}).get("is_active", True),
            is_superuser=attrs.get("app_metadata", {}).get("is_superuser", False),
        )
        return SimpleNamespace(user=user)

    def sign_out(self, jwt: str, scope: str = "global") -> None:
        del scope
        self.signed_out_token = jwt


class FakeAuth:
    def __init__(self, current_user: SimpleNamespace) -> None:
        self.current_user = current_user
        self.admin_users = [current_user]
        self.last_credentials: dict[str, str] | None = None
        self.last_refresh_token: str | None = None
        self.admin = FakeAdminAuth(self)

    def sign_in_with_password(self, credentials: dict[str, str]):
        self.last_credentials = credentials
        return SimpleNamespace(
            user=self.current_user,
            session=SimpleNamespace(
                access_token="access-token",
                refresh_token="refresh-token",
                token_type="bearer",
                expires_in=3600,
                user=self.current_user,
            ),
        )

    def refresh_session(self, refresh_token: str):
        self.last_refresh_token = refresh_token
        if refresh_token != "refresh-token":
            raise AuthError("Invalid refresh token", None)
        return SimpleNamespace(
            user=self.current_user,
            session=SimpleNamespace(
                access_token="refreshed-access-token",
                refresh_token="rotated-refresh-token",
                token_type="bearer",
                expires_in=3600,
                user=self.current_user,
            ),
        )

    def get_user(self, jwt: str):
        if jwt != "valid-token":
            return SimpleNamespace(user=None)
        return SimpleNamespace(user=self.current_user)


class FakeSupabase:
    def __init__(self, current_user: SimpleNamespace) -> None:
        self.auth = FakeAuth(current_user)


def _client_for(*routers: Any) -> TestClient:
    app = FastAPI()
    for router in routers:
        app.include_router(router, prefix="/api/v1")
    return TestClient(app)


def test_login_access_token_uses_supabase_password_auth(monkeypatch) -> None:
    sb = FakeSupabase(_make_user())
    monkeypatch.setattr(login, "get_supabase", lambda: sb)

    with _client_for(login.router) as client:
        response = client.post(
            "/api/v1/login/access-token",
            data={"username": "staff@example.com", "password": "password123"},
        )

    assert response.status_code == 200
    assert response.json()["access_token"] == "access-token"
    assert response.json()["refresh_token"] == "refresh-token"
    assert sb.auth.last_credentials == {
        "email": "staff@example.com",
        "password": "password123",
    }


def test_login_rejects_inactive_user(monkeypatch) -> None:
    sb = FakeSupabase(_make_user(is_active=False))
    monkeypatch.setattr(login, "get_supabase", lambda: sb)

    with _client_for(login.router) as client:
        response = client.post(
            "/api/v1/login/access-token",
            data={"username": "staff@example.com", "password": "password123"},
        )

    assert response.status_code == 403
    assert response.json() == {"detail": "Account is pending admin approval"}
    assert sb.auth.admin.signed_out_token == "access-token"


def test_refresh_access_token_uses_supabase_refresh_token(monkeypatch) -> None:
    sb = FakeSupabase(_make_user())
    monkeypatch.setattr(login, "get_supabase", lambda: sb)

    with _client_for(login.router) as client:
        response = client.post(
            "/api/v1/login/refresh",
            json={"refresh_token": "refresh-token"},
        )

    assert response.status_code == 200
    assert response.json()["access_token"] == "refreshed-access-token"
    assert response.json()["refresh_token"] == "rotated-refresh-token"
    assert sb.auth.last_refresh_token == "refresh-token"


def test_refresh_access_token_rejects_invalid_refresh_token(monkeypatch) -> None:
    sb = FakeSupabase(_make_user())
    monkeypatch.setattr(login, "get_supabase", lambda: sb)

    with _client_for(login.router) as client:
        response = client.post(
            "/api/v1/login/refresh",
            json={"refresh_token": "invalid-refresh-token"},
        )

    assert response.status_code == 401
    assert response.json() == {"detail": "Could not refresh session"}


def test_refresh_rejects_inactive_user(monkeypatch) -> None:
    sb = FakeSupabase(_make_user(is_active=False))
    monkeypatch.setattr(login, "get_supabase", lambda: sb)

    with _client_for(login.router) as client:
        response = client.post(
            "/api/v1/login/refresh",
            json={"refresh_token": "refresh-token"},
        )

    assert response.status_code == 403
    assert response.json() == {"detail": "Account is pending admin approval"}
    assert sb.auth.admin.signed_out_token == "refreshed-access-token"


def test_read_me_returns_supabase_user_metadata(monkeypatch) -> None:
    sb = FakeSupabase(_make_user(is_superuser=True))
    monkeypatch.setattr(deps, "get_supabase", lambda: sb)

    with _client_for(users.router) as client:
        response = client.get(
            "/api/v1/users/me",
            headers={"Authorization": "Bearer valid-token"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "id": "user-1",
        "email": "staff@example.com",
        "full_name": "Staff Member",
        "is_active": True,
        "is_superuser": True,
        "created_at": "2026-04-01T00:00:00+00:00",
    }


def test_users_list_requires_superuser(monkeypatch) -> None:
    sb = FakeSupabase(_make_user(is_superuser=False))
    monkeypatch.setattr(deps, "get_supabase", lambda: sb)
    monkeypatch.setattr(users, "get_supabase", lambda: sb)

    with _client_for(users.router) as client:
        response = client.get(
            "/api/v1/users/",
            headers={"Authorization": "Bearer valid-token"},
        )

    assert response.status_code == 403


def test_create_user_maps_admin_flags_to_supabase_metadata(monkeypatch) -> None:
    sb = FakeSupabase(_make_user(is_superuser=True))
    monkeypatch.setattr(deps, "get_supabase", lambda: sb)
    monkeypatch.setattr(users, "get_supabase", lambda: sb)

    with _client_for(users.router) as client:
        response = client.post(
            "/api/v1/users/",
            headers={"Authorization": "Bearer valid-token"},
            json={
                "email": "doctor@example.com",
                "password": "password123",
                "full_name": "Dr. Example",
                "is_active": True,
                "is_superuser": False,
            },
        )

    assert response.status_code == 201
    assert sb.auth.admin.created_attrs == {
        "email": "doctor@example.com",
        "password": "password123",
        "user_metadata": {"full_name": "Dr. Example"},
        "app_metadata": {"is_active": True, "is_superuser": False},
        "email_confirm": True,
    }


def test_logout_invalidates_supabase_session(monkeypatch) -> None:
    sb = FakeSupabase(_make_user())
    monkeypatch.setattr(deps, "get_supabase", lambda: sb)
    monkeypatch.setattr(login, "get_supabase", lambda: sb)

    with _client_for(login.router) as client:
        response = client.post(
            "/api/v1/login/logout",
            headers={"Authorization": "Bearer valid-token"},
        )

    assert response.status_code == 200
    assert sb.auth.admin.signed_out_token == "valid-token"
