from fastapi.testclient import TestClient


def get_access_token(client: TestClient, username: str, password: str) -> str:
    response = client.post(
        "/api/v1/login/access-token",
        data={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    return payload["access_token"]


def get_auth_headers(
    client: TestClient, username: str, password: str
) -> dict[str, str]:
    token = get_access_token(client, username, password)
    return {"Authorization": f"Bearer {token}"}
