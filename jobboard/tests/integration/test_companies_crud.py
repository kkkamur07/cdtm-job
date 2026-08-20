"""Companies: live Supabase CRUD via API."""

from __future__ import annotations

import pytest

from tests.integration.helpers import integration_slug

pytestmark = pytest.mark.integration


def test_company_list_filters(live_api_client, api_prefix: str) -> None:
    c = live_api_client
    base = f"{api_prefix}/companies"
    slug = integration_slug("it-filter-co")

    r_create = c.post(
        f"{base}/",
        json={
            "name": "Filter Test Co",
            "slug": slug,
            "industry": "integration-testing",
            "hq_city": "Munich",
            "is_cdtm_startup": True,
        },
    )
    assert r_create.status_code == 201, r_create.text
    company_id = r_create.json()["id"]

    try:
        r_industry = c.get(f"{base}/", params={"industry": "integration-testing"})
        assert r_industry.status_code == 200, r_industry.text
        ids = {row["id"] for row in r_industry.json()["items"]}
        assert company_id in ids

        r_cdtm = c.get(f"{base}/", params={"is_cdtm_startup": True})
        assert r_cdtm.status_code == 200, r_cdtm.text
        assert company_id in {row["id"] for row in r_cdtm.json()["items"]}

        r_q = c.get(f"{base}/", params={"q": "Filter Test"})
        assert r_q.status_code == 200, r_q.text
        assert company_id in {row["id"] for row in r_q.json()["items"]}
    finally:
        c.delete(f"{base}/{company_id}")


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
