"""Keyword translation of a job question, with no model involved.

Runs whenever no provider is configured, whenever the provider is down, and in every test.
Job questions are mostly enumerations (employment type, arrangement, seniority), which is
exactly what keywords are good at; the free-text part is what the model earns its keep on.
"""

from __future__ import annotations

import re
from decimal import Decimal

from backend.core.llm.ask import RULES_SUMMARY_LANGUAGE
from backend.core.llm.phrases import looks_like_a_name, normalise, split_clauses
from backend.jobboard.domain import (
    EmploymentType,
    ExperienceLevel,
    JobAskInterpretation,
    JobQuery,
    WorkArrangement,
)

EMPLOYMENT_KEYWORDS: tuple[tuple[tuple[str, ...], EmploymentType], ...] = (
    (("working student", "werkstudent"), EmploymentType.WORKING_STUDENT),
    (("internship", "intern", "praktikum"), EmploymentType.INTERNSHIP),
    (("part time", "part-time", "teilzeit"), EmploymentType.PART_TIME),
    (("full time", "full-time", "vollzeit", "permanent"), EmploymentType.FULL_TIME),
    (("freelance", "freelancer", "contractor"), EmploymentType.FREELANCE),
    (("contract",), EmploymentType.CONTRACT),
    (
        (
            "temporary",
            "temp",
        ),
        EmploymentType.TEMPORARY,
    ),
)

ARRANGEMENT_KEYWORDS: tuple[tuple[tuple[str, ...], WorkArrangement], ...] = (
    (("remote", "work from home", "wfh"), WorkArrangement.REMOTE),
    (("hybrid",), WorkArrangement.HYBRID),
    (("onsite", "on-site", "on site", "in office", "in the office"), WorkArrangement.ONSITE),
)

LEVEL_KEYWORDS: tuple[tuple[tuple[str, ...], ExperienceLevel], ...] = (
    (("intern",), ExperienceLevel.INTERN),
    (("entry level", "entry-level", "junior", "graduate", "new grad"), ExperienceLevel.ENTRY),
    (("mid level", "mid-level", "midlevel"), ExperienceLevel.MID),
    (("senior", "sr."), ExperienceLevel.SENIOR),
    (("lead", "principal", "staff engineer", "head of", "director"), ExperienceLevel.LEAD),
)

#: Cities the board actually posts in. The job board keeps its own list rather than
#: borrowing Community's: the two contexts do not share vocabulary, and a job's city comes
#: from a posting form, not from a scraped profile.
CITIES: dict[str, str] = {
    "munich": "Munich",
    "münchen": "Munich",
    "muenchen": "Munich",
    "berlin": "Berlin",
    "hamburg": "Hamburg",
    "london": "London",
    "paris": "Paris",
    "zurich": "Zurich",
    "zürich": "Zurich",
    "amsterdam": "Amsterdam",
    "vienna": "Vienna",
    "new york": "New York",
    "san francisco": "San Francisco",
    "singapore": "Singapore",
}

COUNTRIES: dict[str, str] = {
    "germany": "Germany",
    "deutschland": "Germany",
    "switzerland": "Switzerland",
    "austria": "Austria",
    "netherlands": "Netherlands",
    "france": "France",
    "uk": "United Kingdom",
    "united kingdom": "United Kingdom",
    "usa": "United States",
    "united states": "United States",
    "singapore": "Singapore",
}

_CDTM_STARTUP = re.compile(r"\b(?:cdtm startups?|cdtm compan(?:y|ies)|founded by cdtm)\b")
_COMPANY = re.compile(r"\bat\s+(?P<company>[\w'&.\- ]{2,60})$")
_SALARY = re.compile(
    r"\b(?:over|above|at least|paying|more than|from)\s*(?:eur|€|\$)?\s*"
    r"(?P<amount>\d{2,7})\s*(?P<thousands>k)?\b"
)
_ROLE = re.compile(
    r"(?P<role>[\w+#/&.\- ]{3,60}?)\s+(?:roles?|jobs?|positions?|openings?|vacanc(?:y|ies))\b"
)
_RECENT = (
    (re.compile(r"\b(?:today|since yesterday)\b"), 1),
    (re.compile(r"\b(?:this week|last week|past week|last 7 days)\b"), 7),
    (re.compile(r"\b(?:this month|last month|past month|last 30 days)\b"), 30),
    (re.compile(r"\b(?:recent|recently|new)\b"), 30),
)

_NOISE_WORDS = frozenset(
    {"", "a", "an", "the", "job", "jobs", "role", "roles", "position", "positions", "any"}
)


def _first(keywords: tuple[tuple[tuple[str, ...], object], ...], clause: str):
    for needles, value in keywords:
        for needle in needles:
            if re.search(rf"\b{re.escape(needle)}", clause):
                return value
    return None


def _lookup(table: dict[str, str], clause: str) -> str | None:
    for spelling in sorted(table, key=len, reverse=True):
        if re.search(rf"\b{re.escape(spelling)}\b", clause):
            return table[spelling]
    return None


