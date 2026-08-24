"""The keyword translator, read clause by clause.

The companion of ``test_ask_rules_housing.py``: that file checks the filters a question
becomes, this one checks the three things a member sees around them -- the summary
sentence, how sure the reading claims to be, and which phrases are handed back as
unresolved. Every rule in ``_consume`` is worth exactly one clause, so a rule that stops
counting shows up here as a lower confidence and a phrase in ``unresolved``.
"""

from datetime import date

import pytest

from backend.core.llm.ask import ViewerContext
from backend.housing.domain import HousingAskInterpretation, HousingKind
from backend.housing.infrastructure.housing_ask_translator_rules import RulesHousingTranslator

#: A fixed "today" so a month name resolves to the same date whenever the suite runs.
VIEWER = ViewerContext(today=date(2026, 8, 22))
#: Far enough away that no real calendar day can be mistaken for it.
DISTANT_VIEWER = ViewerContext(today=date(2030, 3, 15))


async def read(question: str, **kw) -> HousingAskInterpretation:
    return await RulesHousingTranslator().translate(question, viewer=VIEWER, **kw)


# ---- one clause, one rule, one point of confidence -----------------------------------------


@pytest.mark.parametrize(
    "question",
    [
        "under 900",
        "over 1200",
        "2 rooms",
        "from October",
        "until December",
        "in Schwabing",
        "in Munich",
        "furnished",
        "unfurnished",
        "offering",
        "looking for",
    ],
)
async def test_a_clause_a_rule_understands_is_not_reported_back_as_unresolved(
    question: str,
) -> None:
    """Each rule in ``_consume`` claims its clause: nothing is left over, and the reading is
    one step surer than a question nothing matched."""
    interpretation = await read(question)
    assert interpretation.unresolved == []
    assert interpretation.confidence == 0.6


async def test_confidence_grows_with_every_clause_that_was_understood() -> None:
    assert (await read("somewhere quiet with good vibes")).confidence == 0.5
    assert (await read("under 900")).confidence == 0.6
    assert (await read("under 900, in Munich")).confidence == 0.7


async def test_confidence_stops_at_nine_tenths_however_much_was_understood() -> None:
    """Keywords are never certain: six understood clauses still leave room for doubt."""
    interpretation = await read(
        "offering a furnished 2 room flat in Schwabing, Munich, over 500, under 900, "
        "from October, until December"
    )
    assert interpretation.confidence == 0.9
    assert interpretation.unresolved == []


async def test_a_word_that_carries_no_filter_is_not_reported_as_unresolved() -> None:
    """ "place", "a" and "the" are noise a member types, not something the board failed to
    understand, so they never reach ``unresolved``."""
    interpretation = await read("any place, 2 rooms in Schwabing")
    assert interpretation.unresolved == []
    assert interpretation.filters.min_rooms == 2


# ---- the summary sentence ------------------------------------------------------------------


async def test_the_summary_names_the_board_when_the_question_names_no_side() -> None:
    assert (await read("under 900")).summary == "Housing: listings, under 900 euros."


async def test_the_summary_says_which_side_of_the_board_is_being_searched() -> None:
    assert (await read("offering")).summary == "Housing: rooms on offer."
    assert (await read("looking for")).summary == "Housing: people looking for a room."


async def test_a_floor_and_a_ceiling_are_summarised_as_one_range() -> None:
    interpretation = await read("flat over 500, under 900")
    assert interpretation.summary == "Housing: rooms on offer, between 500 and 900 euros."
    assert (interpretation.filters.min_price, interpretation.filters.max_price) == (500, 900)


async def test_furnished_and_unfurnished_are_summarised_apart() -> None:
    assert (await read("furnished")).summary == "Housing: listings, furnished."
    assert (await read("unfurnished")).summary == "Housing: listings, unfurnished."


async def test_the_summary_reads_as_one_sentence_with_every_clause_in_it() -> None:
    interpretation = await read(
        "offering a furnished 2 room flat in Schwabing, Munich, over 500, under 900, "
        "from October, until December"
    )
    assert interpretation.summary == (
        "Housing: rooms on offer, in Schwabing, in Munich, between 500 and 900 euros, "
        "with at least 2 rooms, furnished, free from 2026-10-01, still free on 2026-12-31."
    )


# ---- places, months and money --------------------------------------------------------------


async def test_the_longer_more_specific_district_wins() -> None:
    """ "Au" and "Haidhausen" are both districts and both spelled inside "Au-Haidhausen";
    the longest spelling is tried first so the more specific one is what gets filtered on."""
    assert (await read("room in Au-Haidhausen")).filters.district == "Haidhausen"


async def test_the_month_being_asked_about_now_means_this_year() -> None:
    """Asked in August, "from August" is this August, not the next one."""
    assert (await read("room from August")).filters.available_from == date(2026, 8, 1)


async def test_the_month_is_read_against_the_askers_today_and_not_the_servers() -> None:
    interpretation = await RulesHousingTranslator().translate(
        "room from June", viewer=DISTANT_VIEWER
    )
    assert interpretation.filters.available_from == date(2030, 6, 1)


async def test_a_month_and_a_floor_price_in_one_clause_are_both_read() -> None:
    """ "from October" is a date and "over 900" is money, in the same breath."""
    filters = (await read("room from october over 900")).filters
    assert filters.available_from == date(2026, 10, 1)
    assert filters.min_price == 900


async def test_a_number_of_rooms_with_a_decimal_point() -> None:
    assert (await read("2.5 zimmer in Schwabing")).filters.min_rooms == 2.5


# ---- free text and unresolved phrases -------------------------------------------------------


async def test_only_the_first_unrecognised_name_becomes_the_free_text_search() -> None:
    """Two names cannot both be the search term; the first one is kept and the second is
    still reported so the member can see it was not used."""
    interpretation = await read("anna weber haus and sophie mueller hof")
    assert interpretation.filters.q == "anna weber haus"
    assert interpretation.unresolved == ["anna weber haus", "sophie mueller hof"]


async def test_a_name_the_board_does_not_know_becomes_the_free_text_search() -> None:
    interpretation = await read("flat, alte heide")
    assert interpretation.filters.q == "alte heide"
    assert interpretation.filters.kind is HousingKind.OFFER


# ---- the language of the summary -------------------------------------------------------------


async def test_a_summary_language_the_keywords_cannot_write_is_reported() -> None:
    interpretation = await read("room in Schwabing", language="de")
    assert "summary language de" in interpretation.unresolved
    assert interpretation.filters.district == "Schwabing"


async def test_english_is_the_language_the_keywords_already_write_in() -> None:
    """A regional tag and a capitalised tag are both English, and neither is a complaint."""
    for tag in ("en", "EN-GB", "en-gb"):
        assert (await read("room in Schwabing", language=tag)).unresolved == []
