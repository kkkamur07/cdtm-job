"""Reading a question is cached; searching for the answer is not.

The translation of a question into an interpretation is the only step that costs a model
call, and it is deterministic: the same words, from the same person, in the same language,
are the same filter object. The rows behind it are not, which is why only the reading is
held. These tests drive the two Ask services directly with fakes; nothing here reaches a
provider or a database.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest

from backend.core.actor import Actor
from backend.core.cache import clear_all
from backend.core.exceptions import LlmUnavailableError
from backend.core.llm.ask import LLM_DOWN_NOTE, ViewerContext, interpretation_key
from backend.core.page import PageResult
from backend.housing.application import housing_ask_service
from backend.housing.application.housing_ask_service import HousingAskService
from backend.housing.domain import HousingAskInterpretation, HousingQuery
from backend.members.application import ask_service
from backend.members.application.ask_service import AskService
from backend.members.domain import AskInterpretation, ClassRef, MemberProfile, MemberQuery

VIEWER_ID = uuid.uuid4()
OTHER_ID = uuid.uuid4()


@pytest.fixture(autouse=True)
def _empty_caches():
    """Every test starts and leaves the process with no cached reading."""
    clear_all()
    yield
    clear_all()


# ---- fakes ---------------------------------------------------------------------------------


class CountingTranslator:
    """A ``QueryTranslator`` that counts how often it was actually asked."""

    def __init__(self, *, raises: Exception | None = None) -> None:
        self.model_name = "fake-model"
        self.calls = 0
        self._raises = raises

    async def translate(
        self, question: str, *, viewer: ViewerContext, language: str | None = None
    ) -> AskInterpretation:
        self.calls += 1
        if self._raises is not None:
            raise self._raises
        return AskInterpretation(
            summary=f"read: {question}",
            filters=MemberQuery(q=question),
            confidence=0.5,
            unresolved=[],
            source="llm",
        )


class RulesTranslator:
    def __init__(self) -> None:
        self.model_name = "-"
        self.calls = 0

    async def translate(
        self, question: str, *, viewer: ViewerContext, language: str | None = None
    ) -> AskInterpretation:
        self.calls += 1
        return AskInterpretation(
            summary=f"rules: {question}",
            filters=MemberQuery(q=question),
            confidence=0.2,
            unresolved=[],
            source="rules",
        )


class RecordingViewerTranslator:
    """Keeps the ``ViewerContext`` it was handed, for either board's interpretation type."""

    def __init__(self, interpretation, query) -> None:
        self.model_name = "fake-model"
        self.viewers: list[ViewerContext] = []
        self._interpretation = interpretation
        self._query = query

    async def translate(self, question: str, *, viewer: ViewerContext, language=None):
        self.viewers.append(viewer)
        return self._interpretation(
            summary=f"read: {question}",
            filters=self._query(q=question),
            confidence=0.5,
            unresolved=[],
            source="llm",
        )


class FakeMembers:
    def __init__(self, *profiles: MemberProfile) -> None:
        self._profiles = {p.id: p for p in profiles}
        self.searches = 0

    async def viewer_context(self, member_id) -> tuple[str | None, str | None, int | None]:
        p = self._profiles.get(member_id)
        if p is None:
            return (None, None, None)
        years = [c.year for c in p.classes]
        return (p.class_label, p.location, max(years) if years else None)

    async def search(self, *, skip, limit, filters, viewer_member_id) -> PageResult:
        self.searches += 1
        return PageResult(items=[], total=0)


class FakeGroups:
    def __init__(self, groups: dict) -> None:
        self._groups = groups

    async def current_group_of(self, member_id) -> str | None:
        return self._groups.get(member_id)


class AllowingMeter:
    def __init__(self) -> None:
        self.charges = 0

    async def allow(self, key: str, *, rate_per_minute: int) -> bool:
        self.charges += 1
        return True


def profile(member_id: uuid.UUID, *, location: str) -> MemberProfile:
    return MemberProfile(
        id=member_id,
        slug=f"member-{member_id.hex[:6]}",
        name="Someone",
        class_label="Fall 2019",
        location=location,
        classes=[ClassRef(id=2, label="Fall 2019", year=2019)],
    )


