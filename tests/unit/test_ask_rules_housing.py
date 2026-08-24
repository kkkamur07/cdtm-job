"""The keyword translator for housing questions."""

from datetime import date

from backend.core.llm.ask import ViewerContext
from backend.housing.domain import HousingKind, HousingQuery
from backend.housing.infrastructure.housing_ask_translator_rules import RulesHousingTranslator

VIEWER = ViewerContext(today=date(2026, 8, 22))


async def ask(question: str) -> HousingQuery:
    return (await RulesHousingTranslator().translate(question, viewer=VIEWER)).filters


async def test_room_in_a_district_under_a_price_from_a_month() -> None:
    q = await ask("room in Schwabing under 900 from October")
    assert q.kind is HousingKind.OFFER
    assert q.district == "Schwabing"
    assert q.max_price == 900
    assert q.available_from == date(2026, 10, 1)


async def test_looking_for_flips_the_kind() -> None:
    q = await ask("looking for a 2 room flat in Berlin")
    assert q.kind is HousingKind.LOOKING
    assert q.city == "Berlin"
    assert q.min_rooms == 2


async def test_a_month_already_past_means_next_year() -> None:
    assert (await ask("room from February")).available_from == date(2027, 2, 1)


async def test_until_a_month_is_the_end_of_it() -> None:
    assert (await ask("room until December")).available_until == date(2026, 12, 31)


async def test_furnished_and_unfurnished() -> None:
    assert (await ask("furnished apartment in Munich")).furnished is True
    assert (await ask("unfurnished apartment in Munich")).furnished is False


async def test_minimum_price_is_not_confused_with_a_month() -> None:
    q = await ask("flat over 1200 in Zurich")
    assert q.min_price == 1200
    assert q.available_from is None


async def test_offering_wording() -> None:
    q = await ask("offering a room in Kreuzberg from September")
    assert q.kind is HousingKind.OFFER
    assert q.district == "Kreuzberg"
    assert q.available_from == date(2026, 9, 1)


async def test_a_bare_home_word_still_asks_for_offers() -> None:
    assert (await ask("wg in maxvorstadt")).kind is HousingKind.OFFER


async def test_unmapped_phrase_is_reported() -> None:
    interpretation = await RulesHousingTranslator().translate(
        "somewhere quiet with good vibes", viewer=VIEWER
    )
    assert interpretation.unresolved
    assert interpretation.source == "rules"


async def test_summary_reads_as_a_sentence() -> None:
    interpretation = await RulesHousingTranslator().translate(
        "room in Schwabing under 900", viewer=VIEWER
    )
    assert interpretation.summary.startswith("Housing: rooms on offer")
