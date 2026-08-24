"""Company curation, company search and the reader-dependent parts of the job list.

The board's company records had no test that ever read one back by slug, listed them with
a filter, or edited one successfully: every existing company test stops at a 403 or a 409.
These cover the paths a curator and a reader actually walk, plus the two job reads (the
list and the slug lookup) whose salary redaction depends on who is asking.
"""

from __future__ import annotations

import contextlib
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from backend.core.exceptions import AppError, ConflictError
from backend.core.settings import get_database_settings
from backend.jobboard.application.commands import CompanyCreate, CompanyUpdate
from backend.jobboard.application.ports import CompanyFilters
from backend.jobboard.infrastructure.company_repository import SqlCompanyRepository

pytestmark = pytest.mark.integration


def _create_company(client: TestClient, headers: dict, **body) -> dict:
    payload = {"name": "ACME", "slug": "acme"}
    payload.update(body)
    r = client.post("/api/v1/companies/", json=payload, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


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


# ---- company curation ------------------------------------------------------------------


def test_a_company_is_attributed_to_its_curator_who_may_then_correct_it(
    client: TestClient, member_anna: dict, member_ben: dict, admin_headers: dict
) -> None:
    """Who added the record is what decides who may fix it later.

    The attribution is server-assigned from the caller, and it is the only thing standing
    between "the member who curated this employer" and "anybody with a token", so it has to
    survive the write and come back on the read.
    """
    ha, hb = member_anna["headers"], member_ben["headers"]
    company = _create_company(client, ha, slug="curated")
    assert company["created_by_member_id"] == str(member_anna["id"])
    fetched = client.get(f"/api/v1/companies/{company['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["created_by_member_id"] == str(member_anna["id"])

    # Somebody else's token does not curate this record.
    assert (
        client.patch(f"/api/v1/companies/{company['id']}", json={"name": "Ben Inc"}, headers=hb)
    ).status_code == 403

    # The curator does, and the correction is stored, not just echoed.
    r = client.patch(
        f"/api/v1/companies/{company['id']}",
        json={"name": "ACME GmbH", "industry": "fintech"},
        headers=ha,
    )
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "ACME GmbH"
    assert r.json()["industry"] == "fintech"
    stored = client.get(f"/api/v1/companies/{company['id']}").json()
    assert stored["name"] == "ACME GmbH"
    assert stored["industry"] == "fintech"
    # The edit does not reassign the record to whoever last touched it.
    assert stored["created_by_member_id"] == str(member_anna["id"])

    # An admin may correct any record.
    r = client.patch(
        f"/api/v1/companies/{company['id']}", json={"name": "ACME SE"}, headers=admin_headers
    )
    assert r.status_code == 200 and r.json()["name"] == "ACME SE"

    # An id that is not on the board is a 404, not a silent success.
    r = client.patch(
        f"/api/v1/companies/{uuid.uuid4()}", json={"name": "Ghost"}, headers=admin_headers
    )
    assert r.status_code == 404


def test_a_company_patch_only_moves_the_fields_it_names(
    client: TestClient, member_anna: dict
) -> None:
    """A partial update is partial: the fields left out keep the values they had."""
    ha = member_anna["headers"]
    company = _create_company(
        client,
        ha,
        slug="partial",
        industry="biotech",
        hq_city="Munich",
        short_description="Grows things in dishes",
        is_cdtm_startup=True,
    )

    r = client.patch(f"/api/v1/companies/{company['id']}", json={"name": "Renamed"}, headers=ha)
    assert r.status_code == 200, r.text
    after = r.json()
    assert after["name"] == "Renamed"
    assert after["industry"] == "biotech"
    assert after["hq_city"] == "Munich"
    assert after["short_description"] == "Grows things in dishes"
    assert after["is_cdtm_startup"] is True
    assert after["updated_at"] >= company["updated_at"]

    # A patch that names nothing changes nothing, and is still the record, not a 404.
    r = client.patch(f"/api/v1/companies/{company['id']}", json={}, headers=ha)
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "Renamed"
    assert r.json()["industry"] == "biotech"


def test_a_company_is_readable_by_slug(client: TestClient, member_anna: dict) -> None:
    ha = member_anna["headers"]
    first = _create_company(client, ha, name="First", slug="first-co")
    _create_company(client, ha, name="Second", slug="second-co")

    r = client.get("/api/v1/companies/slug/first-co")
    assert r.status_code == 200, r.text
    assert r.json()["id"] == first["id"]
    assert r.json()["name"] == "First"
    assert client.get("/api/v1/companies/slug/no-such-company").status_code == 404


# ---- company search --------------------------------------------------------------------


@pytest.fixture
def three_companies(client: TestClient, member_anna: dict) -> list[dict]:
    """Alpha, Beta and Gamma: one field each is unique, so every filter isolates one.

    Added in reverse alphabetical order on purpose. The board sorts companies by name, and
    a fixture that adds them in the order they should come back cannot tell a sort from an
    accident of insertion order.
    """
    ha = member_anna["headers"]
    return [
        _create_company(
            client,
            ha,
            name="Gamma Games",
            slug="gamma",
            industry="gaming",
            hq_city="Berlin",
            short_description="Joysticks",
            is_cdtm_startup=False,
        ),
        _create_company(
            client,
            ha,
            name="Beta Bank",
            slug="beta",
            industry="fintech",
            hq_city="Frankfurt",
            short_description="Ledgers all the way down",
            is_cdtm_startup=False,
        ),
        _create_company(
            client,
            ha,
            name="Alpha Bio",
            slug="alpha",
            industry="biotech",
            hq_city="Munich",
            short_description="Pipettes and patience",
            is_cdtm_startup=True,
        ),
    ]


def _listed(client: TestClient, **params) -> list[str]:
    r = client.get("/api/v1/companies/", params=params)
    assert r.status_code == 200, r.text
    return [c["slug"] for c in r.json()["items"]]


def test_the_company_list_filters_on_every_field_it_advertises(
    client: TestClient, three_companies: list[dict]
) -> None:
    """Each query parameter narrows the board, and no parameter narrows it by accident."""
    assert _listed(client) == ["alpha", "beta", "gamma"]

    assert _listed(client, industry="fintech") == ["beta"]
    assert _listed(client, industry="agritech") == []

    assert _listed(client, is_cdtm_startup=True) == ["alpha"]
    assert _listed(client, is_cdtm_startup=False) == ["beta", "gamma"]

    # City is a contains-match, and it does not care about case.
    assert _listed(client, hq_city="unich") == ["alpha"]
    assert _listed(client, hq_city="MUNICH") == ["alpha"]
    assert _listed(client, hq_city="Munchen") == []

    # The free-text search reaches the name, the short description and the industry.
    assert _listed(client, q="Gamma") == ["gamma"]
    assert _listed(client, q="joystick") == ["gamma"]
    assert _listed(client, q="pipettes") == ["alpha"]
    assert _listed(client, q="fintech") == ["beta"]
    # Surrounding whitespace is trimmed rather than searched for.
    assert _listed(client, q="  fintech  ") == ["beta"]
    assert _listed(client, q="nothing here") == []

    # Two filters narrow, they do not replace each other.
    assert _listed(client, industry="fintech", hq_city="Berlin") == []


def test_the_company_list_is_ordered_by_name_and_pages(
    client: TestClient, three_companies: list[dict]
) -> None:
    r = client.get("/api/v1/companies/", params={"limit": 2})
    assert r.status_code == 200, r.text
    assert [c["slug"] for c in r.json()["items"]] == ["alpha", "beta"]
    # The total counts the whole result set, not the page.
    assert r.json()["total"] == 3

    r = client.get("/api/v1/companies/", params={"skip": 2, "limit": 2})
    assert [c["slug"] for c in r.json()["items"]] == ["gamma"]
    assert r.json()["total"] == 3

    r = client.get("/api/v1/companies/", params={"skip": 3, "limit": 2})
    assert r.json()["items"] == []
    assert r.json()["total"] == 3

    # A filter narrows the total too, not only the page.
    r = client.get("/api/v1/companies/", params={"industry": "gaming", "limit": 2})
    assert r.json()["total"] == 1


# ---- who the board is rendered for -----------------------------------------------------


def test_the_poster_sees_their_confidential_salary_in_the_list_and_by_slug(
    client: TestClient, member_anna: dict, member_ben: dict, admin_headers: dict
) -> None:
    """Redaction runs against the caller on every read, not only on get-by-id.

    A confidential salary is hidden from the board but not from the person who typed it in,
    and the list and the slug lookup are the same board under different keys.
    """
    ha, hb = member_anna["headers"], member_ben["headers"]
    company = _create_company(client, ha, slug="pay-gaps")
    job = client.post(
        "/api/v1/jobs/",
        json=_job_body(
            company["id"],
            slug="quiet-pay",
            status="published",
            salary_min=60000,
            salary_max=80000,
            salary_currency="EUR",
            compensation_disclosure="confidential",
        ),
        headers=ha,
    ).json()
    assert job["id"]

    # In the list: the poster and an admin see the numbers, nobody else does.
    mine = client.get("/api/v1/jobs/", headers=ha).json()["items"][0]
    assert mine["salary_min"] == "60000"
    assert mine["salary_max"] == "80000"
    assert mine["salary_currency"] == "EUR"
    assert client.get("/api/v1/jobs/", headers=admin_headers).json()["items"][0]["salary_min"] == (
        "60000"
    )
    assert client.get("/api/v1/jobs/", headers=hb).json()["items"][0]["salary_min"] is None
    assert client.get("/api/v1/jobs/").json()["items"][0]["salary_min"] is None

    # By slug: same answer, same reader.
    by_slug = client.get("/api/v1/jobs/slug/quiet-pay", headers=ha).json()
    assert by_slug["salary_min"] == "60000"
    assert by_slug["salary_max"] == "80000"
    assert (
        client.get("/api/v1/jobs/slug/quiet-pay", headers=admin_headers).json()["salary_max"]
        == "80000"
    )
    assert client.get("/api/v1/jobs/slug/quiet-pay", headers=hb).json()["salary_min"] is None
    assert client.get("/api/v1/jobs/slug/quiet-pay").json()["salary_min"] is None
    # The disclosure itself travels with the posting either way.
    assert client.get("/api/v1/jobs/slug/quiet-pay").json()["compensation_disclosure"] == (
        "confidential"
    )


def test_the_job_list_pages_the_board(client: TestClient, member_anna: dict) -> None:
    """``skip`` and ``limit`` bound the page; ``total`` keeps counting the whole board."""
    ha = member_anna["headers"]
    company = _create_company(client, ha, slug="paged")
    for n in range(3):
        r = client.post(
            "/api/v1/jobs/",
            json=_job_body(company["id"], title=f"Role {n}", slug=f"role-{n}", status="published"),
            headers=ha,
        )
        assert r.status_code == 201, r.text

    first = client.get("/api/v1/jobs/", params={"limit": 1}).json()
    assert len(first["items"]) == 1
    assert first["total"] == 3

    second = client.get("/api/v1/jobs/", params={"skip": 2, "limit": 10}).json()
    assert len(second["items"]) == 1
    assert second["total"] == 3

    past_the_end = client.get("/api/v1/jobs/", params={"skip": 3, "limit": 10}).json()
    assert past_the_end["items"] == []
    assert past_the_end["total"] == 3


# ---- the shared session survives a failed statement -------------------------------------


@pytest.fixture
async def sessions():
    """A session factory on its own engine, so each scenario gets an untouched session.

    ``NullPool`` because this engine lives for one test on one event loop; it must not hand
    a connection back to anything the app's own engine is using.
    """
    engine = create_async_engine(get_database_settings().async_url, poolclass=NullPool)
    try:
        yield async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    finally:
        await engine.dispose()


async def _fail_a_statement(session: AsyncSession) -> None:
    """Leave the session exactly as an earlier failed statement in the request left it."""
    with contextlib.suppress(SQLAlchemyError):
        await session.execute(text("select cast('not-a-uuid' as uuid)"))


async def test_a_failed_company_statement_does_not_poison_the_rest_of_the_request(
    client: TestClient, member_anna: dict, sessions
) -> None:
    """One failed statement must not turn every later one in the request into a 503.

    The session is shared by every repository serving a request, and Postgres refuses every
    statement after a failed one until the transaction is rolled back. The repository rolls
    it back where the failure happened, which is why a caller that catches the error can
    carry on.
    """
    company = _create_company(client, member_anna["headers"], slug="poison")
    company_id = uuid.UUID(company["id"])

    async def survives(op):
        """Run ``op`` on a session a failed statement has already broken, then again."""
        async with sessions() as s:
            repo = SqlCompanyRepository(s)
            await _fail_a_statement(s)
            with pytest.raises(AppError):
                await op(repo)
            # The same session answers the next statement, because the failure rolled back.
            return await op(repo)

    # A real conflict: the duplicate slug fails inside create, and the session survives it.
    async with sessions() as s:
        repo = SqlCompanyRepository(s)
        with pytest.raises(ConflictError):
            await repo.create(CompanyCreate(name="Other", slug="poison"), created_by_member_id=None)
        assert (await repo.get_by_slug("poison")).id == company_id

    # Every read and every write on the record cleans up after itself the same way.
    assert (await survives(lambda r: r.get(company_id))).slug == "poison"
    assert (await survives(lambda r: r.get_by_slug("poison"))).id == company_id
    listed = await survives(lambda r: r.list(skip=0, limit=10, filters=CompanyFilters()))
    assert listed.total == 1
    updated = await survives(lambda r: r.update(company_id, CompanyUpdate(legal_name="ACME AG")))
    assert updated.legal_name == "ACME AG"
    assert await survives(lambda r: r.delete(company_id)) is True

    async with sessions() as s:
        assert await SqlCompanyRepository(s).get(company_id) is None
