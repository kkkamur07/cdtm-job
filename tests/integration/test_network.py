"""Saved people and intro requests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration
API = "/api/v1/network"


def test_saved_people_and_intro_requests(
    client: TestClient, member_anna: dict, member_ben: dict
) -> None:
    ha, hb = member_anna["headers"], member_ben["headers"]
    r = client.put(f"{API}/saved/{member_ben['id']}", json={"note": "ask about VC"}, headers=ha)
    assert r.status_code == 200, r.text
    assert r.json()["member"]["slug"] == "ben-test" and r.json()["saved"]["note"] == "ask about VC"
    assert client.get(f"{API}/saved", headers=ha).json()["total"] == 1
    assert client.put(f"{API}/saved/{member_anna['id']}", json={}, headers=ha).status_code == 422

    r = client.post(
        f"{API}/intros",
        json={"target_member_id": str(member_ben["id"]), "message": "hi"},
        headers=ha,
    )
    assert r.status_code == 201, r.text
    req_id = r.json()["id"]
    intros = client.get(f"{API}/intros", headers=hb).json()
    assert intros["total"] == 1 and intros["items"][0]["requester"]["slug"] == "anna-test"
    # requester cannot accept, target can
    assert (
        client.post(
            f"{API}/intros/{req_id}/respond", json={"status": "accepted"}, headers=ha
        ).status_code
        == 403
    )
    r = client.post(f"{API}/intros/{req_id}/respond", json={"status": "accepted"}, headers=hb)
    assert r.status_code == 200 and r.json()["status"] == "accepted"
    assert (
        client.post(
            f"{API}/intros/{req_id}/respond", json={"status": "declined"}, headers=hb
        ).status_code
        == 409
    )

    assert client.delete(f"{API}/saved/{member_ben['id']}", headers=ha).status_code == 204
    assert client.get(f"{API}/saved", headers=ha).json() == {"items": [], "total": 0}
