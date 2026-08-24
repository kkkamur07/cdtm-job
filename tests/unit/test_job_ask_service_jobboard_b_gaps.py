"""The jobs Ask with a provider configured, and the filter object a question becomes.

Every other test runs with ``LLM_PROVIDER=none``, so ``JobAskService`` is always built with
``translator=None`` and the "a model answered, or the model was down" branch never runs.
These build the service directly on fakes that implement the ``JobQueryTranslator``,
``JobRepository`` and ``QuestionMeter`` ports, which is the only way to walk the path an
install with credentials takes. No network, no database.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from backend.core.actor import Actor
from backend.core.exceptions import LlmUnavailableError, RateLimitedError, ValidationError
from backend.core.page import PageResult
from backend.housing.application.housing_ask_service import (
    rate_limit_key as housing_rate_limit_key,
)
from backend.jobboard.application.job_ask_service import (
    JobAskService,
    rate_limit_key,
    to_job_filters,
)
from backend.jobboard.application.ports import JobFilters
from backend.jobboard.domain import (
    CompensationDisclosure,
    EmploymentType,
    ExperienceLevel,
    Job,
    JobAskInterpretation,
    JobQuery,
    JobStatus,
    WorkArrangement,
)
from backend.members.application.ask_service import rate_limit_key as members_rate_limit_key

ASKER = uuid.uuid4()
LLM_DOWN_NOTE = "LLM unavailable, keyword interpretation used"
ASK_LOGGER = "backend.ask"


class FakeTranslator:
    """A ``JobQueryTranslator`` that reflects what it was handed back to the caller."""

    def __init__(
        self,
        source: str,
        *,
        model_name: str,
        query: JobQuery | None = None,
        raises: Exception | None = None,
    ) -> None:
        self.source = source
        self.model_name = model_name
        self._query = query
        self._raises = raises
        self.calls: list[tuple[str, str | None]] = []

    async def translate(
        self, question: str, *, language: str | None = None
    ) -> JobAskInterpretation:
        self.calls.append((question, language))
        if self._raises is not None:
            raise self._raises
        return JobAskInterpretation(
            summary=f"{self.source} read: {question}"[:300],
            filters=self._query or JobQuery(q=question[:200]),
            confidence=0.5,
            unresolved=[f"language {language}"] if language else [],
            source=self.source,
        )


class FakeJobs:
    """The one ``JobRepository`` method an Ask goes through."""

    def __init__(self, items: list[Job] | None = None, total: int | None = None) -> None:
        self._items = items or []
        self._total = total if total is not None else len(self._items)
        self.calls: list[tuple[int, int, JobFilters]] = []

    async def list(self, *, skip: int, limit: int, filters: JobFilters) -> PageResult[Job]:
        self.calls.append((skip, limit, filters))
        return PageResult(items=self._items, total=self._total)


class RecordingMeter:
    def __init__(self, *, allow: bool = True) -> None:
        self._allow = allow
        self.keys: list[str] = []

    async def allow(self, key: str, *, rate_per_minute: int) -> bool:
        self.keys.append(key)
        return self._allow


def build_service(
    *,
    translator: FakeTranslator | None = None,
    fallback: FakeTranslator | None = None,
    jobs: FakeJobs | None = None,
    meter: RecordingMeter | None = None,
) -> JobAskService:
    return JobAskService(
        jobs or FakeJobs(),
        translator=translator,
        fallback=fallback or FakeTranslator("rules", model_name="-"),
        meter=meter or RecordingMeter(),
    )


def a_job(**over) -> Job:
    now = datetime.now(UTC)
    body = {
        "id": uuid.uuid4(),
        "company_id": uuid.uuid4(),
        "posted_by_member_id": ASKER,
        "title": "Founding Engineer",
        "description": "Build things",
        "employment_type": EmploymentType.FULL_TIME,
        "work_arrangement": WorkArrangement.REMOTE,
        "experience_level": ExperienceLevel.MID,
        "status": JobStatus.PUBLISHED,
        "created_at": now,
        "updated_at": now,
        "published_at": now,
    }
    body.update(over)
    return Job(**body)


# ---- a question becomes a board filter ---------------------------------------------------


def test_every_field_of_a_translated_question_reaches_the_board() -> None:
    """The one place a question becomes a query against the postings."""
    query = JobQuery(
        q="product",
        employment_type=[EmploymentType.WORKING_STUDENT, EmploymentType.INTERNSHIP],
        work_arrangement=[WorkArrangement.REMOTE, WorkArrangement.HYBRID],
        experience_level=[ExperienceLevel.ENTRY],
        city="Munich",
        country="Germany",
        remote_only=True,
        company="ACME",
        is_cdtm_startup=True,
        salary_min=Decimal("80000"),
        posted_within_days=7,
        limit=5,
        sort="salary",
    )

    assert to_job_filters(query) == JobFilters(
        # Ask reads the board the way the public reads it, whatever the question asked for.
        status=JobStatus.PUBLISHED,
        employment_types=(EmploymentType.WORKING_STUDENT, EmploymentType.INTERNSHIP),
        work_arrangements=(WorkArrangement.REMOTE, WorkArrangement.HYBRID),
        experience_levels=(ExperienceLevel.ENTRY,),
        q="product",
        city="Munich",
        country="Germany",
        remote_only=True,
        company="ACME",
        is_cdtm_startup=True,
        salary_min=Decimal("80000"),
        posted_within_days=7,
        sort="salary",
    )


def test_a_question_with_no_opinion_still_only_sees_the_published_board() -> None:
    filters = to_job_filters(JobQuery())
    assert filters.status is JobStatus.PUBLISHED
    assert (filters.employment_types, filters.work_arrangements, filters.experience_levels) == (
        (),
        (),
        (),
    )
    assert filters.q is None and filters.sort is None and filters.remote_only is None


# ---- a provider that answers, and one that is down ---------------------------------------


async def test_a_configured_provider_answers_and_the_question_reaches_it_whole() -> None:
    translator = FakeTranslator("llm", model_name="fake-model")
    fallback = FakeTranslator("rules", model_name="-")
    service = build_service(translator=translator, fallback=fallback)

    interpretation = await service.explain(
        "remote product roles", actor=Actor(ASKER), language="de"
    )

    assert interpretation.source == "llm"
    assert interpretation.summary == "llm read: remote product roles"
    assert interpretation.filters.q == "remote product roles"
    # The asked-for summary language is the translator's business, so it has to arrive.
    assert interpretation.unresolved == ["language de"]
    assert translator.calls == [("remote product roles", "de")]
    # The keyword translator is not consulted while the provider is answering.
    assert fallback.calls == []


async def test_a_provider_that_is_down_is_answered_with_keywords_and_says_so() -> None:
    translator = FakeTranslator("llm", model_name="fake-model", raises=LlmUnavailableError("down"))
    fallback = FakeTranslator("rules", model_name="-")
    service = build_service(translator=translator, fallback=fallback)

    interpretation = await service.explain(
        "remote product roles", actor=Actor(ASKER), language="de"
    )

    # An outage degrades the answer; it is not a 503 on a search of our own board.
    assert interpretation.source == "rules"
    assert interpretation.filters.q == "remote product roles"
    # The note is appended to what the keyword rules could not read themselves, so the UI
    # can say why this reading looks coarser than usual.
    assert interpretation.unresolved == ["language de", LLM_DOWN_NOTE]
    assert fallback.calls == [("remote product roles", "de")]


async def test_with_no_provider_the_keywords_answer_and_claim_nothing_went_wrong() -> None:
    fallback = FakeTranslator("rules", model_name="-")
    service = build_service(translator=None, fallback=fallback)

    interpretation = await service.explain("remote product roles", actor=Actor(ASKER))

    assert interpretation.source == "rules"
    assert interpretation.unresolved == []
    assert fallback.calls == [("remote product roles", None)]


# ---- what a question has to be before it costs anything ----------------------------------


@pytest.mark.parametrize("length", [3, 300])
async def test_a_question_at_the_edge_of_the_accepted_lengths_is_answered(length: int) -> None:
    service = build_service()
    interpretation = await service.explain("x" * length, actor=Actor(ASKER))
    assert interpretation.source == "rules"


@pytest.mark.parametrize("length", [2, 301])
async def test_a_question_outside_those_lengths_is_refused(length: int) -> None:
    service = build_service()
    with pytest.raises(ValidationError):
        await service.explain("x" * length, actor=Actor(ASKER))


async def test_a_question_is_measured_after_its_whitespace_is_trimmed() -> None:
    service = build_service()
    with pytest.raises(ValidationError):
        await service.explain("  x  ", actor=Actor(ASKER))


async def test_a_caller_over_their_allowance_is_told_so_before_a_provider_is_called() -> None:
    translator = FakeTranslator("llm", model_name="fake-model")
    service = build_service(translator=translator, meter=RecordingMeter(allow=False))

    with pytest.raises(RateLimitedError):
        await service.ask("remote jobs", actor=Actor(ASKER), skip=0, limit=10)
    assert translator.calls == []


async def test_the_allowance_is_counted_against_the_member_who_asked() -> None:
    meter = RecordingMeter()
    service = build_service(meter=meter)

    await service.ask("remote jobs", actor=Actor(ASKER), skip=0, limit=10)
    await service.ask("remote jobs", actor=Actor(uuid.uuid4()), skip=0, limit=10)

    assert meter.keys[0] == str(ASKER)
    # Two members, two buckets: one member's spend is not the other's.
    assert meter.keys[0] != meter.keys[1]


def test_the_bucket_is_the_one_every_other_board_counts_into() -> None:
    """A question costs the same call whichever board it is asked on, so it costs the same
    allowance. The three boards therefore have to spell the key identically."""
    bound = Actor(ASKER)
    unbound = Actor(None)
    assert rate_limit_key(bound) == members_rate_limit_key(bound) == housing_rate_limit_key(bound)
    assert rate_limit_key(bound) == str(ASKER)
    assert (
        rate_limit_key(unbound)
        == members_rate_limit_key(unbound)
        == housing_rate_limit_key(unbound)
    )
    assert rate_limit_key(unbound) != rate_limit_key(bound)


# ---- the answer -------------------------------------------------------------------------


async def test_the_page_the_caller_asked_for_is_the_page_that_is_searched() -> None:
    jobs = FakeJobs()
    service = build_service(jobs=jobs)

    await service.ask("remote jobs", actor=Actor(ASKER), skip=40, limit=5)

    skip, limit, _ = jobs.calls[-1]
    assert (skip, limit) == (40, 5)


async def test_a_translated_page_size_may_shrink_the_page_but_never_grow_it() -> None:
    """``limit`` is the caller's ceiling; a model asking for more does not get more."""
    jobs = FakeJobs()
    translator = FakeTranslator("llm", model_name="fake-model", query=JobQuery(limit=100))
    service = build_service(translator=translator, jobs=jobs)
    await service.ask("remote jobs", actor=Actor(ASKER), skip=0, limit=5)
    assert jobs.calls[-1][1] == 5

    smaller = FakeTranslator("llm", model_name="fake-model", query=JobQuery(limit=2))
    service = build_service(translator=smaller, jobs=jobs)
    await service.ask("remote jobs", actor=Actor(ASKER), skip=0, limit=5)
    assert jobs.calls[-1][1] == 2


