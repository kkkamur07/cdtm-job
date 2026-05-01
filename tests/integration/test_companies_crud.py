"""Companies: live Supabase CRUD via API."""

from __future__ import annotations

import pytest

from tests.integration.helpers import integration_slug

pytestmark = pytest.mark.integration


def test_company_create_update_delete_sequence(live_api_client, api_prefix: str) -> None:
    c = live_api_client
    base = f"{api_prefix}/companies"
    slug = integration_slug("it-co")

    create_body = {
        "name": "Integration Test Co",
        "slug": slug,
        "short_description": "created",
        "company_size_band": "startup",
        "is_cdtm_startup": False,
    }

    r_create = c.post(f"{base}/", json=create_body)
    assert r_create.status_code == 201, r_create.text
    row = r_create.json()
    company_id = row["id"]
    assert row["slug"] == slug
    assert row["short_description"] == "created"

    r_get = c.get(f"{base}/{company_id}")
    assert r_get.status_code == 200, r_get.text
    assert r_get.json()["id"] == company_id

    r_patch = c.patch(
        f"{base}/{company_id}",
        json={"short_description": "updated-by-integration"},
    )
    assert r_patch.status_code == 200, r_patch.text
    assert r_patch.json()["short_description"] == "updated-by-integration"

    r_get2 = c.get(f"{base}/{company_id}")
    assert r_get2.status_code == 200
    assert r_get2.json()["short_description"] == "updated-by-integration"

    r_del = c.delete(f"{base}/{company_id}")
    assert r_del.status_code == 204, r_del.text

    r_gone = c.get(f"{base}/{company_id}")
    assert r_gone.status_code == 404
