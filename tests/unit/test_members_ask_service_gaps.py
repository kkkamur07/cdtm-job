"""AskService with a provider configured, and the filter object a question becomes.

Every other test in this suite runs with ``LLM_PROVIDER=none``, so ``AskService`` is always
built with ``translator=None`` and the whole "a model answered, or the model was down"
branch never executes. These tests build the service directly with fakes that implement the
``QueryTranslator``, ``MemberRepository``, ``ViewerGroupSource`` and ``QuestionMeter``
ports, which is the only way to exercise the path an install with credentials takes. No
network, no database.
"""

from __future__ import annotations

import uuid
from uuid import UUID

from backend.core.actor import Actor
from backend.core.exceptions import LlmUnavailableError
from backend.core.llm.ask import LLM_DOWN_NOTE, ViewerContext
from backend.core.page import PageResult
from backend.members.application.ask_service import AskService, to_member_filters
from backend.members.application.ports import MemberFilters
from backend.members.domain import (
    AskInterpretation,
    ClassRef,
    Intent,
    MemberProfile,
    MemberQuery,
    Role,
)

VIEWER_ID = uuid.uuid4()


class FakeTranslator:
    """A ``QueryTranslator`` that echoes what it was handed back to the caller.

    The service's own output is the only thing a test can see, so the question, the viewer
    and the language it was asked with are reflected into the interpretation it returns.
    """

    def __init__(self, source: str, *, model_name: str, raises: Exception | None = None) -> None:
        self.source = source
        self.model_name = model_name
        self._raises = raises
        self.viewers: list[ViewerContext | None] = []

    async def translate(
        self, question: str, *, viewer: ViewerContext, language: str | None = None
    ) -> AskInterpretation:
        self.viewers.append(viewer)
        if self._raises is not None:
            raise self._raises
        return AskInterpretation(
            summary=f"{self.source} read: {question}",
            filters=MemberQuery(q=question),
            confidence=0.5,
            unresolved=[f"language {language}"] if language else [],
            source=self.source,
        )


class FakeMembers:
    """Just the two ``MemberRepository`` methods an Ask goes through."""

    def __init__(self, profile: MemberProfile | None = None) -> None:
        self.profile = profile
        self.searches: list[tuple[int, int, MemberFilters, UUID | None]] = []

    async def get_by_id(self, member_id: UUID) -> MemberProfile | None:
        if self.profile is not None and self.profile.id == member_id:
            return self.profile
        return None

    async def viewer_context(self, member_id: UUID) -> tuple[str | None, str | None, int | None]:
        """The three scalars the real repository reads in one statement, derived here from
        the same profile the fake already holds so the expectations below do not move."""
        p = self.profile
        if p is None or p.id != member_id:
            return (None, None, None)
        years = [c.year for c in p.classes]
        return (p.class_label, p.location, max(years) if years else None)

    async def search(
        self, *, skip: int, limit: int, filters: MemberFilters, viewer_member_id: UUID | None
    ) -> PageResult:
        self.searches.append((skip, limit, filters, viewer_member_id))
        return PageResult(items=[], total=0)


class FakeGroups:
    """Where the asker works now, in the Paths read model's words."""

    def __init__(self, member_id: UUID, group: str) -> None:
        self._member_id = member_id
        self._group = group

    async def current_group_of(self, member_id: UUID) -> str | None:
        return self._group if member_id == self._member_id else None


class AllowingMeter:
    def __init__(self) -> None:
        self.keys: list[str] = []

    async def allow(self, key: str, *, rate_per_minute: int) -> bool:
        self.keys.append(key)
        return True


def viewer_profile() -> MemberProfile:
    """An asker with two linked classes, a home town and a career group."""
    return MemberProfile(
        id=VIEWER_ID,
        slug="vera-viewer",
        name="Vera Viewer",
        class_label="Fall 2019",
        location="Munich",
        classes=[
            ClassRef(id=1, label="Fall 2018", year=2018),
            ClassRef(id=2, label="Fall 2019", year=2019),
        ],
    )


def build_service(
    *, translator: FakeTranslator | None, fallback: FakeTranslator, members: FakeMembers
) -> AskService:
    return AskService(
        members,
        translator=translator,
        fallback=fallback,
        meter=AllowingMeter(),
        viewer_groups=FakeGroups(VIEWER_ID, "Venture Capital"),
    )


async def test_a_configured_provider_answers_and_the_question_reaches_it_whole() -> None:
    translator = FakeTranslator("llm", model_name="fake-model")
    fallback = FakeTranslator("rules", model_name="-")
    service = build_service(
        translator=translator, fallback=fallback, members=FakeMembers(viewer_profile())
    )

    interpretation = await service.explain(
        "who studied at Stanford", actor=Actor(VIEWER_ID), language="de"
    )

    assert interpretation.source == "llm"
    assert interpretation.summary == "llm read: who studied at Stanford"
    assert interpretation.filters.q == "who studied at Stanford"
    # The asked-for summary language is the translator's business, so it has to arrive.
    assert interpretation.unresolved == ["language de"]
    # The keyword translator is not consulted while the provider is answering.
    assert fallback.viewers == []