#: Words that describe how a job is worked rather than what it is. They are already
#: captured as enumerations, so leaving them in the free-text query would only make it
#: match fewer postings than it should.
_ROLE_NOISE = frozenset(
    {
        "remote",
        "hybrid",
        "onsite",
        "on-site",
        "senior",
        "junior",
        "entry",
        "entry-level",
        "graduate",
        "lead",
        "principal",
        "intern",
        "internship",
        "working",
        "student",
        "full",
        "part",
        "time",
        "full-time",
        "part-time",
        "freelance",
        "cdtm",
        "new",
        "open",
        "available",
    }
)


def _clean_role(role: str) -> str:
    return " ".join(w for w in role.split() if w not in _ROLE_NOISE)


def describe(query: JobQuery) -> str:
    """A chip-friendly sentence saying what will be searched for."""
    bits: list[str] = []
    if query.experience_level:
        bits.append("/".join(x.value for x in query.experience_level))
    if query.employment_type:
        bits.append("/".join(e.value.replace("_", " ") for e in query.employment_type))
    if query.q:
        bits.append(f"about {query.q!r}")
    if query.remote_only:
        bits.append("fully remote")
    elif query.work_arrangement:
        bits.append("/".join(w.value for w in query.work_arrangement))
    if query.company:
        bits.append(f"at {query.company}")
    if query.is_cdtm_startup:
        bits.append("at CDTM startups")
    if query.city:
        bits.append(f"in {query.city}")
    if query.country:
        bits.append(f"in {query.country}")
    if query.salary_min:
        bits.append(f"paying at least {query.salary_min:g}")
    if query.posted_within_days:
        bits.append(f"posted in the last {query.posted_within_days} days")
    if not bits:
        return "Every open job on the board."
    return "Jobs " + ", ".join(bits) + "."


class RulesJobTranslator:
    #: Reported in the ask log where the LLM translator reports its model.
    model_name = "-"

    async def translate(
        self, question: str, *, language: str | None = None
    ) -> JobAskInterpretation:
        text = normalise(question)
        values: dict[str, object] = {}
        employment: list[EmploymentType] = []
        arrangements: list[WorkArrangement] = []
        levels: list[ExperienceLevel] = []
        unresolved: list[str] = []
        mapped = 0

        for pattern, days in _RECENT:
            if pattern.search(text):
                values["posted_within_days"] = days
                mapped += 1
                break

        for clause in split_clauses(text):
            if self._consume(clause, values, employment, arrangements, levels):
                mapped += 1
            elif clause not in _NOISE_WORDS:
                unresolved.append(clause)
                if looks_like_a_name(clause) and "q" not in values:
                    values["q"] = clause

        if employment:
            values["employment_type"] = employment
        if arrangements:
            values["work_arrangement"] = arrangements
        if levels:
            values["experience_level"] = levels

        # ``describe()`` only speaks English, so an asked-for language is reported rather
        # than machine-translated. Same reasoning as the other two boards' keyword rules.
        if language and language.lower().split("-")[0] != RULES_SUMMARY_LANGUAGE:
            unresolved.append(f"summary language {language}")

        query = JobQuery.model_validate(values)
        return JobAskInterpretation(
            summary=describe(query),
            filters=query,
            confidence=min(0.9, 0.5 + 0.1 * mapped),
            unresolved=unresolved,
            source="rules",
        )

    def _consume(
        self,
        clause: str,
        values: dict[str, object],
        employment: list[EmploymentType],
        arrangements: list[WorkArrangement],
        levels: list[ExperienceLevel],
    ) -> bool:
        hit = False

        if _CDTM_STARTUP.search(clause):
            values.setdefault("is_cdtm_startup", True)
            hit = True

        arrangement = _first(ARRANGEMENT_KEYWORDS, clause)
        if arrangement is not None and arrangement not in arrangements:
            arrangements.append(arrangement)
            if arrangement is WorkArrangement.REMOTE:
                # "remote" in a question means "do not show me the office ones", which is
                # a stronger statement than "remote is acceptable".
                values.setdefault("remote_only", True)
            hit = True

        kind = _first(EMPLOYMENT_KEYWORDS, clause)
        if kind is not None and kind not in employment:
            employment.append(kind)
            hit = True

        level = _first(LEVEL_KEYWORDS, clause)
        if level is not None and level not in levels:
            levels.append(level)
            hit = True

        city = _lookup(CITIES, clause)
        if city:
            values.setdefault("city", city)
            hit = True
        country = _lookup(COUNTRIES, clause)
        if country and country != city:
            values.setdefault("country", country)
            hit = True

        match = _SALARY.search(clause)
        if match:
            amount = Decimal(match.group("amount"))
            values.setdefault("salary_min", amount * 1000 if match.group("thousands") else amount)
            hit = True

        match = _ROLE.search(clause)
        if match:
            role = _clean_role(match.group("role").strip())
            if role and role not in _NOISE_WORDS:
                values.setdefault("q", role)
                hit = True

        if not hit:
            match = _COMPANY.search(clause)
            if match:
                values.setdefault("company", match.group("company").strip().title())
                hit = True
        return hit
