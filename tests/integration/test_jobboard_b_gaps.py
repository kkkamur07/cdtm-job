"""What the board can be narrowed to, who may correct a seeker profile, and Ask over jobs.

Three gaps this covers, all of them end to end against the real app and a real Postgres:

* the job list advertises a dozen filters and only a handful of them were ever asked for
  with a posting that should come back, so a filter that quietly matched nothing (or
  everything) looked exactly like a filter that worked;
* a seeker profile could be refused to a stranger but had never once been corrected or
  withdrawn by the member who owns it, or by an admin, so neither the ownership check nor
  the repository's update and delete ran in any test;
* the jobs Ask had none of the guarantees the plain board has tests for: no draft may
  surface through a question, a confidential salary is hidden from an answer the same way
  it is hidden from the list, and one member's questions do not spend another's allowance.
"""

from __future__ import annotations

import contextlib
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from backend.core.exceptions import AppError
from backend.core.llm.rate_limit import ask_limiter
from backend.core.settings import get_database_settings, reset_settings_caches
from backend.jobboard.application.commands import SeekerCreate, SeekerUpdate
from backend.jobboard.application.ports import JobFilters
from backend.jobboard.domain import (
    EmploymentType,
    ExperienceLevel,
    JobStatus,
    WorkArrangement,
)
from backend.jobboard.infrastructure.job_repository import SqlJobRepository
from backend.jobboard.infrastructure.seeker_repository import SqlSeekerRepository

pytestmark = pytest.mark.integration

JOBS = "/api/v1/jobs"
SEEKERS = "/api/v1/seekers"


@pytest.fixture(autouse=True)
def _fresh_buckets():
    # The in-process limiter is the fallback for the SQL meter and is process-wide; tests
    # must not inherit each other's spend.
    ask_limiter.reset()
    yield
    ask_limiter.reset()


@pytest.fixture
async def sessions():
    """A session factory on its own engine, so each scenario gets an untouched session."""
    engine = create_async_engine(get_database_settings().async_url, poolclass=NullPool)
    try:
        yield async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    finally:
        await engine.dispose()


