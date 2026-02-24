from tests.utils import get_auth_headers


def test_login_access_token_success_admin(client):
    response = client.post(
        "/api/v1/login/access-token",
        data={"username": "admin@example.com", "password": "changethis123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_access_token_success_alice(client):
    response = client.post(
        "/api/v1/login/access-token",
        data={"username": "alice@example.com", "password": "password123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_access_token_wrong_password(client):
    response = client.post(
        "/api/v1/login/access-token",
        data={"username": "alice@example.com", "password": "wrongpassword"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Incorrect email or password"


def test_test_token_requires_auth(client):
    response = client.post("/api/v1/login/test-token")
    assert response.status_code in (401, 403)  # FastAPI auth layer may return 401


def test_test_token_returns_current_user(client):
    headers = get_auth_headers(client, "alice@example.com", "password123")
    response = client.post("/api/v1/login/test-token", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "alice@example.com"
    assert data["is_superuser"] is False
