"""Natural-language Ask over the member directory.

The shape of a question's life: validate it, meter it, resolve what "my class" means for
the person asking, translate it into a ``MemberQuery``, and then run the same repository
search the ordinary directory endpoint runs. The translator is the only step a language
model is involved in, and its output is a validated filter object, never a query. It is
also the only step worth caching: reading the question is deterministic and costs a second
of provider time, while the search behind it has to see the directory as it is now. Both
``/ask`` and ``/ask/explain`` go through ``_interpret``, so the preview a member types their
way to and the answer they then ask for are one model call, not two.

The Sankey flow an answer is drawn with belongs to Paths, so it is not assembled here.
``backend/members/api/ask.py`` composes the two, which keeps this service, and everything
below it, free of any knowledge of career groups beyond the strings it passes through.
"""

from __future__ import annotations

import time
from datetime import date
from uuid import UUID

from backend.core.actor import Actor
from backend.core.cache import TTLCache
from backend.core.exceptions import LlmUnavailableError, RateLimitedError
from backend.core.llm.ask import (
    LLM_DOWN_NOTE,
    ViewerContext,
    interpretation_key,
    validate_question,
)
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

#: How long one reading of one question is held. Reading a question is the only step that
#: costs a model call, and it is deterministic: the same words, from the same person, in the
#: same language, mean the same filter object. Ten minutes covers the way the board is
#: actually used (a preview on the way to an answer, then the same question paged through,
#: then somebody else asking the question that is on the front page), and is short enough
#: that a prompt change is live before anyone notices the old one.
INTERPRETATION_TTL_SECONDS = 600

#: Keyed on the whole of what the translator was given, viewer context included: two people
#: asking "who is in my class" mean different classes, and the same person asking in German
#: gets a German summary. A few hundred entries is a few hundred short filter objects.
_INTERPRETATIONS = TTLCache(maxsize=256, ttl=INTERPRETATION_TTL_SECONDS)


def _handed_out(entry: tuple[AskInterpretation, str]) -> tuple[AskInterpretation, str]:
    """A copy of a cached reading, for the caller to do what it likes with.

    An ``AskInterpretation`` is not frozen and neither is the ``MemberQuery`` inside it, so
    the cached object never leaves this module: an API layer that edited a chip, or a test
    that poked at one, would otherwise be editing what the next asker is handed. Same rule
    as ``Facets``, which is frozen and holds tuples for exactly this reason. It is applied on
    the way out of the miss branch too, so the first asker is not the one caller holding a
    reference to the cache's copy.
    """
    interpretation, model_name = entry
    return interpretation.model_copy(deep=True), model_name


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
            key = interpretation_key(
                board="members", question=question, language=language, viewer=viewer
            )
            cached = _INTERPRETATIONS.get(key)
            if cached is not None:
                return _handed_out(cached)
            try:
                interpretation = await self._translator.translate(
                    question, viewer=viewer, language=language
                )
                # Only a reading the model produced is kept. The keyword fallback below is
                # pure Python over the same words, so caching it would buy nothing and would
                # pin LLM_DOWN_NOTE onto every asker for ten minutes after the provider came
                # back. The meter is charged above either way: the cache spares the provider,
                # not the allowance.
                _INTERPRETATIONS.set(key, (interpretation, self._translator.model_name))
                return _handed_out((interpretation, self._translator.model_name))
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
        # ``today`` is set on every branch, including the two empty ones. The prompt reads it
        # to resolve "graduating this year", and a field the translator uses but the context
        # does not carry is a field the cache key cannot see: the reading would then outlive
        # the day it was made.
        today = date.today()
        if actor.member_id is None:
            return ViewerContext(today=today)
        # Three scalars, not a profile: the prompt needs a class label, a year and a city,
        # and loading the whole member to read them fetched positions and educations that
        # are thrown away here.
        class_label, location, class_year = await self._members.viewer_context(actor.member_id)
        if class_label is None and location is None and class_year is None:
            return ViewerContext(today=today)
        return ViewerContext(
            class_label=class_label,
            class_year=class_year,
            location=location,
            current_group=await self._viewer_groups.current_group_of(actor.member_id),
            today=today,
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
