"""Keyword translator behaviours that only showed up once the golden-set test ids were ASCII.

Until then every mutant of this module was a false kill (see docs/mutation-testing.md), so
nothing had ever pinned "near me" or the longest-spelling rule for schools.
"""

from __future__ import annotations

from datetime import date

from backend.core.llm.ask import ViewerContext
from backend.members.infrastructure import ask_translator_rules
from backend.members.infrastructure.ask_translator_rules import RulesQueryTranslator
from backend.paths.domain import CAREER_GROUP_NAMES, STUDY_GROUP_NAMES

VIEWER = ViewerContext(
    class_label="Fall 2019", class_year=2019, location="Munich", today=date(2026, 8, 22)
)


def translator() -> RulesQueryTranslator:
    return RulesQueryTranslator(study_groups=STUDY_GROUP_NAMES, career_groups=CAREER_GROUP_NAMES)


async def test_near_me_is_the_askers_own_city() -> None:
    interpretation = await translator().translate("people near me", viewer=VIEWER)
    assert interpretation.filters.location == "Munich"
    # The clause was consumed by a rule, so it is neither echoed back as unread nor turned
    # into free text by the fallback at the end.
    assert interpretation.unresolved == []
    assert interpretation.filters.q is None


async def test_my_class_is_consumed_not_echoed_back() -> None:
    interpretation = await translator().translate("people from my class", viewer=VIEWER)
    assert interpretation.filters.class_label == "Fall 2019"
    assert interpretation.unresolved == []
    assert interpretation.filters.q is None


async def test_a_studied_subject_is_consumed_not_echoed_back() -> None:
    interpretation = await translator().translate(
        "people who studied computer science", viewer=VIEWER
    )
    assert interpretation.filters.study_group == "Computer Science"
    assert interpretation.unresolved == []
    assert interpretation.filters.q is None


async def test_near_me_is_reported_when_the_asker_has_no_city() -> None:
    # "people" is a lead-in, so the whole clause left over is "near me", and a clause no rule
    # consumed is reported rather than guessed at. ("founders near me" would be consumed by
    # the intent rule and the unread half would go unreported; that is the clause model.)
    nowhere = ViewerContext(class_label="Fall 2019", class_year=2019, today=date(2026, 8, 22))
    interpretation = await translator().translate("people near me", viewer=nowhere)
    assert interpretation.filters.location is None
    assert interpretation.unresolved == ["near me"]


async def test_the_longest_school_spelling_wins_over_a_shorter_one_inside_it(monkeypatch) -> None:
    # The shipped table has no spelling that is a whole phrase inside another, so the
    # longest-first order is only observable with one added.
    monkeypatch.setitem(ask_translator_rules.SCHOOLS, "university of munich", "LMU")
    long = await translator().translate(
        "who studied at technical university of munich", viewer=VIEWER
    )
    assert long.filters.school == "Technical University of Munich"
    short = await translator().translate("who studied at university of munich", viewer=VIEWER)
    assert short.filters.school == "LMU"
