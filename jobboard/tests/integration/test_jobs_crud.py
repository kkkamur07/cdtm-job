"""Jobs: live Supabase CRUD via API (creates a parent company for FK)."""

from __future__ import annotations

import pytest

from tests.integration.helpers import integration_slug

pytestmark = pytest.mark.integration


def test_job_create_update_delete_sequence(live_api_client, api_prefix: str) -> None:
    c = live_api_client
    companies_b = f"{api_prefix}/companies"
    jobs_b = f"{api_prefix}/jobs"

    slug = integration_slug("it-job-co")
    rc = c.post(
        f"{companies_b}/",
        json={
            "name": "Integration Job Parent Co",
            "slug": slug,
            "company_size_band": "startup",
        },
    )
    assert rc.status_code == 201, rc.text
    company_id = rc.json()["id"]

    job_slug = integration_slug("it-job")
    create_job = {
        "company_id": company_id,
        "title": "Integration Engineer",
        "slug": job_slug,
        "description": "Responsible for integration testing against Supabase.",
        "employment_type": "full_time",
        "work_arrangement": "hybrid",
        "experience_level": "mid",
        "summary": "created",
        "status": "draft",
    }
    rj = c.post(f"{jobs_b}/", json=create_job)
    assert rj.status_code == 201, rj.text
    job_id = rj.json()["id"]
    assert rj.json()["summary"] == "created"

    assert c.get(f"{jobs_b}/{job_id}").status_code == 200

    r_patch = c.patch(
        f"{jobs_b}/{job_id}",
        json={"summary": "updated-by-integration"},
    )
    assert r_patch.status_code == 200
    assert r_patch.json()["summary"] == "updated-by-integration"

    assert c.delete(f"{jobs_b}/{job_id}").status_code == 204
    assert c.get(f"{jobs_b}/{job_id}").status_code == 404

    assert c.delete(f"{companies_b}/{company_id}").status_code == 204
    assert c.get(f"{companies_b}/{company_id}").status_code == 404