def build_members_service(
    translator: CountingTranslator, *, meter: AllowingMeter | None = None
) -> tuple[AskService, FakeMembers]:
    members = FakeMembers(
        profile(VIEWER_ID, location="Munich"), profile(OTHER_ID, location="Berlin")
    )
    service = AskService(
        members,
        translator=translator,
        fallback=RulesTranslator(),
        meter=meter or AllowingMeter(),
        viewer_groups=FakeGroups({VIEWER_ID: "Venture Capital", OTHER_ID: "Consulting"}),
    )
    return service, members


# ---- the key itself ------------------------------------------------------------------------


def test_the_key_folds_case_and_whitespace_but_nothing_else() -> None:
    viewer = ViewerContext(class_label="Fall 2019")
    same = interpretation_key(
        board="members", question="  Who   is in VC? ", language=None, viewer=viewer
    )
    assert same == interpretation_key(
        board="members", question="who is in vc?", language=None, viewer=viewer
    )
    # A different board, language or viewer is a different question.
    assert same != interpretation_key(
        board="housing", question="who is in vc?", language=None, viewer=viewer
    )
    assert same != interpretation_key(
        board="members", question="who is in vc?", language="de", viewer=viewer
    )
    assert same != interpretation_key(
        board="members",
        question="who is in vc?",
        language=None,
        viewer=ViewerContext(class_label="Fall 2020"),
    )


def test_a_reading_made_yesterday_is_not_the_same_key_as_one_made_today() -> None:
    """A relative date means something different on the two sides of midnight.

    The prompts interpolate ``viewer.today``, so a key that ignored it would hand a stale
    reading of a relative date back for as long as the entry lived. The field is on the
    viewer, and the viewer goes into the key whole, so this holds as long as the services
    actually fill it in.
    """
    yesterday = ViewerContext(today=date(2026, 8, 23))
    today = ViewerContext(today=date(2026, 8, 24))
    unset = ViewerContext()

    key = interpretation_key(
        board="housing", question="a flat from next month", language=None, viewer=today
    )
    assert key != interpretation_key(
        board="housing", question="a flat from next month", language=None, viewer=yesterday
    )
    # And an unset date is its own reading rather than quietly sharing one of the above.
    assert key != interpretation_key(
        board="housing", question="a flat from next month", language=None, viewer=unset
    )


async def test_the_asks_put_todays_date_in_the_context_they_hand_the_translator() -> None:
    """Both services fill ``today`` in, which is what makes the key above cover it."""
    members_translator = RecordingViewerTranslator(AskInterpretation, MemberQuery)
    service, _ = build_members_service(members_translator)
    await service.explain("who is in VC", actor=Actor(VIEWER_ID))

    housing_translator = RecordingViewerTranslator(HousingAskInterpretation, HousingQuery)
    housing = HousingAskService(
        FakeHousing(),
        translator=housing_translator,
        fallback=CountingHousingTranslator(),
        meter=AllowingMeter(),
    )
    await housing.explain("a flat in Schwabing", actor=Actor(VIEWER_ID))

    assert members_translator.viewers[0].today == date.today()
    assert housing_translator.viewers[0].today == date.today()


# ---- the directory's Ask ---------------------------------------------------------------------


async def test_the_same_question_from_the_same_person_is_one_model_call() -> None:
    translator = CountingTranslator()
    service, members = build_members_service(translator)

    first = await service.explain("who is in VC", actor=Actor(VIEWER_ID))
    second = await service.explain("  Who is in VC  ", actor=Actor(VIEWER_ID))

    assert translator.calls == 1
    assert second.summary == first.summary

    # The search behind an answer is never cached: the directory changes under it.
    await service.ask("who is in VC", actor=Actor(VIEWER_ID), skip=0, limit=10)
    await service.ask("who is in VC", actor=Actor(VIEWER_ID), skip=0, limit=10)
    assert translator.calls == 1
    assert members.searches == 2


async def test_explain_and_ask_share_one_reading() -> None:
    """The preview a member types their way to is the reading their answer uses."""
    translator = CountingTranslator()
    service, _ = build_members_service(translator)

    await service.explain("founders in Berlin", actor=Actor(VIEWER_ID))
    await service.ask("founders in Berlin", actor=Actor(VIEWER_ID), skip=0, limit=10)

    assert translator.calls == 1


async def test_a_different_viewer_or_language_is_a_miss() -> None:
    translator = CountingTranslator()
    service, _ = build_members_service(translator)

    await service.explain("people from my class", actor=Actor(VIEWER_ID))
    # Same words, different asker: "my class" and "near me" resolve differently, so the
    # cached reading must not be handed over.
    await service.explain("people from my class", actor=Actor(OTHER_ID))
    assert translator.calls == 2

    # Same asker, different summary language.
    await service.explain("people from my class", actor=Actor(VIEWER_ID), language="de")
    assert translator.calls == 3
    # And the first key is still live.
    await service.explain("people from my class", actor=Actor(VIEWER_ID))
    assert translator.calls == 3


