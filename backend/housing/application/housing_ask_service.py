"""Natural-language Ask over the housing board.

Same shape as the directory's Ask in :mod:`backend.members.application.ask_service`, over
a different board and a different filter object. The two are kept apart rather than
generalised: the boards share a mechanism, not a use case, and one class covering both
would be parameterised by everything that matters.
"""

from __future__ import annotations

import time

from backend.core.actor import Actor
from backend.core.exceptions import LlmUnavailableError, RateLimitedError
from backend.core.llm.ask import LLM_DOWN_NOTE, ViewerContext, validate_question
from backend.core.llm.observability import log_ask
from backend.core.llm.ports import QuestionMeter
from backend.core.settings import get_llm_settings
from backend.housing.application.ports import (
    HousingFilters,
    HousingQueryTranslator,
    HousingRepository,
)
from backend.housing.application.visibility import for_viewer
from backend.housing.domain import (
    HousingAskAnswer,
    HousingAskInterpretation,
    HousingQuery,
    HousingStatus,
)


def to_housing_filters(query: HousingQuery) -> HousingFilters:
    return HousingFilters(
        kind=query.kind,
        city=query.city,
        district=query.district,
        # Closed listings are answers to a question nobody asked; Ask only ever sees open
        # ones, the same default the housing list endpoint uses.
        status=HousingStatus.OPEN,
        min_price=query.min_price,
        max_price=query.max_price,
        available_from=query.available_from,
        available_until=query.available_until,
        min_rooms=query.min_rooms,
        furnished=query.furnished,
        q=query.q,
    )


class HousingAskService:
    def __init__(
        self,
        housing: HousingRepository,
        *,
        translator: HousingQueryTranslator | None,
        fallback: HousingQueryTranslator,
        meter: QuestionMeter,
    ) -> None:
        self._housing = housing
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
    ) -> HousingAskAnswer:
        started = time.perf_counter()
        interpretation, model = await self._interpret(question, actor=actor, language=language)
        page_limit = min(interpretation.filters.limit or limit, limit)
        result = await self._housing.list(
            skip=skip, limit=page_limit, filters=to_housing_filters(interpretation.filters)
        )
        self._log(
            question,
            actor=actor,
            interpretation=interpretation,
            model=model,
            started=started,
            total=result.total,
        )
        return HousingAskAnswer(
            interpretation=interpretation,
            # An answer is a way of listing the board, so it hides the view counter exactly
            # the way the board's own list does.
            listings=[for_viewer(row, actor) for row in result.items],
            total=result.total,
        )

    async def explain(
        self, question: str, *, actor: Actor, language: str | None = None
    ) -> HousingAskInterpretation:
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
    ) -> tuple[HousingAskInterpretation, str]:
        validate_question(question)
        allowed = await self._meter.allow(
            rate_limit_key(actor), rate_per_minute=get_llm_settings().max_questions_per_minute
        )
        if not allowed:
            raise RateLimitedError("you are asking faster than we can answer; try again shortly")

        viewer = ViewerContext()
        if self._translator is not None:
            try:
                interpretation = await self._translator.translate(
                    question, viewer=viewer, language=language
                )
                return interpretation, self._translator.model_name
            except LlmUnavailableError:
                interpretation = await self._fallback.translate(
                    question, viewer=viewer, language=language
                )
                return (
                    interpretation.model_copy(
                        update={"unresolved": [*interpretation.unresolved, LLM_DOWN_NOTE]}
                    ),
                    self._fallback.model_name,
                )
        return (
            await self._fallback.translate(question, viewer=viewer, language=language),
            self._fallback.model_name,
        )

    @staticmethod
    def _log(
        question: str,
        *,
        actor: Actor,
        interpretation: HousingAskInterpretation,
        model: str,
        started: float,
        total: int | None,
    ) -> None:
        log_ask(
            board="housing",
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

    Spelled the same way as the directory's so a member who spends their allowance asking
    about people does not get a fresh one asking about flats: it is the same call to the
    same provider either way.
    """
    return str(actor.member_id) if actor.member_id else "unbound"
