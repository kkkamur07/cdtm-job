"""The keyword translator for job board questions."""

from decimal import Decimal

import pytest

from backend.jobboard.domain import EmploymentType, ExperienceLevel, JobQuery, WorkArrangement
from backend.jobboard.infrastructure.ask_translator_rules import RulesJobTranslator, describe


async def ask(question: str) -> JobQuery:
    return (await RulesJobTranslator().translate(question)).filters


async def test_remote_roles_at_cdtm_startups() -> None:
    q = await ask("remote product roles at CDTM startups")
    assert q.remote_only is True
    assert q.work_arrangement == [WorkArrangement.REMOTE]
    assert q.is_cdtm_startup is True
    assert q.q == "product"


async def test_employment_type_and_city() -> None:
    q = await ask("working student positions in Munich")
    assert q.employment_type == [EmploymentType.WORKING_STUDENT]
    assert q.city == "Munich"


async def test_internship_is_both_a_type_and_a_level() -> None:
    q = await ask("internships in Berlin")
    assert q.employment_type == [EmploymentType.INTERNSHIP]
    assert q.experience_level == [ExperienceLevel.INTERN]


@pytest.mark.parametrize(
    ("question", "level"),
    [
        ("senior jobs", ExperienceLevel.SENIOR),
        ("junior jobs", ExperienceLevel.ENTRY),
        ("mid-level jobs", ExperienceLevel.MID),
        ("principal jobs", ExperienceLevel.LEAD),
    ],
)
async def test_experience_levels(question: str, level: ExperienceLevel) -> None:
    assert (await ask(question)).experience_level == [level]


async def test_country_is_recognised_separately_from_city() -> None:
    q = await ask("hybrid jobs in Germany")
    assert q.country == "Germany"
    assert q.city is None
    assert q.work_arrangement == [WorkArrangement.HYBRID]
    assert q.remote_only is None


async def test_salary_floor_with_thousands_suffix() -> None:
    assert (await ask("jobs paying over 80k")).salary_min == Decimal("80000")
    assert (await ask("jobs paying at least 65000")).salary_min == Decimal("65000")


async def test_recency_windows() -> None:
    assert (await ask("jobs posted this week")).posted_within_days == 7
    assert (await ask("new jobs")).posted_within_days == 30


async def test_company_by_name() -> None:
    assert (await ask("openings at Personio")).company == "Personio"


async def test_unmapped_phrases_are_reported() -> None:
    interpretation = await RulesJobTranslator().translate("something about the vibe")
    assert interpretation.filters.model_dump(exclude_none=True) == {}
    assert interpretation.unresolved == ["something about the vibe"]
    assert interpretation.source == "rules"


async def test_summary_and_confidence() -> None:
    interpretation = await RulesJobTranslator().translate("remote product roles at CDTM startups")
    assert "remote" in interpretation.summary.lower()
    assert 0.5 < interpretation.confidence <= 0.9


# ---- what the translator says it understood ---------------------------------------------


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("cdtm startups", {"is_cdtm_startup": True}),
        ("remote jobs", {"work_arrangement": [WorkArrangement.REMOTE], "remote_only": True}),
        ("full time jobs", {"employment_type": [EmploymentType.FULL_TIME]}),
        ("senior jobs", {"experience_level": [ExperienceLevel.SENIOR]}),
        ("jobs in Munich", {"city": "Munich"}),
        ("jobs in Germany", {"country": "Germany"}),
        ("jobs paying over 80k", {"salary_min": Decimal("80000")}),
        ("product roles", {"q": "product"}),
        ("openings at Personio", {"company": "Personio"}),
    ],
)
async def test_a_clause_the_rules_understood_is_not_also_reported_as_unresolved(
    question: str, expected: dict
) -> None:
    """A clause that filled a field is a clause we mapped, and the reply has to say so.

    ``unresolved`` is what the UI shows as "we could not use this part of your question",
    so a phrase that did fill a filter must not appear there, and the confidence that goes
    with one understood clause must count it.
    """
    interpretation = await RulesJobTranslator().translate(question)
    assert interpretation.filters.model_dump(exclude_none=True) == expected
    assert interpretation.unresolved == []
    assert interpretation.confidence == 0.6