async def test_the_allowance_is_charged_even_on_a_hit() -> None:
    """The cache spares the provider, not the member's quota."""
    translator = CountingTranslator()
    meter = AllowingMeter()
    service, _ = build_members_service(translator, meter=meter)

    await service.explain("who is in VC", actor=Actor(VIEWER_ID))
    await service.explain("who is in VC", actor=Actor(VIEWER_ID))

    assert (translator.calls, meter.charges) == (1, 2)


async def test_a_keyword_answer_is_not_kept() -> None:
    """Otherwise "the model is down" would outlive the outage by ten minutes."""
    down = CountingTranslator(raises=LlmUnavailableError("down"))
    members = FakeMembers(profile(VIEWER_ID, location="Munich"))
    fallback = RulesTranslator()
    service = AskService(
        members,
        translator=down,
        fallback=fallback,
        meter=AllowingMeter(),
        viewer_groups=FakeGroups({}),
    )

    first = await service.explain("who is in VC", actor=Actor(VIEWER_ID))
    second = await service.explain("who is in VC", actor=Actor(VIEWER_ID))

    assert first.unresolved == [LLM_DOWN_NOTE] and second.unresolved == [LLM_DOWN_NOTE]
    # The provider was asked again, so a recovery is picked up on the next question.
    assert down.calls == 2
    assert fallback.calls == 2


async def test_clear_all_empties_it() -> None:
    """A loader run drops every cached read in the process, this one included."""
    translator = CountingTranslator()
    service, _ = build_members_service(translator)

    await service.explain("who is in VC", actor=Actor(VIEWER_ID))
    assert len(ask_service._INTERPRETATIONS) == 1

    clear_all()

    assert len(ask_service._INTERPRETATIONS) == 0
    await service.explain("who is in VC", actor=Actor(VIEWER_ID))
    assert translator.calls == 2


# ---- the housing Ask, same shape --------------------------------------------------------------


class CountingHousingTranslator:
    def __init__(self) -> None:
        self.model_name = "fake-model"
        self.calls = 0

    async def translate(
        self, question: str, *, viewer: ViewerContext, language: str | None = None
    ) -> HousingAskInterpretation:
        self.calls += 1
        return HousingAskInterpretation(
            summary=f"read: {question}",
            filters=HousingQuery(q=question),
            confidence=0.5,
            unresolved=[],
            source="llm",
        )


class FakeHousing:
    def __init__(self) -> None:
        self.lists = 0

    async def list(self, *, skip, limit, filters) -> PageResult:
        self.lists += 1
        return PageResult(items=[], total=0)


async def test_the_housing_ask_caches_its_reading_too() -> None:
    translator = CountingHousingTranslator()
    housing = FakeHousing()
    service = HousingAskService(
        housing,
        translator=translator,
        fallback=CountingHousingTranslator(),
        meter=AllowingMeter(),
    )

    await service.explain("a flat in Schwabing", actor=Actor(VIEWER_ID))
    await service.ask("A flat in Schwabing", actor=Actor(VIEWER_ID), skip=0, limit=10)
    await service.ask("a flat in schwabing", actor=Actor(VIEWER_ID), skip=0, limit=10)

    assert translator.calls == 1
    # The board itself is read fresh every time: a listing closes while the question is warm.
    assert housing.lists == 2

    await service.explain("a flat in Schwabing", actor=Actor(VIEWER_ID), language="de")
    assert translator.calls == 2

    clear_all()
    assert len(housing_ask_service._INTERPRETATIONS) == 0


async def test_a_caller_cannot_edit_the_reading_the_next_asker_gets() -> None:
    """An ``AskInterpretation`` is not frozen, so the cache hands out a copy."""
    translator = CountingTranslator()
    service, _ = build_members_service(translator)

    first = await service.explain("who is in VC", actor=Actor(VIEWER_ID))
    first.summary = "vandalised"
    first.filters.q = "vandalised"
    first.unresolved.append("vandalised")

    second = await service.explain("who is in VC", actor=Actor(VIEWER_ID))

    assert translator.calls == 1
    assert second.summary == "read: who is in VC"
    assert second.filters.q == "who is in VC"
    assert second.unresolved == []