async def test_an_answer_hides_a_confidential_salary_from_everybody_but_the_poster() -> None:
    """An answer is a way of listing the board, so it redacts what the board redacts."""
    job = a_job(
        salary_min=Decimal("60000"),
        salary_max=Decimal("80000"),
        salary_currency="EUR",
        compensation_disclosure=CompensationDisclosure.CONFIDENTIAL,
    )
    service = build_service(jobs=FakeJobs([job]))

    stranger = await service.ask("remote jobs", actor=Actor(uuid.uuid4()), skip=0, limit=10)
    assert stranger.jobs[0].salary_min is None
    assert stranger.jobs[0].salary_max is None
    assert stranger.jobs[0].salary_currency is None
    assert stranger.total == 1

    poster = await service.ask("remote jobs", actor=Actor(ASKER), skip=0, limit=10)
    assert poster.jobs[0].salary_min == Decimal("60000")

    admin = await service.ask("remote jobs", actor=Actor(None, is_admin=True), skip=0, limit=10)
    assert admin.jobs[0].salary_max == Decimal("80000")


async def test_explain_reads_the_question_without_searching_the_board() -> None:
    jobs = FakeJobs([a_job()])
    service = build_service(jobs=jobs)

    interpretation = await service.explain("remote jobs", actor=Actor(ASKER))

    assert interpretation.source == "rules"
    assert jobs.calls == []