async def test_a_question_the_rules_could_not_place_is_reported_with_the_lowest_confidence() -> (
    None
):
    interpretation = await RulesJobTranslator().translate("something about the vibe")
    assert interpretation.confidence == 0.5


async def test_every_clause_of_a_long_question_is_read_and_the_confidence_is_capped() -> None:
    """Five understood clauses is as sure as the keyword rules ever get."""
    interpretation = await RulesJobTranslator().translate(
        "senior remote full-time jobs in munich, in germany, paying over 80k, "
        "at cdtm startups, posted this week"
    )
    assert interpretation.filters.model_dump(exclude_none=True) == {
        "q": "posted this week",
        "employment_type": [EmploymentType.FULL_TIME],
        "work_arrangement": [WorkArrangement.REMOTE],
        "experience_level": [ExperienceLevel.SENIOR],
        "city": "Munich",
        "country": "Germany",
        "remote_only": True,
        "is_cdtm_startup": True,
        "salary_min": Decimal("80000"),
        "posted_within_days": 7,
    }
    assert interpretation.unresolved == ["posted this week"]
    assert interpretation.confidence == 0.9


async def test_a_role_of_several_words_keeps_its_words() -> None:
    assert (await ask("machine learning roles")).q == "machine learning"


async def test_a_role_that_is_only_filler_is_not_searched_for() -> None:
    """ "the new jobs" says when, not what: "the" is not a thing to search titles for."""
    interpretation = await RulesJobTranslator().translate("the new jobs")
    assert interpretation.filters.posted_within_days == 30
    # The whole clause is reported as unread rather than mined for a one-word query.
    assert interpretation.unresolved == ["the new jobs"]
    assert interpretation.filters.q == "the new jobs"


async def test_the_kind_of_work_wins_over_a_phrase_we_could_not_read() -> None:
    """A named role is what the member asked for; a leftover clause does not replace it."""
    interpretation = await RulesJobTranslator().translate("machine learning roles, quantum vibes")
    assert interpretation.filters.q == "machine learning"
    assert interpretation.unresolved == ["quantum vibes"]


# ---- the summary language ---------------------------------------------------------------


async def test_a_summary_language_the_rules_cannot_write_is_reported() -> None:
    interpretation = await RulesJobTranslator().translate("remote jobs", language="de")
    assert "summary language de" in interpretation.unresolved
    # The filters are unaffected by the asked-for language.
    assert interpretation.filters.remote_only is True


async def test_a_region_tagged_english_tag_is_the_language_the_summary_is_already_in() -> None:
    """ "en-GB" is English, so there is nothing to report; only the base tag counts."""
    interpretation = await RulesJobTranslator().translate("remote jobs", language="en-GB")
    assert interpretation.unresolved == []


async def test_a_region_tagged_other_language_is_still_reported() -> None:
    interpretation = await RulesJobTranslator().translate("remote jobs", language="de-DE")
    assert interpretation.unresolved == ["summary language de-DE"]


# ---- the chip sentence ------------------------------------------------------------------


def test_the_summary_names_every_filter_the_question_set() -> None:
    """The sentence above the results is the reader's only proof of what was searched."""
    summary = describe(
        JobQuery(
            experience_level=[ExperienceLevel.SENIOR, ExperienceLevel.LEAD],
            employment_type=[EmploymentType.FULL_TIME, EmploymentType.WORKING_STUDENT],
            q="product",
            remote_only=True,
            company="ACME",
            is_cdtm_startup=True,
            city="Munich",
            country="Germany",
            salary_min=Decimal("80000"),
            posted_within_days=7,
        )
    )
    assert summary == (
        "Jobs senior/lead, full time/working student, about 'product', fully remote, "
        "at ACME, at CDTM startups, in Munich, in Germany, paying at least 80000, "
        "posted in the last 7 days."
    )


def test_an_arrangement_that_is_not_remote_only_is_named_as_itself() -> None:
    query = JobQuery(work_arrangement=[WorkArrangement.HYBRID, WorkArrangement.ONSITE])
    assert describe(query) == "Jobs hybrid/onsite."


def test_a_question_with_no_filters_describes_the_whole_board() -> None:
    assert describe(JobQuery()) == "Every open job on the board."
