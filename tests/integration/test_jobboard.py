"""Job board contract, ported from the original jobboard integration tests."""

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def _company(client: TestClient, headers: dict, slug: str = "acme") -> dict:
    r = client.post("/api/v1/companies/", json={"name": "ACME", "slug": slug}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def test_company_and_job_crud(client: TestClient, member_anna: dict) -> None:
    h = member_anna["headers"]
    company = _company(client, h)
    job_in = {
        "company_id": company["id"],
        "title": "Founding Engineer",
        "description": "Build things",
        "employment_type": "full_time",
        "work_arrangement": "hybrid",
        "experience_level": "mid",
        "slug": "founding-engineer",
    }
    r = client.post("/api/v1/jobs/", json=job_in, headers=h)
    assert r.status_code == 201, r.text
    job = r.json()
    assert job["status"] == "draft" and job["published_at"] is None
    assert job["posted_by_member_id"] == str(member_anna["id"])

    # publish stamps published_at once
    r = client.patch(f"/api/v1/jobs/{job['id']}", json={"status": "published"}, headers=h)
    assert r.status_code == 200 and r.json()["published_at"] is not None
    published_at = r.json()["published_at"]
    r = client.patch(
        f"/api/v1/jobs/{job['id']}", json={"title": "Founding Engineer (m/w/d)"}, headers=h
    )
    assert r.json()["published_at"] == published_at

    # reads are public and filterable
    r = client.get("/api/v1/jobs/", params={"status": "published", "q": "founding"})
    assert r.status_code == 200 and r.json()["total"] == 1
    r = client.get("/api/v1/jobs/slug/founding-engineer")
    assert r.status_code == 200
    r = client.get("/api/v1/jobs/", params={"employment_type": "internship"})
    assert r.json()["total"] == 0

    # writes need auth
    assert client.post("/api/v1/jobs/", json=job_in).status_code == 401

    r = client.delete(f"/api/v1/jobs/{job['id']}", headers=h)
    assert r.status_code == 204
    assert client.get(f"/api/v1/jobs/{job['id']}").status_code == 404


def test_duplicate_company_slug_is_conflict(client: TestClient, member_anna: dict) -> None:
    _company(client, member_anna["headers"], "dup")
    r = client.post(
        "/api/v1/companies/", json={"name": "Other", "slug": "dup"}, headers=member_anna["headers"]
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "conflict"


def test_salary_range_is_validated(client: TestClient, member_anna: dict) -> None:
    company = _company(client, member_anna["headers"], "sal")
    r = client.post(
        "/api/v1/jobs/",
        json={
            "company_id": company["id"],
            "title": "X",
            "description": "Y",
            "employment_type": "full_time",
            "work_arrangement": "remote",
            "experience_level": "mid",
            "salary_min": 100,
            "salary_max": 50,
        },
        headers=member_anna["headers"],
    )
    assert r.status_code == 422


def test_seekers_require_auth_and_link_member(client: TestClient, member_anna: dict) -> None:
    assert client.get("/api/v1/seekers/").status_code == 401
    r = client.post(
        "/api/v1/seekers/",
        json={"full_name": "Anna Test", "skills": ["python"]},
        headers=member_anna["headers"],
    )
    assert r.status_code == 201 and r.json()["member_id"] == str(member_anna["id"])
    r = client.get("/api/v1/seekers/", headers=member_anna["headers"])
    assert r.json()["total"] == 1


def test_a_job_is_attributed_to_the_caller_not_to_whoever_the_body_names(
    client: TestClient, member_anna: dict, member_ben: dict
) -> None:
    """Posting cannot put someone else's name and face on a job.

    The poster id used to be a body field that the server only filled in when it was left
    out, so a crafted POST could hang another member's name and avatar next to an
    attacker-chosen application link. It is server-assigned now, and the field is not part
    of the request schema at all.
    """
    company = _company(client, member_anna["headers"], "attrib")
    job_in = {
        "company_id": company["id"],
        "title": "Impersonation Bait",
        "description": "Apply here",
        "employment_type": "full_time",
        "work_arrangement": "remote",
        "experience_level": "mid",
        "posted_by_member_id": str(member_ben["id"]),
    }
    # The body cannot even carry the field any more.
    r = client.post("/api/v1/jobs/", json=job_in, headers=member_anna["headers"])
    assert r.status_code == 422, r.text

    job_in.pop("posted_by_member_id")
    r = client.post("/api/v1/jobs/", json=job_in, headers=member_anna["headers"])
    assert r.status_code == 201, r.text
    job = r.json()
    assert job["posted_by_member_id"] == str(member_anna["id"])

    # And it cannot be reassigned afterwards either.
    r = client.patch(
        f"/api/v1/jobs/{job['id']}",
        json={"posted_by_member_id": str(member_ben["id"])},
        headers=member_anna["headers"],
    )
    assert r.status_code == 422, r.text
    # Read it back as the poster: the job is still a draft, and a draft is only visible to
    # the member who posted it or to an admin.
    stored = client.get(f"/api/v1/jobs/{job['id']}", headers=member_anna["headers"]).json()
    assert stored["posted_by_member_id"] == str(member_anna["id"])


def test_a_seeker_profile_belongs_to_the_caller(
    client: TestClient, member_anna: dict, member_ben: dict
) -> None:
    r = client.post(
        "/api/v1/seekers/",
        json={"full_name": "Not Ben", "member_id": str(member_ben["id"])},
        headers=member_anna["headers"],
    )
    assert r.status_code == 422, r.text
    r = client.post(
        "/api/v1/seekers/", json={"full_name": "Anna Test"}, headers=member_anna["headers"]
    )
    assert r.status_code == 201 and r.json()["member_id"] == str(member_anna["id"])


def _job_body(company_id: str, **over) -> dict:
    body = {
        "company_id": company_id,
        "title": "Founding Engineer",
        "description": "Build things",
        "employment_type": "full_time",
        "work_arrangement": "remote",
        "experience_level": "mid",
    }
    body.update(over)
    return body


def test_another_member_cannot_edit_or_delete_what_you_posted(
    client: TestClient, member_anna: dict, member_ben: dict, admin_headers: dict
) -> None:
    """Signing in is not the same as owning the row.

    Every write route on this board used to take any authenticated caller and never compare
    them to the row: one token was enough to retitle, redirect or delete any job, any seeker
    profile and any company on the platform.
    """
    ha, hb = member_anna["headers"], member_ben["headers"]
    company = _company(client, ha, "owned")
    job = client.post("/api/v1/jobs/", json=_job_body(company["id"]), headers=ha).json()
    seeker = client.post("/api/v1/seekers/", json={"full_name": "Anna Test"}, headers=ha).json()

    # Ben holds a perfectly valid token and owns none of it.
    assert (
        client.patch(f"/api/v1/jobs/{job['id']}", json={"title": "Apply here"}, headers=hb)
    ).status_code == 403
    assert client.delete(f"/api/v1/jobs/{job['id']}", headers=hb).status_code == 403
    assert (
        client.patch(
            f"/api/v1/seekers/{seeker['id']}", json={"email": "ben@evil.example"}, headers=hb
        )
    ).status_code == 403
    assert client.delete(f"/api/v1/seekers/{seeker['id']}", headers=hb).status_code == 403
    assert (
        client.patch(f"/api/v1/companies/{company['id']}", json={"name": "Ben Inc"}, headers=hb)
    ).status_code == 403

    # Deleting a company cascades to every job posted under it, so it is admin only, even
    # for the member who added the record.
    assert client.delete(f"/api/v1/companies/{company['id']}", headers=ha).status_code == 403

    # Nothing moved.
    assert (
        client.get(f"/api/v1/jobs/{job['id']}", headers=ha).json()["title"] == "Founding Engineer"
    )
    assert client.get(f"/api/v1/seekers/{seeker['id']}", headers=ha).json()["email"] is None

    # The owner still can, and so can an admin.
    assert (
        client.patch(f"/api/v1/jobs/{job['id']}", json={"title": "Renamed"}, headers=ha)
    ).status_code == 200
    assert (
        client.patch(
            f"/api/v1/jobs/{job['id']}", json={"title": "Renamed twice"}, headers=admin_headers
        )
    ).status_code == 200
    assert (
        client.delete(f"/api/v1/companies/{company['id']}", headers=admin_headers).status_code
        == 204
    )


def test_a_draft_job_is_only_visible_to_its_poster(
    client: TestClient, member_anna: dict, member_ben: dict, admin_headers: dict
) -> None:
    """A draft is a draft. It used to be on the public board and readable without a token."""
    ha, hb = member_anna["headers"], member_ben["headers"]
    company = _company(client, ha, "drafts")
    job = client.post(
        "/api/v1/jobs/", json=_job_body(company["id"], slug="secret-role"), headers=ha
    ).json()
    assert job["status"] == "draft"

    assert client.get("/api/v1/jobs/").json()["total"] == 0
    assert client.get("/api/v1/jobs/", headers=hb).json()["total"] == 0
    # Asking for the drafts explicitly does not lift the pin either, anonymous or signed in.
    assert client.get("/api/v1/jobs/", params={"status": "draft"}).json()["total"] == 0
    assert client.get("/api/v1/jobs/", params={"status": "draft"}, headers=hb).json()["total"] == 0
    assert client.get(f"/api/v1/jobs/{job['id']}").status_code == 404
    assert client.get(f"/api/v1/jobs/{job['id']}", headers=hb).status_code == 404
    # Slug lookup is the same board under a different key, so it keeps the same pin, whether
    # the caller is anonymous or is a signed-in member who is not the poster.
    assert client.get("/api/v1/jobs/slug/secret-role").status_code == 404
    assert client.get("/api/v1/jobs/slug/secret-role", headers=hb).status_code == 404

    # The poster sees their own drafts, by id, by slug and in their own list.
    assert client.get(f"/api/v1/jobs/{job['id']}", headers=ha).status_code == 200
    assert client.get("/api/v1/jobs/slug/secret-role", headers=ha).status_code == 200
    mine = client.get(
        "/api/v1/jobs/",
        params={"posted_by_member_id": str(member_anna["id"]), "status": "draft"},
        headers=ha,
    )
    assert mine.json()["total"] == 1
    assert (
        client.get("/api/v1/jobs/", params={"status": "draft"}, headers=admin_headers).json()[
            "total"
        ]
        == 1
    )

    # Publishing puts it on the board for everyone.
    client.patch(f"/api/v1/jobs/{job['id']}", json={"status": "published"}, headers=ha)
    assert client.get("/api/v1/jobs/").json()["total"] == 1
    assert client.get(f"/api/v1/jobs/{job['id']}").status_code == 200


def test_a_confidential_salary_is_not_in_the_public_payload(
    client: TestClient, member_anna: dict, member_ben: dict, admin_headers: dict
) -> None:
    """``compensation_disclosure`` was stored and then ignored on every read."""
    ha, hb = member_anna["headers"], member_ben["headers"]
    company = _company(client, ha, "pay")
    job = client.post(
        "/api/v1/jobs/",
        json=_job_body(
            company["id"],
            status="published",
            salary_min=60000,
            salary_max=80000,
            salary_currency="EUR",
            compensation_disclosure="confidential",
        ),
        headers=ha,
    ).json()

    for headers in ({}, hb):
        seen = client.get(f"/api/v1/jobs/{job['id']}", **({"headers": headers} if headers else {}))
        body = seen.json()
        assert seen.status_code == 200, seen.text
        assert body["salary_min"] is None
        assert body["salary_max"] is None
        assert body["salary_currency"] is None
        # The disclosure itself is not a secret; the numbers behind it are.
        assert body["compensation_disclosure"] == "confidential"

    listed = client.get("/api/v1/jobs/", headers=hb).json()["items"][0]
    assert listed["salary_min"] is None

    # The poster and an admin still see what was entered.
    assert client.get(f"/api/v1/jobs/{job['id']}", headers=ha).json()["salary_min"] == "60000"
    assert (
        client.get(f"/api/v1/jobs/{job['id']}", headers=admin_headers).json()["salary_max"]
        == "80000"
    )

    # A range the poster chose to publish stays published.
    open_job = client.post(
        "/api/v1/jobs/",
        json=_job_body(
            company["id"],
            slug="open-pay",
            status="published",
            salary_min=1000,
            compensation_disclosure="public",
        ),
        headers=ha,
    ).json()
    assert client.get(f"/api/v1/jobs/{open_job['id']}", headers=hb).json()["salary_min"] == "1000"


def test_seeker_contact_details_are_only_for_the_seeker_and_an_admin(
    client: TestClient, member_anna: dict, member_ben: dict, admin_headers: dict
) -> None:
    """A seeker profile is a CV with a phone number on it, handed to every member."""
    ha, hb = member_anna["headers"], member_ben["headers"]
    seeker = client.post(
        "/api/v1/seekers/",
        json={
            "full_name": "Anna Test",
            "email": "anna.private@example.com",
            "phone": "+49 151 0000000",
            "resume_url": "https://example.com/anna.pdf",
            "headline": "Backend engineer",
        },
        headers=ha,
    ).json()

    as_ben = client.get(f"/api/v1/seekers/{seeker['id']}", headers=hb).json()
    assert as_ben["email"] is None
    assert as_ben["phone"] is None
    assert as_ben["resume_url"] is None
    # The profile is still useful, which is the point of redacting rather than hiding.
    assert as_ben["headline"] == "Backend engineer"
    assert client.get("/api/v1/seekers/", headers=hb).json()["items"][0]["email"] is None

    assert (
        client.get(f"/api/v1/seekers/{seeker['id']}", headers=ha).json()["phone"]
        == "+49 151 0000000"
    )
    assert (
        client.get(f"/api/v1/seekers/{seeker['id']}", headers=admin_headers).json()["email"]
        == "anna.private@example.com"
    )