# ---- the log line an operator counts questions with --------------------------------------


async def test_an_answered_question_is_logged_with_its_shape_and_its_filters(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """``docs/ask.md`` reads these with grep, so the fields are a contract."""
    translator = FakeTranslator(
        "llm",
        model_name="fake-model",
        query=JobQuery(city="Munich", employment_type=[EmploymentType.WORKING_STUDENT]),
    )
    service = build_service(
        translator=translator, jobs=FakeJobs([a_job(), a_job()], total=7), meter=RecordingMeter()
    )

    caplog.clear()
    with caplog.at_level(logging.INFO, logger=ASK_LOGGER):
        await service.ask("working student jobs in munich", actor=Actor(ASKER), skip=0, limit=10)

    records = [r for r in caplog.records if r.name == ASK_LOGGER]
    assert len(records) == 1
    line = records[0].getMessage()
    assert "board=jobs" in line
    assert f"actor={ASKER}" in line
    assert f"question_length={len('working student jobs in munich')}" in line
    assert "source=llm" in line
    assert "model=fake-model" in line
    assert "total=7" in line
    assert "unresolved=[]" in line
    # Only the fields the question set, and rendered the way the wire renders them.
    assert 'filters={"city": "Munich", "employment_type": ["working_student"]}' in line, line
    latency = int(line.split("latency_ms=")[1].split(" ")[0])
    assert 0 <= latency < 60_000


async def test_an_explained_question_is_logged_with_no_result_count(
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = build_service()
    caplog.clear()
    with caplog.at_level(logging.INFO, logger=ASK_LOGGER):
        await service.explain("remote jobs", actor=Actor(ASKER))

    line = [r for r in caplog.records if r.name == ASK_LOGGER][0].getMessage()
    assert " total=- " in line
    assert json.loads(line.split("unresolved=")[1].split(" filters=")[0]) == []
