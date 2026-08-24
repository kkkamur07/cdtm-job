"""Keyword translation of a housing question, with no model involved.

Housing questions are the most formulaic of the three boards: a kind, a place, a ceiling
and a date. That makes the keyword translator genuinely competitive here, which is why the
LLM is optional rather than assumed.
"""

from __future__ import annotations

import calendar
import re
from datetime import date

from backend.core.llm.ask import RULES_SUMMARY_LANGUAGE, ViewerContext
from backend.core.llm.phrases import CITIES, looks_like_a_name, normalise, split_clauses
from backend.housing.domain import HousingAskInterpretation, HousingKind, HousingQuery

#: The parts of Munich and Berlin people actually name in a housing post. Anything else
#: falls through to ``q``, which searches the area field as well as the text.
DISTRICTS: dict[str, str] = {
    "schwabing": "Schwabing",
    "maxvorstadt": "Maxvorstadt",
    "haidhausen": "Haidhausen",
    "sendling": "Sendling",
    "neuhausen": "Neuhausen",
    "giesing": "Giesing",
    "bogenhausen": "Bogenhausen",
    "laim": "Laim",
    "au": "Au",
    "kreuzberg": "Kreuzberg",
    "mitte": "Mitte",
    "neukölln": "Neukölln",
    "neukoelln": "Neukölln",
    "prenzlauer berg": "Prenzlauer Berg",
    "friedrichshain": "Friedrichshain",
    "wedding": "Wedding",
}

_MONTHS = {name.lower(): number for number, name in enumerate(calendar.month_name) if name}
_MONTHS |= {name.lower(): number for number, name in enumerate(calendar.month_abbr) if name}

_MAX_PRICE = re.compile(
    r"\b(?:under|below|max|maximum|at most|less than|up to|cheaper than)\s*"
    r"(?:eur|€)?\s*(?P<amount>\d{2,5})"
)
_MIN_PRICE = re.compile(
    r"\b(?:over|above|at least|more than|from)\s*(?:eur|€)?\s*(?P<amount>\d{2,5})\b"
)
_ROOMS = re.compile(r"\b(?P<rooms>\d(?:[.,]\d)?)[\s-]*(?:room|rooms|zimmer|bedroom|bedrooms)\b")
_FROM_MONTH = re.compile(r"\b(?:from|starting|as of|available from|ab)\s+(?P<month>[a-zà-ÿ]{3,9})")
_UNTIL_MONTH = re.compile(r"\b(?:until|till|through|to)\s+(?P<month>[a-zà-ÿ]{3,9})")
_OFFERING = re.compile(r"\b(?:offering|offer|offers|subletting|sublet|available|free from)\b")
_LOOKING = re.compile(r"\b(?:looking for|searching|search|wanted|needs?|i need|seeking)\b")
_HOME_WORD = re.compile(r"\b(?:room|rooms|flat|flats|apartment|apartments|wg|studio|zimmer)\b")
_FURNISHED = re.compile(r"\b(?:furnished|möbliert|moebliert)\b")
_UNFURNISHED = re.compile(r"\b(?:unfurnished|unmöbliert|empty)\b")

_STOP_CLAUSES = frozenset({"", "a", "an", "the", "room", "flat", "apartment", "wg", "place"})


def _month_start(month_name: str, today: date) -> date | None:
    month = _MONTHS.get(month_name)
    if month is None:
        return None
    # A month that has already passed this year means the next one: nobody looking in
    # November means last February.
    year = today.year if month >= today.month else today.year + 1
    return date(year, month, 1)


def _month_end(month_name: str, today: date) -> date | None:
    start = _month_start(month_name, today)
    if start is None:
        return None
    return date(start.year, start.month, calendar.monthrange(start.year, start.month)[1])


def _lookup(table: dict[str, str], clause: str) -> str | None:
    for spelling in sorted(table, key=len, reverse=True):
        if re.search(rf"\b{re.escape(spelling)}\b", clause):
            return table[spelling]
    return None


