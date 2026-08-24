import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def test_health_ok(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "database": "ok"}


def test_error_envelope_and_security_headers(client: TestClient) -> None:
    r = client.get("/api/v1/jobs/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404
    body = r.json()["error"]
    assert body["code"] == "not_found"
    assert body["ref"] == r.headers["X-Error-ID"]
    assert r.headers["X-Content-Type-Options"] == "nosniff"


def test_auth_required_for_members(client: TestClient) -> None:
    r = client.get("/api/v1/members/")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"