def _company(client: TestClient, headers: dict, slug: str, **over) -> dict:
    payload = {"name": slug.title(), "slug": slug} | over
    r = client.post("/api/v1/companies/", json=payload, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def _job(client: TestClient, headers: dict, company_id: str, **over) -> dict:
    payload = {
        "company_id": company_id,
        "title": "Founding Engineer",
        "description": "Build things",
        "employment_type": "full_time",
        "work_arrangement": "remote",
        "experience_level": "mid",
        "status": "published",
    } | over
    r = client.post(f"{JOBS}/", json=payload, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


# ---- the board a question or a query parameter narrows -----------------------------------


@pytest.fixture
def board(client: TestClient, member_anna: dict) -> dict:
    """Four published postings across two employers, differing on every filterable field.

    One employer is a CDTM startup and one is not, so a filter on the employer has to reach
    the right one of the two rather than merely reach *an* employer.
    """
    ha = member_anna["headers"]
    nordwind = _company(client, ha, "nordwind", name="Nordwind Labs", is_cdtm_startup=True)
    suedbahn = _company(client, ha, "suedbahn", name="Suedbahn AG", is_cdtm_startup=False)
    jobs = {
        "alpha": _job(
            client,
            ha,
            nordwind["id"],
            slug="alpha",
            title="Alpha Wind",
            summary="wind turbines",
            description="cabling harnesses",
            location_display="Neuperlach Sued",
            city="Munich",
            country="Germany",
            employment_type="full_time",
            work_arrangement="remote",
            experience_level="senior",
            salary_min=90000,
            salary_max=120000,
            salary_currency="EUR",
            compensation_disclosure="public",
        ),
        "beta": _job(
            client,
            ha,
            suedbahn["id"],
            slug="beta",
            title="Beta Ledger",
            city="Berlin",
            country="Germany",
            employment_type="internship",
            work_arrangement="onsite",
            experience_level="intern",
            salary_min=20000,
            salary_max=30000,
            salary_currency="EUR",
            compensation_disclosure="public",
        ),
        "gamma": _job(
            client,
            ha,
            suedbahn["id"],
            slug="gamma",
            title="Gamma Joystick",
            location_display="Munich Office",
            country="Switzerland",
            employment_type="working_student",
            work_arrangement="hybrid",
            experience_level="entry",
        ),
        "delta": _job(
            client,
            ha,
            nordwind["id"],
            slug="delta",
            title="Delta Bridge",
            city="Zurich",
            country="Switzerland",
            employment_type="part_time",
            work_arrangement="remote",
            experience_level="mid",
            salary_min=50000,
            salary_currency="EUR",
            compensation_disclosure="public",
        ),
    }
    # Gamma was posted two months ago; the other three today.
    long_ago = (datetime.now(UTC) - timedelta(days=60)).isoformat()
    r = client.patch(f"{JOBS}/{jobs['gamma']['id']}", json={"published_at": long_ago}, headers=ha)
    assert r.status_code == 200, r.text
    return {"companies": {"nordwind": nordwind, "suedbahn": suedbahn}, "jobs": jobs}


def _slugs(client: TestClient, **params) -> list[str]:
    r = client.get(f"{JOBS}/", params=params)
    assert r.status_code == 200, r.text
    return sorted(j["slug"] for j in r.json()["items"])


def test_the_job_list_filters_on_the_query_parameters_it_advertises(
    client: TestClient, board: dict, member_anna: dict, member_ben: dict
) -> None:
    """Each parameter returns the postings that match it, not merely fewer postings.

    Every existing test asked a filter for something no posting had and checked the board
    came back empty, which a filter that matches nothing at all passes just as well.
    """
    jobs, companies = board["jobs"], board["companies"]
    assert _slugs(client) == ["alpha", "beta", "delta", "gamma"]

    assert _slugs(client, company_id=companies["nordwind"]["id"]) == ["alpha", "delta"]
    assert _slugs(client, company_id=companies["suedbahn"]["id"]) == ["beta", "gamma"]
    assert _slugs(client, company_id=str(uuid.uuid4())) == []

    assert _slugs(client, employment_type="internship") == ["beta"]
    assert _slugs(client, employment_type="full_time") == ["alpha"]

    assert _slugs(client, work_arrangement="remote") == ["alpha", "delta"]
    assert _slugs(client, work_arrangement="hybrid") == ["gamma"]

    assert _slugs(client, posted_by_member_id=str(member_anna["id"])) == [
        "alpha",
        "beta",
        "delta",
        "gamma",
    ]
    assert _slugs(client, posted_by_member_id=str(member_ben["id"])) == []

    # Two filters narrow, they do not replace each other.
    assert _slugs(client, company_id=companies["nordwind"]["id"], work_arrangement="remote") == [
        "alpha",
        "delta",
    ]
    assert _slugs(client, company_id=companies["suedbahn"]["id"], work_arrangement="remote") == []
    assert jobs["alpha"]["published_at"] is not None


def test_the_free_text_search_reaches_every_part_of_a_posting_it_promises(
    client: TestClient, board: dict
) -> None:
    """``q`` searches the title, the summary, the description and the displayed location."""
    assert _slugs(client, q="Alpha Wind") == ["alpha"]
    assert _slugs(client, q="wind turbines") == ["alpha"]
    assert _slugs(client, q="cabling") == ["alpha"]
    assert _slugs(client, q="Neuperlach") == ["alpha"]
    assert _slugs(client, q="  Neuperlach  ") == ["alpha"]
    assert _slugs(client, q="nothing here") == []


def test_a_search_term_is_read_as_text_and_not_as_a_pattern(
    client: TestClient, member_anna: dict
) -> None:
    """``%``, ``_`` and ``\\`` are characters a member can type, not wildcards they aimed.

    Left unescaped they turn one search into a much wider one, which on a board is the
    difference between "the posting I meant" and "everything that vaguely rhymes".
    """
    ha = member_anna["headers"]
    company = _company(client, ha, "patterns")
    for slug, title in [
        ("literal-percent", "Beta 50% Ledger"),
        ("wider-percent", "Beta 500 Ledger"),
        ("literal-underscore", "Gamma_Joystick"),
        ("wider-underscore", "GammaXJoystick"),
        ("backslash", "C:\\Data Engineer"),
    ]:
        _job(client, ha, company["id"], slug=slug, title=title)

    assert _slugs(client, q="50%") == ["literal-percent"]
    assert _slugs(client, q="gamma_joystick") == ["literal-underscore"]
    assert _slugs(client, q="c:\\d") == ["backslash"]


# ---- the same board, straight at the repository ------------------------------------------


async def _filtered(sessions, **kw) -> list[str]:
    async with sessions() as s:
        result = await SqlJobRepository(s).list(
            skip=0, limit=50, filters=JobFilters(status=JobStatus.PUBLISHED, **kw)
        )
    return sorted(j.slug for j in result.items)


async def test_every_filter_a_translated_question_can_set_narrows_the_board(
    client: TestClient, board: dict, sessions
) -> None:
    """The plural and free-text filters only a question can fill are what Ask searches with.

    They have no query parameter on the list route, so this asks the repository for them
    directly: each one has to return the postings that match it and leave the rest out.
    """
    assert await _filtered(sessions) == ["alpha", "beta", "delta", "gamma"]

    assert await _filtered(sessions, employment_types=(EmploymentType.WORKING_STUDENT,)) == [
        "gamma"
    ]
    assert await _filtered(
        sessions, employment_types=(EmploymentType.PART_TIME, EmploymentType.INTERNSHIP)
    ) == ["beta", "delta"]

    assert await _filtered(sessions, work_arrangements=(WorkArrangement.REMOTE,)) == [
        "alpha",
        "delta",
    ]
    assert await _filtered(
        sessions, work_arrangements=(WorkArrangement.HYBRID, WorkArrangement.ONSITE)
    ) == ["beta", "gamma"]

    assert await _filtered(sessions, experience_levels=(ExperienceLevel.SENIOR,)) == ["alpha"]
    assert await _filtered(
        sessions, experience_levels=(ExperienceLevel.INTERN, ExperienceLevel.ENTRY)
    ) == ["beta", "gamma"]

    # remote_only is stronger than "remote is acceptable": the hybrid posting stays out.
    assert await _filtered(sessions, remote_only=True) == ["alpha", "delta"]

    # A city matches the city column or the location the posting displays.
    assert await _filtered(sessions, city="Munich") == ["alpha", "gamma"]
    assert await _filtered(sessions, city="munich") == ["alpha", "gamma"]
    assert await _filtered(sessions, city="Hamburg") == []

    assert await _filtered(sessions, country="Germany") == ["alpha", "beta"]
    assert await _filtered(sessions, country="switzerland") == ["delta", "gamma"]

    # The employer is matched by name, and by whether it came out of CDTM.
    assert await _filtered(sessions, company="Nordwind") == ["alpha", "delta"]
    assert await _filtered(sessions, company="nordwind labs") == ["alpha", "delta"]
    assert await _filtered(sessions, is_cdtm_startup=True) == ["alpha", "delta"]
    assert await _filtered(sessions, is_cdtm_startup=False) == ["beta", "gamma"]
    assert await _filtered(sessions, company="Suedbahn", is_cdtm_startup=True) == []

    # Two filters narrow together.
    assert await _filtered(sessions, country="Germany", remote_only=True) == ["alpha"]


async def test_a_salary_floor_is_cleared_by_a_posting_that_reaches_it(
    client: TestClient, board: dict, sessions
) -> None:
    """A range clears the floor when either end does: a 60-80k posting is a 70k job.

    The floor is inclusive at both ends, and a posting with no salary at all never clears
    one, because "unpaid" is not what "does not say" means.
    """
    assert await _filtered(sessions, salary_min=100000) == ["alpha"]
    assert await _filtered(sessions, salary_min=90000) == ["alpha"]
    # Delta advertises a floor and no ceiling; the floor itself is enough.
    assert await _filtered(sessions, salary_min=50000) == ["alpha", "delta"]
    # Beta's ceiling is exactly 30000, and exactly is enough.
    assert await _filtered(sessions, salary_min=30000) == ["alpha", "beta", "delta"]
    # Gamma says nothing about pay and so never clears a floor.
    assert await _filtered(sessions, salary_min=1) == ["alpha", "beta", "delta"]


async def test_a_recency_window_counts_back_from_now(
    client: TestClient, board: dict, sessions
) -> None:
    """ "posted this week" is the last seven days, not the next seven."""
    assert await _filtered(sessions, posted_within_days=7) == ["alpha", "beta", "delta"]
    assert await _filtered(sessions, posted_within_days=90) == ["alpha", "beta", "delta", "gamma"]


async def test_the_board_is_newest_first_unless_the_question_asked_for_the_money(
    client: TestClient, board: dict, sessions
) -> None:
    """ "salary" sorts on the advertised floor, and a posting that says nothing goes last."""
    async with sessions() as s:
        repo = SqlJobRepository(s)
        by_salary = await repo.list(
            skip=0, limit=50, filters=JobFilters(status=JobStatus.PUBLISHED, sort="salary")
        )
        newest = await repo.list(skip=0, limit=50, filters=JobFilters(status=JobStatus.PUBLISHED))

    assert [j.slug for j in by_salary.items] == ["alpha", "delta", "beta", "gamma"]
    # The default is the other order, so the sort is doing something rather than nothing.
    assert [j.slug for j in newest.items] == ["delta", "gamma", "beta", "alpha"]


async def test_the_repository_pages_the_board_and_still_counts_all_of_it(
    client: TestClient, board: dict, sessions
) -> None:
    async with sessions() as s:
        repo = SqlJobRepository(s)
        filters = JobFilters(status=JobStatus.PUBLISHED)
        first = await repo.list(skip=0, limit=2, filters=filters)
        second = await repo.list(skip=2, limit=2, filters=filters)
        past_the_end = await repo.list(skip=4, limit=2, filters=filters)

    assert [j.slug for j in first.items] == ["delta", "gamma"]
    assert [j.slug for j in second.items] == ["beta", "alpha"]
    assert past_the_end.items == []
    # The total counts the whole result set, not the page.
    assert (first.total, second.total, past_the_end.total) == (4, 4, 4)


# ---- publishing stamps the date, once ----------------------------------------------------


def test_a_posting_published_on_the_way_in_is_dated_on_the_way_in(
    client: TestClient, member_anna: dict
) -> None:
    """Published without ever being a draft still has to say when it went up."""
    ha = member_anna["headers"]
    company = _company(client, ha, "stamped")
    job = _job(client, ha, company["id"], slug="born-published")
    assert job["status"] == "published"
    assert job["published_at"] is not None
    assert client.get(f"{JOBS}/slug/born-published").json()["published_at"] is not None


def test_publishing_a_draft_with_an_empty_date_still_dates_it(
    client: TestClient, member_anna: dict
) -> None:
    """An explicit null is "I did not say", not "clear it": the board would lose the date."""
    ha = member_anna["headers"]
    company = _company(client, ha, "explicit-null")
    draft = _job(client, ha, company["id"], slug="quiet", status="draft")
    assert draft["published_at"] is None

    r = client.patch(
        f"{JOBS}/{draft['id']}", json={"status": "published", "published_at": None}, headers=ha
    )
    assert r.status_code == 200, r.text
    assert r.json()["published_at"] is not None


# ---- a seeker profile, corrected and withdrawn by the people who may ----------------------


def _seeker(client: TestClient, headers: dict, **over) -> dict:
    payload = {"full_name": "Anna Test", "headline": "Backend engineer"} | over
    r = client.post(f"{SEEKERS}/", json=payload, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def test_a_seeker_corrects_their_own_profile_and_an_admin_may_correct_any(
    client: TestClient, member_anna: dict, member_ben: dict, admin_headers: dict
) -> None:
    """The refusal for a stranger was tested; the permission for the owner never was.

    A regression that denied the owner, or one that accepted the edit and stored nothing,
    passed the whole suite: no test had ever changed a seeker profile at all.
    """
    ha, hb = member_anna["headers"], member_ben["headers"]
    seeker = _seeker(client, ha, email="anna.private@example.com", phone="+49 151 0000000")

    r = client.patch(
        f"{SEEKERS}/{seeker['id']}",
        json={"headline": "Platform engineer", "years_of_experience": 6},
        headers=ha,
    )
    assert r.status_code == 200, r.text
    assert r.json()["headline"] == "Platform engineer"
    assert r.json()["years_of_experience"] == 6
    # Stored, not merely echoed, and the fields the patch did not name are untouched.
    stored = client.get(f"{SEEKERS}/{seeker['id']}", headers=ha).json()
    assert stored["headline"] == "Platform engineer"
    assert stored["years_of_experience"] == 6
    assert stored["email"] == "anna.private@example.com"
    assert stored["phone"] == "+49 151 0000000"
    assert stored["full_name"] == "Anna Test"
    assert stored["updated_at"] >= seeker["updated_at"]

    # A patch that names nothing is still the profile, not a 404 and not a wipe.
    r = client.patch(f"{SEEKERS}/{seeker['id']}", json={}, headers=ha)
    assert r.status_code == 200, r.text
    assert r.json()["headline"] == "Platform engineer"

    # An admin may correct anybody's, a stranger still may not.
    r = client.patch(
        f"{SEEKERS}/{seeker['id']}", json={"headline": "Corrected"}, headers=admin_headers
    )
    assert r.status_code == 200 and r.json()["headline"] == "Corrected"
    assert (
        client.patch(f"{SEEKERS}/{seeker['id']}", json={"headline": "Ben"}, headers=hb)
    ).status_code == 403

    # And a profile that is not there is a 404 whoever asks.
    assert (
        client.patch(f"{SEEKERS}/{uuid.uuid4()}", json={"headline": "Ghost"}, headers=ha)
    ).status_code == 404


def test_a_seeker_withdraws_their_own_profile_and_an_admin_may_withdraw_any(
    client: TestClient, member_anna: dict, member_ben: dict, admin_headers: dict
) -> None:
    ha, hb = member_anna["headers"], member_ben["headers"]
    mine = _seeker(client, ha, full_name="Anna Test")
    theirs = _seeker(client, hb, full_name="Ben Test")

    assert client.delete(f"{SEEKERS}/{mine['id']}", headers=ha).status_code == 204
    # Gone, and only that one: the other member's profile is still on the board.
    assert client.get(f"{SEEKERS}/{mine['id']}", headers=ha).status_code == 404
    assert client.get(f"{SEEKERS}/{theirs['id']}", headers=hb).status_code == 200
    assert client.get(f"{SEEKERS}/", headers=ha).json()["total"] == 1

    # Withdrawing it twice is a 404, not a second success.
    assert client.delete(f"{SEEKERS}/{mine['id']}", headers=ha).status_code == 404
    assert client.delete(f"{SEEKERS}/{uuid.uuid4()}", headers=ha).status_code == 404

    # An admin may withdraw anybody's.
    assert client.delete(f"{SEEKERS}/{theirs['id']}", headers=admin_headers).status_code == 204
    assert client.get(f"{SEEKERS}/", headers=ha).json()["total"] == 0


def test_the_seeker_board_is_newest_first_and_pages(client: TestClient, member_anna: dict) -> None:
    ha = member_anna["headers"]
    for name in ("First", "Second", "Third"):
        _seeker(client, ha, full_name=name)

    r = client.get(f"{SEEKERS}/", params={"limit": 2}, headers=ha)
    assert r.status_code == 200, r.text
    assert [s["full_name"] for s in r.json()["items"]] == ["Third", "Second"]
    assert r.json()["total"] == 3

    r = client.get(f"{SEEKERS}/", params={"skip": 2, "limit": 2}, headers=ha)
    assert [s["full_name"] for s in r.json()["items"]] == ["First"]
    assert r.json()["total"] == 3

    r = client.get(f"{SEEKERS}/", params={"skip": 3, "limit": 2}, headers=ha)
    assert r.json()["items"] == []
    assert r.json()["total"] == 3


def test_the_seeker_list_is_redacted_for_the_reader_it_is_rendered_for(
    client: TestClient, member_anna: dict, member_ben: dict, admin_headers: dict
) -> None:
    """Redaction runs per row against the caller, on the list as much as on the detail."""
    ha, hb = member_anna["headers"], member_ben["headers"]
    _seeker(client, ha, full_name="Anna Test", email="anna.private@example.com")
    _seeker(client, hb, full_name="Ben Test", email="ben.private@example.com")

    def emails(headers: dict) -> dict[str, str | None]:
        body = client.get(f"{SEEKERS}/", headers=headers).json()
        return {s["full_name"]: s["email"] for s in body["items"]}

    assert emails(ha) == {"Anna Test": "anna.private@example.com", "Ben Test": None}
    assert emails(hb) == {"Anna Test": None, "Ben Test": "ben.private@example.com"}
    assert emails(admin_headers) == {
        "Anna Test": "anna.private@example.com",
        "Ben Test": "ben.private@example.com",
    }


# ---- Ask over the job board --------------------------------------------------------------


def _ask(client: TestClient, headers: dict, question: str, **body):
    return client.post(f"{JOBS}/ask/", json={"question": question, **body}, headers=headers)


def test_a_question_never_surfaces_a_draft(
    client: TestClient, member_anna: dict, member_ben: dict
) -> None:
    """A draft is a job nobody has decided to advertise yet; asking is not a way in.

    The plain board has this test; the Ask endpoint reads the same postings and had none.
    """
    ha, hb = member_anna["headers"], member_ben["headers"]
    company = _company(client, ha, "drafts-and-asks")
    published = _job(
        client, ha, company["id"], slug="on-the-board", title="Remote Product", city="Munich"
    )
    _job(
        client,
        ha,
        company["id"],
        slug="not-yet",
        title="Remote Product",
        city="Munich",
        status="draft",
    )

    for headers in (ha, hb):
        body = _ask(client, headers, "remote product roles in Munich").json()
        assert body["total"] == 1
        assert [j["slug"] for j in body["jobs"]] == ["on-the-board"]
        assert body["jobs"][0]["id"] == published["id"]


def test_an_answer_hides_a_confidential_salary_the_way_the_board_does(
    client: TestClient, member_anna: dict, member_ben: dict, admin_headers: dict
) -> None:
    """An answer is a way of listing the board, so it redacts what the board redacts."""
    ha, hb = member_anna["headers"], member_ben["headers"]
    company = _company(client, ha, "quiet-pay-ask")
    _job(
        client,
        ha,
        company["id"],
        slug="quiet",
        title="Remote Product",
        city="Munich",
        salary_min=60000,
        salary_max=80000,
        salary_currency="EUR",
        compensation_disclosure="confidential",
    )
    question = "remote product roles in Munich"

    stranger = _ask(client, hb, question).json()["jobs"][0]
    assert stranger["salary_min"] is None
    assert stranger["salary_max"] is None
    assert stranger["salary_currency"] is None
    # The disclosure itself is not a secret; the numbers behind it are.
    assert stranger["compensation_disclosure"] == "confidential"

    assert _ask(client, ha, question).json()["jobs"][0]["salary_min"] == "60000"
    assert _ask(client, admin_headers, question).json()["jobs"][0]["salary_max"] == "80000"


def test_a_question_reads_the_words_that_narrow_the_board(
    client: TestClient, board: dict, member_anna: dict
) -> None:
    """The filters a question is read as are the filters the answer was searched with."""
    ha = member_anna["headers"]
    body = _ask(client, ha, "senior remote jobs in Germany paying over 80k").json()
    interpretation = body["interpretation"]
    assert interpretation["filters"]["experience_level"] == ["senior"]
    assert interpretation["filters"]["remote_only"] is True
    assert interpretation["filters"]["country"] == "Germany"
    assert interpretation["filters"]["salary_min"] == "80000"
    assert [j["slug"] for j in body["jobs"]] == ["alpha"]
    assert body["total"] == 1

    at_the_employer = _ask(client, ha, "working student jobs at Suedbahn AG").json()
    assert at_the_employer["interpretation"]["filters"]["employment_type"] == ["working_student"]
    assert [j["slug"] for j in at_the_employer["jobs"]] == ["gamma"]

    cdtm = _ask(client, ha, "jobs at cdtm startups").json()
    assert sorted(j["slug"] for j in cdtm["jobs"]) == ["alpha", "delta"]


def test_an_answer_is_a_page_of_the_board_the_caller_asked_for(
    client: TestClient, board: dict, member_anna: dict
) -> None:
    """``limit`` bounds the answer, ``skip`` moves it, and ``total`` counts the whole match."""
    ha = member_anna["headers"]
    first = _ask(client, ha, "jobs in Germany", limit=1).json()
    assert len(first["jobs"]) == 1
    assert first["total"] == 2

    second = _ask(client, ha, "jobs in Germany", skip=1, limit=1).json()
    assert len(second["jobs"]) == 1
    assert second["jobs"][0]["slug"] != first["jobs"][0]["slug"]
    assert second["total"] == 2

    past_the_end = _ask(client, ha, "jobs in Germany", skip=2, limit=5).json()
    assert past_the_end["jobs"] == []
    assert past_the_end["total"] == 2


def test_explaining_a_question_reads_it_without_searching_the_board(
    client: TestClient, board: dict, member_anna: dict
) -> None:
    r = client.post(
        f"{JOBS}/ask/explain",
        json={"question": "senior remote jobs in Germany"},
        headers=member_anna["headers"],
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["filters"]["experience_level"] == ["senior"]
    assert body["filters"]["country"] == "Germany"
    assert body["source"] == "rules"
    assert body["summary"]
    assert "jobs" not in body


def test_a_question_that_is_not_a_question_is_refused_before_it_costs_anything(
    client: TestClient, member_anna: dict
) -> None:
    assert _ask(client, member_anna["headers"], "a").status_code == 422
    assert _ask(client, member_anna["headers"], "x" * 301).status_code == 422


def test_a_summary_language_the_keyword_rules_cannot_write_is_reported_for_jobs(
    client: TestClient, member_anna: dict
) -> None:
    """No provider here, so the summary stays English and says so rather than pretending."""
    r = _ask(client, member_anna["headers"], "remote jobs", language="de-DE")
    assert r.status_code == 200, r.text
    assert "summary language de-DE" in r.json()["interpretation"]["unresolved"]
    assert r.json()["interpretation"]["filters"]["remote_only"] is True


def test_one_members_questions_do_not_spend_another_members_allowance(
    client: TestClient, member_anna: dict, member_ben: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The quota is per member, and the jobs board counts into the same bucket as the rest."""
    monkeypatch.setenv("LLM_MAX_QUESTIONS_PER_MINUTE", "1")
    reset_settings_caches()
    ha, hb = member_anna["headers"], member_ben["headers"]

    assert _ask(client, ha, "remote jobs").status_code == 200
    over = _ask(client, ha, "remote jobs")
    assert over.status_code == 429
    assert over.json()["error"]["code"] == "rate_limited"
    # A preview shares the bucket: asking on every keystroke is not free either.
    assert (
        client.post(f"{JOBS}/ask/explain", json={"question": "remote jobs"}, headers=ha).status_code
        == 429
    )
    # Another member has their own allowance.
    assert _ask(client, hb, "remote jobs").status_code == 200


def test_a_members_allowance_is_the_same_one_whichever_board_they_ask(
    client: TestClient, member_anna: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """It is the same call to the same provider, so it is the same allowance."""
    monkeypatch.setenv("LLM_MAX_QUESTIONS_PER_MINUTE", "1")
    reset_settings_caches()
    ha = member_anna["headers"]

    assert (
        client.post(
            "/api/v1/members/ask/", json={"question": "founders in Berlin"}, headers=ha
        ).status_code
        == 200
    )
    assert _ask(client, ha, "remote jobs").status_code == 429


def test_asking_needs_a_login_even_though_reading_the_board_does_not(
    client: TestClient,
) -> None:
    assert client.get(f"{JOBS}/").status_code == 200
    assert client.post(f"{JOBS}/ask/", json={"question": "remote jobs"}).status_code == 401
    assert client.post(f"{JOBS}/ask/explain", json={"question": "remote jobs"}).status_code == 401


# ---- the shared session survives a failed statement --------------------------------------


async def _fail_a_statement(session: AsyncSession) -> None:
    """Leave the session exactly as an earlier failed statement in the request left it."""
    with contextlib.suppress(SQLAlchemyError):
        await session.execute(text("select cast('not-a-uuid' as uuid)"))


async def test_a_failed_job_statement_does_not_poison_the_rest_of_the_request(
    client: TestClient, member_anna: dict, board: dict, sessions
) -> None:
    """One failed statement must not turn every later one in the request into a 503.

    The session is shared by every repository serving a request, and Postgres refuses every
    statement after a failed one until the transaction is rolled back. The repository rolls
    it back where the failure happened, which is why a caller that catches the error carries
    on.
    """
    job_id = uuid.UUID(board["jobs"]["alpha"]["id"])

    async def survives(op):
        async with sessions() as s:
            repo = SqlJobRepository(s)
            await _fail_a_statement(s)
            with pytest.raises(AppError):
                await op(repo)
            # The same session answers the next statement, because the failure rolled back.
            return await op(repo)

    assert (await survives(lambda r: r.get(job_id))).slug == "alpha"
    assert (await survives(lambda r: r.get_by_slug("alpha"))).id == job_id
    listed = await survives(
        lambda r: r.list(skip=0, limit=10, filters=JobFilters(status=JobStatus.PUBLISHED))
    )
    assert listed.total == 4
    assert await survives(lambda r: r.delete(job_id)) is True

    async with sessions() as s:
        assert await SqlJobRepository(s).get(job_id) is None


async def test_a_failed_seeker_statement_does_not_poison_the_rest_of_the_request(
    client: TestClient, member_anna: dict, sessions
) -> None:
    member_id = member_anna["id"]
    async with sessions() as s:
        created = await SqlSeekerRepository(s).create(
            SeekerCreate(full_name="Anna Test", headline="Backend engineer"),
            member_id=member_id,
        )

    async def survives(op):
        async with sessions() as s:
            repo = SqlSeekerRepository(s)
            await _fail_a_statement(s)
            with pytest.raises(AppError):
                await op(repo)
            return await op(repo)

    assert (await survives(lambda r: r.get(created.id))).full_name == "Anna Test"
    listed = await survives(lambda r: r.list(skip=0, limit=10))
    assert listed.total == 1
    updated = await survives(lambda r: r.update(created.id, SeekerUpdate(headline="Platform")))
    assert updated.headline == "Platform"
    assert await survives(lambda r: r.delete(created.id)) is True

    async with sessions() as s:
        assert await SqlSeekerRepository(s).get(created.id) is None
