"""Text helpers the keyword translators share.

Small, boring and deterministic on purpose: this is the code path that has to keep working
when there is no API key, no credit, or no network.
"""

from __future__ import annotations

import re

#: Words a question opens with that carry no filter ("show me people who ...", "wer ...").
_LEAD_IN = re.compile(
    r"^(?:please\s+)?(?:can you\s+|could you\s+)?"
    r"(?:show me|show|find me|find|list|give me|get me|search for|search|who are|who is|who|"
    r"any|anyone|anybody|somebody|someone|people|members|alumni|folks|is there|are there|"
    r"zeig mir|zeige mir|gibt es|wer|welche|jemand)\b",
    re.IGNORECASE,
)
#: German "und" and "der/die/das" clause openers are here for the same reason "and" is: a
#: sizeable share of the questions members type are German, and without them a whole
#: sentence arrives at the company rule as one clause and lands in an ILIKE.
_CLAUSE_SPLIT = re.compile(
    r",|\bwho\b|\band then\b|\bthen\b|\band\b|\bwith\b|;|\bund\b|\bdie\b|\bder\b"
)
_WORD = re.compile(r"^[a-zA-ZÀ-ÿ][a-zA-ZÀ-ÿ'’.-]*$")

#: Canonical spellings so "München" and "Munich" are one filter. Shared because a place
#: name is not a board's word: the directory and the housing board have to agree on it or
#: the same question means two things depending on which box it is typed into.
CITIES: dict[str, str] = {
    "berlin": "Berlin",
    "munich": "Munich",
    "münchen": "Munich",
    "muenchen": "Munich",
    "london": "London",
    "zurich": "Zurich",
    "zürich": "Zurich",
    "paris": "Paris",
    "new york": "New York",
    "san francisco": "San Francisco",
    "bay area": "Bay Area",
    "singapore": "Singapore",
    "amsterdam": "Amsterdam",
    "vienna": "Vienna",
    "hamburg": "Hamburg",
}


def city_in(clause: str) -> str | None:
    """The canonical spelling of the first city named in ``clause``, if any."""
    # Longest first so "new york" wins over a shorter spelling inside it.
    for spelling in sorted(CITIES, key=len, reverse=True):
        if re.search(rf"\b{re.escape(spelling)}\b", clause):
            return CITIES[spelling]
    return None


def normalise(question: str) -> str:
    """Lower-case, collapse whitespace, drop the lead-in and a trailing question mark."""
    text = " ".join(question.strip().split()).rstrip("?").strip()
    previous = None
    while previous != text:
        previous = text
        text = _LEAD_IN.sub("", text, count=1).strip()
    return text.lower()


def split_clauses(question: str) -> list[str]:
    """Cut a question into the phrases a rule can be tried against."""
    parts = (p.strip(" .") for p in _CLAUSE_SPLIT.split(question))
    return [p for p in parts if p]


def looks_like_a_name(text: str) -> bool:
    """Two or three plain words: a person or a company, not a half-parsed instruction."""
    words = text.split()
    return 2 <= len(words) <= 3 and all(_WORD.match(w) for w in words)