def describe(query: HousingQuery) -> str:
    """A chip-friendly sentence saying what will be searched for."""
    bits: list[str] = []
    if query.kind is HousingKind.OFFER:
        bits.append("rooms on offer")
    elif query.kind is HousingKind.LOOKING:
        bits.append("people looking for a room")
    else:
        bits.append("listings")
    if query.district:
        bits.append(f"in {query.district}")
    if query.city:
        bits.append(f"in {query.city}")
    if query.max_price and query.min_price:
        bits.append(f"between {query.min_price} and {query.max_price} euros")
    elif query.max_price:
        bits.append(f"under {query.max_price} euros")
    elif query.min_price:
        bits.append(f"over {query.min_price} euros")
    if query.min_rooms:
        bits.append(f"with at least {query.min_rooms:g} rooms")
    if query.furnished is True:
        bits.append("furnished")
    elif query.furnished is False:
        bits.append("unfurnished")
    if query.available_from:
        bits.append(f"free from {query.available_from.isoformat()}")
    if query.available_until:
        bits.append(f"still free on {query.available_until.isoformat()}")
    if query.q:
        bits.append(f"matching {query.q!r}")
    return "Housing: " + ", ".join(bits) + "."


class RulesHousingTranslator:
    model_name = "-"

    async def translate(
        self, question: str, *, viewer: ViewerContext, language: str | None = None
    ) -> HousingAskInterpretation:
        text = normalise(question)
        today = viewer.today or date.today()
        values: dict[str, object] = {}
        unresolved: list[str] = []
        mapped = 0

        if _LOOKING.search(text):
            values["kind"] = HousingKind.LOOKING
        elif _OFFERING.search(text) or _HOME_WORD.search(text):
            # Somebody typing "room in Schwabing" wants a room, not a flatmate; only the
            # explicit "looking for" wording flips the board around.
            values["kind"] = HousingKind.OFFER

        for clause in split_clauses(text):
            if self._consume(clause, values, today):
                mapped += 1
            elif clause not in _STOP_CLAUSES and not _HOME_WORD.fullmatch(clause):
                unresolved.append(clause)
                if looks_like_a_name(clause) and "q" not in values:
                    values["q"] = clause

        # ``describe()`` only speaks English, so an asked-for language is reported rather
        # than machine-translated. Same reasoning as the directory's keyword translator.
        if language and language.lower().split("-")[0] != RULES_SUMMARY_LANGUAGE:
            unresolved.append(f"summary language {language}")

        query = HousingQuery.model_validate(values)
        return HousingAskInterpretation(
            summary=describe(query),
            filters=query,
            confidence=min(0.9, 0.5 + 0.1 * mapped),
            unresolved=unresolved,
            source="rules",
        )

    def _consume(self, clause: str, values: dict[str, object], today: date) -> bool:
        hit = False

        match = _MAX_PRICE.search(clause)
        if match:
            values.setdefault("max_price", int(match.group("amount")))
            hit = True

        match = _ROOMS.search(clause)
        if match:
            values.setdefault("min_rooms", float(match.group("rooms").replace(",", ".")))
            hit = True

        match = _FROM_MONTH.search(clause)
        if match:
            start = _month_start(match.group("month"), today)
            if start is not None:
                values.setdefault("available_from", start)
                hit = True
        if not hit or "available_from" in values:
            # "from 900" is a floor on the rent; "from October" is a date. The date rule
            # runs first, so a surviving number here is money.
            match = _MIN_PRICE.search(clause)
            if match:
                values.setdefault("min_price", int(match.group("amount")))
                hit = True

        match = _UNTIL_MONTH.search(clause)
        if match:
            end = _month_end(match.group("month"), today)
            if end is not None:
                values.setdefault("available_until", end)
                hit = True

        district = _lookup(DISTRICTS, clause)
        if district:
            values.setdefault("district", district)
            hit = True
        city = _lookup(CITIES, clause)
        if city:
            values.setdefault("city", city)
            hit = True

        if _FURNISHED.search(clause):
            values.setdefault("furnished", True)
            hit = True
        elif _UNFURNISHED.search(clause):
            values.setdefault("furnished", False)
            hit = True

        if _OFFERING.search(clause) or _LOOKING.search(clause):
            hit = True
        return hit
