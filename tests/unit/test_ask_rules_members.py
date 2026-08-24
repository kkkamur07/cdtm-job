"""The keyword translator for directory questions. No database, no network."""

from datetime import date

import pytest

from backend.core.llm.ask import ViewerContext
from backend.members.domain import Intent, MemberQuery
from backend.members.infrastructure.ask_translator_rules import RulesQueryTranslator
from backend.paths.domain import CAREER_GROUP_NAMES, STUDY_GROUP_NAMES, CareerGroup, StudyGroup

VIEWER = ViewerContext(
    class_label="Fall 2019", class_year=2019, location="Munich", today=date(2026, 8, 22)
)


def translator() -> RulesQueryTranslator:
    """The group names are injected, the way ``backend/members/api/deps.py`` injects them."""
    return RulesQueryTranslator(study_groups=STUDY_GROUP_NAMES, career_groups=CAREER_GROUP_NAMES)


async def ask(question: str, viewer: ViewerContext = VIEWER) -> MemberQuery:
    return (await translator().translate(question, viewer=viewer)).filters


async def test_school_then_career_group() -> None:
    q = await ask("who studied at Stanford and then went into VC")
    assert q.school == "Stanford"
    assert q.current_group == CareerGroup.VENTURE_CAPITAL
    assert q.study_group is None


async def test_bare_school_name_is_recognised() -> None:
    assert (await ask("TUM alumni in product")).school == "TUM"


async def test_unknown_school_after_studied_at() -> None:
    assert (await ask("people who studied at Rice University")).school == "Rice University"


async def test_my_class_resolves_from_the_viewer() -> None:
    q = await ask("people from my class who founded something in Berlin")
    assert q.class_label == "Fall 2019"
    assert q.location == "Berlin"
    assert q.current_group == CareerGroup.FOUNDER


async def test_my_class_is_unresolved_without_a_viewer() -> None:
    interpretation = await translator().translate("people from my class", viewer=ViewerContext())
    assert interpretation.filters.class_label is None
    assert interpretation.unresolved == ["from my class"]


async def test_class_of_a_year_becomes_a_year_range() -> None:
    q = await ask("class of 2019 in consulting")
    assert (q.class_year_min, q.class_year_max) == (2019, 2019)
    assert q.current_group == CareerGroup.CONSULTING


async def test_season_and_year_become_a_class_label() -> None:
    assert (await ask("spring 2021 founders")).class_label == "Spring 2021"


async def test_studied_field_maps_to_a_study_group() -> None:
    q = await ask("people who studied computer science and are now in big tech")
    assert q.study_group == StudyGroup.COMPUTER_SCIENCE
    assert q.current_group == CareerGroup.BIG_TECH


@pytest.mark.parametrize(
    ("question", "group"),
    [
        ("anyone in consulting", CareerGroup.CONSULTING),
        ("who is doing a phd", CareerGroup.RESEARCH_ACADEMIA),
        ("people in banking", CareerGroup.FINANCE_BANKING),
        ("members in corporate", CareerGroup.CORPORATE),
        ("engineers", CareerGroup.PRODUCT_ENGINEERING),
    ],
)
async def test_career_keywords(question: str, group: CareerGroup) -> None:
    assert (await ask(question)).current_group == group


async def test_first_step_wording_targets_the_first_step() -> None:
    q = await ask("people whose first job was in consulting")
    assert q.first_step_group == CareerGroup.CONSULTING
    assert q.current_group is None


async def test_intents_are_collected() -> None:
    q = await ask("members open to mentoring who worked at McKinsey")
    assert q.intents == [Intent.MENTORING]
    assert q.past_company == "Mckinsey"


async def test_skills_survive_the_comma_split() -> None:
    q = await ask("someone with skills in python, kubernetes who is in Berlin")
    assert q.skills == ["python", "kubernetes"]
    assert q.location == "Berlin"


async def test_language_and_center_assistant() -> None:
    assert (await ask("anyone speaks french")).languages == ["French"]
    assert (await ask("Center Assistants in Munich")).is_ca is True


async def test_city_spellings_are_canonical() -> None:
    assert (await ask("people in München")).location == "Munich"
    assert (await ask("people in Zürich")).location == "Zurich"


async def test_unmapped_phrases_are_reported_not_guessed() -> None:
    interpretation = await translator().translate("in the AI space", viewer=VIEWER)
    assert interpretation.filters.model_dump(exclude_none=True) == {}
    assert interpretation.unresolved == ["in the ai space"]
    assert interpretation.source == "rules"


async def test_a_bare_name_becomes_free_text() -> None:
    assert (await ask("Anna Test")).q == "anna test"


async def test_confidence_grows_with_mapped_clauses_and_is_capped() -> None:
    plain = await translator().translate("in the AI space", viewer=VIEWER)
    rich = await translator().translate(
        "studied at Stanford and then went into VC in Berlin", viewer=VIEWER
    )
    assert plain.confidence == pytest.approx(0.5)
    assert rich.confidence > plain.confidence
    assert rich.confidence <= 0.9


async def test_summary_is_a_sentence_about_the_filters() -> None:
    interpretation = await translator().translate(
        "who studied at Stanford and then went into VC", viewer=VIEWER
    )
    assert interpretation.summary == "Members studied at Stanford, now in Venture Capital."


async def test_a_group_name_the_paths_context_does_not_have_is_dropped() -> None:
    """The vocabulary is data, so a keyword table that drifts degrades rather than lies."""
    narrow = RulesQueryTranslator(study_groups=(), career_groups=("Consulting",))
    q = (await narrow.translate("founders in Berlin", viewer=VIEWER)).filters
    assert q.current_group is None
    assert q.location == "Berlin"


async def test_german_question_reads_city_company_and_intent() -> None:
    q = await ask("Wer in Muenchen arbeitet bei BMW und ist offen fuer Mentoring?")
    assert q.location == "Munich"
    assert q.company == "Bmw"
    assert q.intents == [Intent.MENTORING]


async def test_or_later_leaves_the_range_open_at_the_top() -> None:
    q = await ask("class of 2019 or later, open to speaking")
    assert (q.class_year_min, q.class_year_max) == (2019, None)
    assert q.intents == [Intent.SPEAKING]


async def test_a_kind_of_employer_is_not_read_as_an_employer() -> None:
    # "at a big tech company" names a category; putting it in an ILIKE would match nobody.
    q = await ask("who went from engineering into product management at a big tech company?")
    assert q.company is None
    assert q.current_group == CareerGroup.BIG_TECH
