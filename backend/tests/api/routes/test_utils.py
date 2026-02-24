def test_health_check(client):
    response = client.get("/api/v1/utils/health-check")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
