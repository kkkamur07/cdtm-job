"""Application service: natural-language Ask over the job board.

Reading jobs is public on this board, but asking is not: a question costs a call to a
metered provider, so the router puts it behind an authenticated Actor and this service
meters it per Member, through the same Postgres-backed meter the members and housing
boards use.
"""

from __future__ import annotations

import time

from backend.core.actor import Actor
from backend.core.exceptions import LlmUnavailableError, RateLimitedError, ValidationError
from backend.core.llm.observability import log_ask
from backend.core.llm.ports import QuestionMeter
from backend.core.settings import get_llm_settings
from backend.jobboard.application.ports import (
    JobFilters,
    JobQueryTranslator,
    JobRepository,
)
from backend.jobboard.application.visibility import job_for_viewer
from backend.jobboard.domain import JobAskAnswer, JobAskInterpretation, JobQuery, JobStatus

MIN_QUESTION_LENGTH = 3
MAX_QUESTION_LENGTH = 300

_LLM_DOWN_NOTE = "LLM unavailable, keyword interpretation used"


def to_job_filters(query: JobQuery) -> JobFilters:
    return JobFilters(
        # Ask only ever sees the board as the public sees it. A draft is a job nobody has
        # decided to advertise yet, and a question is not a reason to surface one.
        status=JobStatus.PUBLISHED,
        employment_types=tuple(query.employment_type or ()),
        work_arrangements=tuple(query.work_arrangement or ()),
        experience_levels=tuple(query.experience_level or ()),
        q=query.q,
        city=query.city,
        country=query.country,
        remote_only=query.remote_only,
        company=query.company,
        is_cdtm_startup=query.is_cdtm_startup,
        salary_min=query.salary_min,
        posted_within_days=query.posted_within_days,
        sort=query.sort,
    )


class JobAskService:
    def __init__(
        self,
        jobs: JobRepository,
        *,
        translator: JobQueryTranslator | None,
        fallback: JobQueryTranslator,
        meter: QuestionMeter,
    ) -> None:
        self._jobs = jobs
        self._translator = translator
        self._fallback = fallback
        self._meter = meter

    async def ask(
        self,
        question: str,
        *,
        actor: Actor,
        skip: int,
        limit: int,
        language: str | None = None,
    ) -> JobAskAnswer:
        started = time.perf_counter()
        interpretation, model = await self._interpret(question, actor=actor, language=language)
        page_limit = min(interpretation.filters.limit or limit, limit)
        result = await self._jobs.list(
            skip=skip, limit=page_limit, filters=to_job_filters(interpretation.filters)
        )
        self._log(
            question,
            actor=actor,
            interpretation=interpretation,
            model=model,
            started=started,
            total=result.total,
        )
        return JobAskAnswer(
            interpretation=interpretation,
            # An answer is a way of listing the board, so it hides a confidential salary
            # exactly the way the board's own list does.
            jobs=[job_for_viewer(job, actor) for job in result.items],
            total=result.total,
        )

    async def explain(
        self, question: str, *, actor: Actor, language: str | None = None
    ) -> JobAskInterpretation:
        started = time.perf_counter()
        interpretation, model = await self._interpret(question, actor=actor, language=language)
        self._log(
            question,
            actor=actor,
            interpretation=interpretation,
            model=model,
            started=started,
            total=None,
        )
        return interpretation

    async def _interpret(
        self, question: str, *, actor: Actor, language: str | None = None
    ) -> tuple[JobAskInterpretation, str]:
        length = len(question.strip())
        if length < MIN_QUESTION_LENGTH:
            raise ValidationError("ask a question of at least three characters")
        if length > MAX_QUESTION_LENGTH:
            raise ValidationError(
                f"that question is {length} characters; keep it under {MAX_QUESTION_LENGTH}"
            )
        allowed = await self._meter.allow(
            rate_limit_key(actor), rate_per_minute=get_llm_settings().max_questions_per_minute
        )
        if not allowed:
            raise RateLimitedError("you are asking faster than we can answer; try again shortly")

        if self._translator is not None:
            try:
                return (
                    await self._translator.translate(question, language=language),
                    self._translator.model_name,
                )
            except LlmUnavailableError:
                interpretation = await self._fallback.translate(question, language=language)
                return (
                    interpretation.model_copy(
                        update={"unresolved": [*interpretation.unresolved, _LLM_DOWN_NOTE]}
                    ),
                    self._fallback.model_name,
                )
        return (
            await self._fallback.translate(question, language=language),
            self._fallback.model_name,
        )

    @staticmethod
    def _log(
        question: str,
        *,
        actor: Actor,
        interpretation: JobAskInterpretation,
        model: str,
        started: float,
        total: int | None,
    ) -> None:
        log_ask(
            board="jobs",
            actor=rate_limit_key(actor),
            question_length=len(question),
            source=interpretation.source,
            model=model,
            latency_ms=int((time.perf_counter() - started) * 1000),
            filters=interpretation.filters.model_dump(exclude_none=True, mode="json"),
            total=total,
            unresolved=interpretation.unresolved,
        )


def rate_limit_key(actor: Actor) -> str:
    """One bucket per member, shared with every other board's Ask.

    Spelled the same way as the directory's and housing's so a member who spends their
    allowance asking about people does not get a fresh one asking about jobs: it is the same
    call to the same provider either way. It was keyed on the account id and counted in
    process memory, which made it both a second allowance and unenforced across workers.
    """
    return str(actor.member_id) if actor.member_id else "unbound"
