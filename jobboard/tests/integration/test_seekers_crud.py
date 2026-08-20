"""Seekers: live Supabase CRUD via API."""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.integration


def test_seeker_create_update_delete_sequence(live_api_client, api_prefix: str) -> None:
    c = live_api_client
    base = f"{api_prefix}/seekers"
    token = uuid.uuid4().hex[:10]

    create_body = {
        "full_name": f"Integration Seeker {token}",
        "email": f"it-{token}@example.com",
        "headline": "created",
    }
    r_create = c.post(f"{base}/", json=create_body)
    assert r_create.status_code == 201, r_create.text
    row = r_create.json()
    seeker_id = row["id"]
    assert row["headline"] == "created"

    r_get = c.get(f"{base}/{seeker_id}")
    assert r_get.status_code == 200

    r_patch = c.patch(
        f"{base}/{seeker_id}",
        json={"headline": "updated-by-integration"},
    )
    assert r_patch.status_code == 200
    assert r_patch.json()["headline"] == "updated-by-integration"

    r_del = c.delete(f"{base}/{seeker_id}")
    assert r_del.status_code == 204

    assert c.get(f"{base}/{seeker_id}").status_code == 404
