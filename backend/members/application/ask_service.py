"""Natural-language Ask over the member directory.

The shape of a question's life: validate it, meter it, resolve what "my class" means for
the person asking, translate it into a ``MemberQuery``, and then run the same repository
search the ordinary directory endpoint runs. The translator is the only step a language
model is involved in, and its output is a validated filter object, never a query.

The Sankey flow an answer is drawn with belongs to Paths, so it is not assembled here.
``backend/members/api/ask.py`` composes the two, which keeps this service, and everything
below it, free of any knowledge of career groups beyond the strings it passes through.
"""

from __future__ import annotations

import time
from uuid import UUID

from backend.core.actor import Actor
from backend.core.exceptions import LlmUnavailableError, RateLimitedError
from backend.core.llm.ask import LLM_DOWN_NOTE, ViewerContext, validate_question
from backend.core.llm.observability import log_ask
from backend.core.llm.ports import QuestionMeter
from backend.core.settings import get_llm_settings
from backend.members.application.ports import (
    MemberFilters,
    MemberRepository,
    QueryTranslator,
    ViewerGroupSource,
)
from backend.members.domain import AskAnswer, AskInterpretation, MemberQuery


def to_member_filters(query: MemberQuery) -> MemberFilters:
    """The one place a translated question becomes a directory filter."""
    return MemberFilters(
        q=query.q,
        class_label=query.class_label,
        class_year_min=query.class_year_min,
        class_year_max=query.class_year_max,
        major=query.major,
        roles=tuple(r.value for r in query.roles or ()),
        location=query.location,
        intents=tuple(i.value for i in query.intents or ()),
        # "open to mentoring and investing" is one person who does both, not the union.
        intents_match="all",
        skills=tuple(query.skills or ()),
        languages=tuple(query.languages or ()),
        is_ca=query.is_ca,
        company=query.company,
        past_company=query.past_company,
        title=query.title,
        school=query.school,
        degree=query.degree,
        study_group=query.study_group,
        first_step_group=query.first_step_group,
        current_group=query.current_group,
        sort=query.sort,
    )


class AskService:
    def __init__(
        self,
        members: MemberRepository,
        *,
        translator: QueryTranslator | None,
        fallback: QueryTranslator,
        meter: QuestionMeter,
        viewer_groups: ViewerGroupSource,
    ) -> None:
        self._members = members
        self._translator = translator
        self._fallback = fallback
        self._meter = meter
        self._viewer_groups = viewer_groups

    # ---- use cases ----------------------------------------------------------------------

    async def ask(
        self,
        question: str,
        *,
        actor: Actor,
        skip: int,
        limit: int,
        language: str | None = None,
    ) -> AskAnswer:
        started = time.perf_counter()
        interpretation, model = await self._interpret(question, actor=actor, language=language)
        filters = to_member_filters(interpretation.filters)
        page_limit = min(interpretation.filters.limit or limit, limit)
        result = await self._members.search(
            skip=skip, limit=page_limit, filters=filters, viewer_member_id=actor.member_id
        )
        self._log(
            question,
            actor=actor,
            interpretation=interpretation,
            model=model,
            started=started,
            total=result.total,
        )
        return AskAnswer(
            interpretation=interpretation,
            members=result.items,
            total=result.total,
        )

    async def matching_member_ids(self, interpretation: AskInterpretation) -> list[UUID]:
        """Every member an interpretation matches, not just the page that was returned.

        The Ask router hands these to Paths so the Sankey is drawn over exactly the people
        the answer is about. It is a second pass over the same predicates rather than a
        second reading of the question, so it costs no model call.
        """
        return await self._members.matching_ids(to_member_filters(interpretation.filters))

    async def explain(
        self, question: str, *, actor: Actor, language: str | None = None
    ) -> AskInterpretation:
        """Translate only. Powers the live "this is how I read it" preview.

        It shares the rate limit bucket with :meth:`ask` because it costs the same call to
        the same provider; a preview on every keystroke would otherwise be free.
        """
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

    # ---- internals ----------------------------------------------------------------------

    async def _interpret(
        self, question: str, *, actor: Actor, language: str | None
    ) -> tuple[AskInterpretation, str]:
        validate_question(question)
        await self._charge(actor)
        viewer = await self._viewer_context(actor)
        if self._translator is not None:
            try:
                return await self._translator.translate(
                    question, viewer=viewer, language=language
                ), self._translator.model_name
            except LlmUnavailableError:
                # The provider being down is not the member's problem: answer the question
                # with keywords and say so, rather than returning a 503 for a search.
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

    async def _charge(self, actor: Actor) -> None:
        allowed = await self._meter.allow(
            rate_limit_key(actor), rate_per_minute=get_llm_settings().max_questions_per_minute
        )
        if not allowed:
            raise RateLimitedError("you are asking faster than we can answer; try again shortly")

    async def _viewer_context(self, actor: Actor) -> ViewerContext:
        if actor.member_id is None:
            return ViewerContext()
        profile = await self._members.get_by_id(actor.member_id)
        if profile is None:
            return ViewerContext()
        years = [c.year for c in profile.classes]
        return ViewerContext(
            class_label=profile.class_label,
            class_year=max(years) if years else None,
            location=profile.location,
            current_group=await self._viewer_groups.current_group_of(actor.member_id),
        )

    @staticmethod
    def _log(
        question: str,
        *,
        actor: Actor,
        interpretation: AskInterpretation,
        model: str,
        started: float,
        total: int | None,
    ) -> None:
        log_ask(
            board="members",
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
    """One bucket per member.

    An Account with no Member shares a single bucket. That is deliberate: this context's
    whole view of the caller is the Actor, which carries no account id, and unbound
    accounts are a handful of shared mailboxes rather than a crowd.
    """
    return str(actor.member_id) if actor.member_id else "unbound"
