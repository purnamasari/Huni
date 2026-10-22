import pytest


@pytest.mark.django_db
def test_health_reports_database_and_postgis(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["postgis"]