async def test_a_provider_that_is_down_is_answered_with_keywords_and_says_so() -> None:
    translator = FakeTranslator("llm", model_name="fake-model", raises=LlmUnavailableError("down"))
    fallback = FakeTranslator("rules", model_name="-")
    service = build_service(
        translator=translator, fallback=fallback, members=FakeMembers(viewer_profile())
    )

    interpretation = await service.explain(
        "who studied at Stanford", actor=Actor(VIEWER_ID), language="de"
    )

    # A provider outage degrades the answer; it is not a 503 on a search.
    assert interpretation.source == "rules"
    assert interpretation.summary == "rules read: who studied at Stanford"
    assert interpretation.filters.q == "who studied at Stanford"
    # The note is appended to whatever the keyword translator could not resolve itself,
    # so the UI can say why the reading looks coarser than usual.
    assert interpretation.unresolved == ["language de", LLM_DOWN_NOTE]


async def test_the_viewer_a_translator_is_given_is_the_asker_own_row() -> None:
    """Relative phrases resolve from the person asking, before any query runs."""
    translator = FakeTranslator("llm", model_name="fake-model")
    fallback = FakeTranslator("rules", model_name="-")
    service = build_service(
        translator=translator, fallback=fallback, members=FakeMembers(viewer_profile())
    )

    await service.explain("people from my class", actor=Actor(VIEWER_ID), language=None)

    assert translator.viewers == [
        ViewerContext(
            class_label="Fall 2019",
            # The most recent linked class, not the first one.
            class_year=2019,
            location="Munich",
            current_group="Venture Capital",
        )
    ]


async def test_a_down_provider_hands_the_same_viewer_to_the_keyword_translator() -> None:
    translator = FakeTranslator("llm", model_name="fake-model", raises=LlmUnavailableError("down"))
    fallback = FakeTranslator("rules", model_name="-")
    service = build_service(
        translator=translator, fallback=fallback, members=FakeMembers(viewer_profile())
    )

    await service.explain("people from my class", actor=Actor(VIEWER_ID), language=None)

    assert fallback.viewers == translator.viewers
    assert fallback.viewers[0].class_year == 2019


async def test_an_asker_with_no_member_row_gets_an_empty_viewer() -> None:
    translator = FakeTranslator("llm", model_name="fake-model")
    fallback = FakeTranslator("rules", model_name="-")
    service = build_service(
        translator=translator, fallback=fallback, members=FakeMembers(viewer_profile())
    )

    await service.explain("people from my class", actor=Actor(uuid.uuid4()))

    assert translator.viewers == [ViewerContext()]


async def test_ask_pages_the_search_and_reports_the_whole_match_count() -> None:
    """The page asked for is the page searched for, even when the model wants more."""
    translator = FakeTranslator("llm", model_name="fake-model")
    members = FakeMembers(viewer_profile())
    service = build_service(
        translator=translator, fallback=FakeTranslator("rules", model_name="-"), members=members
    )

    await service.ask("people in Berlin", actor=Actor(VIEWER_ID), skip=40, limit=5)

    skip, limit, _, _ = members.searches[-1]
    assert (skip, limit) == (40, 5)


def test_to_member_filters_carries_every_field_through() -> None:
    """The one place a translated question becomes a directory filter."""
    query = MemberQuery(
        q="plato",
        school="Stanford",
        degree="MSc",
        major="Computer Science",
        company="Index Ventures",
        past_company="McKinsey",
        title="Investor",
        location="Munich",
        class_label="Fall 2019",
        class_year_min=2018,
        class_year_max=2020,
        study_group="Business & Management",
        first_step_group="Consulting",
        current_group="Venture Capital",
        skills=["python", "sql"],
        languages=["de", "en"],
        intents=[Intent.MENTORING, Intent.INVESTING],
        roles=[Role.STUDENT, Role.CA],
        is_ca=True,
        limit=5,
        sort="name",
    )

    assert to_member_filters(query) == MemberFilters(
        q="plato",
        class_label="Fall 2019",
        class_year_min=2018,
        class_year_max=2020,
        major="Computer Science",
        roles=("student", "ca"),
        location="Munich",
        intents=("mentoring", "investing"),
        # "open to mentoring and investing" is one person who does both, not the union.
        intents_match="all",
        skills=("python", "sql"),
        languages=("de", "en"),
        is_ca=True,
        company="Index Ventures",
        past_company="McKinsey",
        title="Investor",
        school="Stanford",
        degree="MSc",
        study_group="Business & Management",
        first_step_group="Consulting",
        current_group="Venture Capital",
        sort="name",
    )


def test_a_question_with_no_opinion_filters_on_nothing() -> None:
    filters = to_member_filters(MemberQuery())
    assert (filters.roles, filters.intents, filters.skills, filters.languages) == ((), (), (), ())
    assert filters.q is None and filters.sort is None
    # Still "all": an empty intent list has nothing to combine, but the rule does not move.
    assert filters.intents_match == "all"
