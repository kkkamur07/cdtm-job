"""``JobService.list_jobs`` against a fake repository: the page it asks for, and for whom.

The routes always spell ``skip`` and ``limit`` out, so the service's own defaults and the
exact page it forwards are only visible from here.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from backend.core.actor import Actor
from backend.core.page import PageResult
from backend.jobboard.application.job_service import JobService
from backend.jobboard.application.ports import JobFilters
from backend.jobboard.domain import (
    CompensationDisclosure,
    EmploymentType,
    ExperienceLevel,
    Job,
    JobStatus,
    JobSummary,
    WorkArrangement,
)

POSTER_ID = uuid.uuid4()


def _job(**over) -> Job:
    now = datetime.now(UTC)
    fields = {
        "id": uuid.uuid4(),
        "company_id": uuid.uuid4(),
        "posted_by_member_id": POSTER_ID,
        "title": "Founding Engineer",
        "description": "Build things",
        "employment_type": EmploymentType.FULL_TIME,
        "work_arrangement": WorkArrangement.REMOTE,
        "experience_level": ExperienceLevel.MID,
        "status": JobStatus.PUBLISHED,
        "created_at": now,
        "updated_at": now,
    }
    fields.update(over)
    return Job(**fields)


class FakeJobRepository:
    """Records the page and filters it was asked for and hands back a fixed board."""

    def __init__(self, items: list[Job]) -> None:
        self._items = items
        self.calls: list[dict] = []

    async def list(self, *, skip: int, limit: int, filters: JobFilters) -> PageResult[JobSummary]:
        self.calls.append({"skip": skip, "limit": limit, "filters": filters})
        # The port hands out summaries, the way the SQL list does.
        return PageResult(
            items=[JobSummary.model_validate(j) for j in self._items], total=len(self._items)
        )


async def test_list_jobs_asks_for_the_first_page_of_fifty_by_default() -> None:
    """A caller that names no page gets the board from the top, capped.

    ``skip`` and ``limit`` are forwarded verbatim to the repository, so a default that
    starts at the second row, or a cap that is not the documented one, would silently
    change what every caller without an explicit page sees.
    """
    repo = FakeJobRepository([_job()])
    result = await JobService(repo).list_jobs()

    assert repo.calls[0]["skip"] == 0
    assert repo.calls[0]["limit"] == 50
    assert result.total == 1

    await JobService(repo).list_jobs(skip=10, limit=5)
    assert repo.calls[1]["skip"] == 10
    assert repo.calls[1]["limit"] == 5


async def test_list_jobs_redacts_a_confidential_salary_for_everyone_but_the_poster() -> None:
    """The list renders each row for the caller, the same way get-by-id does."""
    job = _job(
        salary_min=60000,
        salary_max=80000,
        salary_currency="EUR",
        compensation_disclosure=CompensationDisclosure.CONFIDENTIAL,
    )
    service = JobService(FakeJobRepository([job]))

    poster = Actor(member_id=POSTER_ID, is_admin=False)
    seen = (await service.list_jobs(actor=poster)).items[0]
    assert seen.salary_min == job.salary_min
    assert seen.salary_max == job.salary_max
    assert seen.salary_currency == "EUR"

    stranger = Actor(member_id=uuid.uuid4(), is_admin=False)
    for actor in (None, stranger):
        seen = (await service.list_jobs(actor=actor)).items[0]
        assert seen.salary_min is None
        assert seen.salary_max is None
        assert seen.salary_currency is None
        # The disclosure is not the secret; the numbers behind it are.
        assert seen.compensation_disclosure == CompensationDisclosure.CONFIDENTIAL
