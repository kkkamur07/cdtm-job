"""The three list DTOs, and what they are allowed to leave out.

``JobSummaryPublic``, ``HousingListingSummaryPublic`` and ``EventSummaryPublic`` are the
row shapes the boards return. Each one restates its aggregate's fields minus the long
text, because pydantic has no way to take a field back off a parent, and a restatement
drifts unless something holds the two sides together. That is what these tests are: a
field added to ``Job``, ``HousingListing`` or ``Event`` fails here until somebody decides
whether a list row should carry it.

They also pin the values: a summary built from a real aggregate must say exactly what the
aggregate says about every field it kept, salary normalisation included.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from backend.events.api.schemas import EventPublic, EventSummaryPublic
from backend.events.domain import Event
from backend.housing.api.schemas import HousingListingPublic, HousingListingSummaryPublic
from backend.housing.domain import HousingListing
from backend.jobboard.api.schemas import JobPublic, JobSummaryPublic
from backend.jobboard.domain import Job

#: What a list row has no use for. The description is the expensive one on all three
#: boards (``MAX_RICH_TEXT`` is 20,000 characters); on jobs the three keyword lists ride
#: along with it.
JOB_OMITS = {"description", "must_have_skills", "nice_to_have_skills", "languages"}
HOUSING_OMITS = {"description"}
EVENT_OMITS = {"description"}


def _job() -> Job:
    return Job(
        id=uuid4(),
        company_id=uuid4(),
        posted_by_member_id=uuid4(),
        slug="backend-engineer",
        title="Backend Engineer",
        summary="A short line the row may draw.",
        description="A very long posting. " * 500,
        employment_type="full_time",
        work_arrangement="hybrid",
        location_display="Munich, Germany",
        city="Munich",
        region="Bavaria",
        country="Germany",
        remote_eligibility_note="Two days a week in the office.",
        salary_min=Decimal("60000.00"),
        salary_max=Decimal("75000.50"),
        salary_currency="EUR",
        salary_period="yearly",
        compensation_disclosure="public",
        experience_level="mid",
        education_level="Bachelor",
        must_have_skills=["Python", "Postgres"],
        nice_to_have_skills=["SQLAlchemy"],
        languages=["en", "de"],
        image_url="https://example.com/job.png",
        application_url="https://example.com/apply",
        application_email="jobs@example.com",
        valid_through=date(2027, 1, 1),
        status="published",
        visa_sponsorship=True,
        relocation_assistance=False,
        created_at=datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
        updated_at=datetime(2026, 2, 1, 9, 0, tzinfo=UTC),
        published_at=datetime(2026, 1, 2, 9, 0, tzinfo=UTC),
    )


def _listing() -> HousingListing:
    return HousingListing(
        id=uuid4(),
        member_id=uuid4(),
        kind="offer",
        title="Room in Schwabing",
        description="A very long description. " * 500,
        city="Munich",
        area="Schwabing",
        price_eur=850,
        rooms=Decimal("1.5"),
        furnished=True,
        available_from=date(2026, 10, 1),
        available_until=date(2027, 3, 31),
        photo_urls=["housing/one.webp", "housing/two.webp"],
        status="open",
        view_count=12,
        expires_at=datetime(2026, 12, 1, tzinfo=UTC),
        created_at=datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
        updated_at=datetime(2026, 2, 1, 9, 0, tzinfo=UTC),
    )


def _event() -> Event:
    return Event(
        id=uuid4(),
        title="Alumni dinner",
        description="A very long description. " * 500,
        kind="community",
        starts_at=datetime(2026, 5, 1, 18, 0, tzinfo=UTC),
        ends_at=datetime(2026, 5, 1, 22, 0, tzinfo=UTC),
        location="Munich",
        url="https://example.com/dinner",
        created_by_member_id=uuid4(),
        is_published=True,
        going_count=7,
        interested_count=3,
        my_rsvp="going",
        created_at=datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
        updated_at=datetime(2026, 2, 1, 9, 0, tzinfo=UTC),
    )


def _same_but_for(summary, full, omitted: set[str]) -> None:
    """The summary is the full body minus the omitted keys, value for value."""
    thin = json.loads(summary.model_dump_json())
    fat = json.loads(full.model_dump_json())
    assert set(thin) == set(fat) - omitted
    assert all(thin[key] == fat[key] for key in thin)


def test_a_job_summary_is_the_job_without_its_description_or_keyword_lists() -> None:
    assert set(JobSummaryPublic.model_fields) == set(Job.model_fields) - JOB_OMITS


def test_a_housing_summary_is_the_listing_without_its_description() -> None:
    assert (
        set(HousingListingSummaryPublic.model_fields)
        == set(HousingListing.model_fields) - HOUSING_OMITS
    )


def test_an_event_summary_is_the_event_without_its_description() -> None:
    assert set(EventSummaryPublic.model_fields) == set(Event.model_fields) - EVENT_OMITS


def test_a_job_summary_says_what_the_job_says_about_every_field_it_kept() -> None:
    job = _job()
    _same_but_for(JobSummaryPublic.model_validate(job), JobPublic.model_validate(job), JOB_OMITS)


def test_a_job_summary_normalises_salary_the_way_the_detail_route_does() -> None:
    """Both shapes are drawn by the same code in the browser, so 60000 must not become
    60000.00 on one of them and not the other."""
    job = _job()
    row = json.loads(JobSummaryPublic.model_validate(job).model_dump_json())
    assert row["salary_min"] == "60000"
    assert row["salary_max"] == "75000.5"


def test_a_housing_summary_says_what_the_listing_says_about_every_field_it_kept() -> None:
    listing = _listing()
    _same_but_for(
        HousingListingSummaryPublic.model_validate(listing),
        HousingListingPublic.model_validate(listing),
        HOUSING_OMITS,
    )


def test_an_event_summary_says_what_the_event_says_about_every_field_it_kept() -> None:
    event = _event()
    _same_but_for(
        EventSummaryPublic.model_validate(event), EventPublic.model_validate(event), EVENT_OMITS
    )
