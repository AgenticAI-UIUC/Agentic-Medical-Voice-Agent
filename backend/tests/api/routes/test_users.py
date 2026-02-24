from tests.utils import get_auth_headers


def test_read_users_me(client):
    headers = get_auth_headers(client, "alice@example.com", "password123")
    response = client.get("/api/v1/users/me", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "alice@example.com"
    assert data["is_superuser"] is False


def test_read_users_me_requires_auth(client):
    response = client.get("/api/v1/users/me")
    assert response.status_code in (401, 403)


def test_read_users_admin_only_forbidden_for_normal_user(client):
    headers = get_auth_headers(client, "alice@example.com", "password123")
    response = client.get("/api/v1/users/", headers=headers)
    assert response.status_code == 403


def test_read_users_as_admin(client):
    headers = get_auth_headers(client, "admin@example.com", "changethis123")
    response = client.get("/api/v1/users/", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "count" in data
    assert data["count"] >= 2


def test_update_me_email_conflict(client):
    # Alice tries to change email to admin's email
    headers = get_auth_headers(client, "alice@example.com", "password123")
    response = client.patch(
        "/api/v1/users/me",
        headers=headers,
        json={"email": "admin@example.com"},
    )
    assert response.status_code == 409


def test_update_me_password_success_and_login_with_new_password(client):
    headers = get_auth_headers(client, "alice@example.com", "password123")

    response = client.patch(
        "/api/v1/users/me/password",
        headers=headers,
        json={
            "current_password": "password123",
            "new_password": "newpassword123",
        },
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Password updated successfully"

    # Old password should fail
    old_login = client.post(
        "/api/v1/login/access-token",
        data={"username": "alice@example.com", "password": "password123"},
    )
    assert old_login.status_code == 400

    # New password should work
    new_login = client.post(
        "/api/v1/login/access-token",
        data={"username": "alice@example.com", "password": "newpassword123"},
    )
    assert new_login.status_code == 200


def test_admin_create_get_update_delete_user(client):
    admin_headers = get_auth_headers(client, "admin@example.com", "changethis123")

    # Create
    create_res = client.post(
        "/api/v1/users/",
        headers=admin_headers,
        json={
            "email": "bob@example.com",
            "full_name": "Bob",
            "is_active": True,
            "is_superuser": False,
            "password": "password123",
        },
    )
    assert create_res.status_code == 201, create_res.text
    created = create_res.json()
    user_id = created["id"]
    assert created["email"] == "bob@example.com"

    # Get by ID
    get_res = client.get(f"/api/v1/users/{user_id}", headers=admin_headers)
    assert get_res.status_code == 200
    assert get_res.json()["email"] == "bob@example.com"

    # Update
    patch_res = client.patch(
        f"/api/v1/users/{user_id}",
        headers=admin_headers,
        json={"full_name": "Bob Updated", "is_active": False},
    )
    assert patch_res.status_code == 200
    patched = patch_res.json()
    assert patched["full_name"] == "Bob Updated"
    assert patched["is_active"] is False

    # Delete
    delete_res = client.delete(f"/api/v1/users/{user_id}", headers=admin_headers)
    assert delete_res.status_code == 200
    assert delete_res.json()["message"] == "User deleted successfully"

    # Should not exist now
    get_deleted = client.get(f"/api/v1/users/{user_id}", headers=admin_headers)
    assert get_deleted.status_code == 404
