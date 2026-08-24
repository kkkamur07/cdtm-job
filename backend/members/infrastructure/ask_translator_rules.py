"""Keyword translation of a directory question, with no model involved.

This is the translator that runs when no provider is configured, when the provider is
down, and in every test. It is worse than a language model at unusual phrasings and better
than one at being predictable: the same sentence always produces the same filters, and it
cannot invent a school that nobody attended.

Anything it fails to consume is reported in ``unresolved`` rather than guessed at, which is
what lets the UI say "I did not understand 'in the AI space'" instead of quietly dropping
half the question.

The career and study group names are handed in rather than imported. They belong to the
Paths read model and this context has no vocabulary of its own for them, so a name that is
not in the vocabulary it was given is dropped: the filter degrades to something broader
instead of matching nothing, and ``tests/unit/test_ask_golden.py`` fails loudly if the two
lists ever drift apart.
"""

from __future__ import annotations

import re

from backend.core.llm.ask import RULES_SUMMARY_LANGUAGE, ViewerContext
from backend.core.llm.phrases import city_in, looks_like_a_name, normalise, split_clauses
from backend.members.domain import AskInterpretation, Intent, MemberQuery

#: Schools people name without saying "studied at". Canonical spelling on the right,
#: because it goes into an ILIKE and "Tum" would match "Tumor Biology".
SCHOOLS: dict[str, str] = {
    "stanford": "Stanford",
    "mit": "MIT",
    "berkeley": "Berkeley",
    "tum": "TUM",
    "technical university of munich": "Technical University of Munich",
    "lmu": "LMU",
    "eth": "ETH",
    "oxford": "Oxford",
    "cambridge": "Cambridge",
    "harvard": "Harvard",
    "columbia": "Columbia",
    "nus": "NUS",
    "hec": "HEC",
    "insead": "INSEAD",
    "kth": "KTH",
    "bocconi": "Bocconi",
}

#: Keywords to Paths group names, spelled exactly as ``backend/paths/domain`` spells them.
#: They are strings here because nothing in this context may import that enumeration; the
#: translator checks each one against the vocabulary it was given before using it.
CAREER_KEYWORDS: tuple[tuple[tuple[str, ...], str], ...] = (
    (
        ("vc", "venture capital", "venture", "investing in startups", "wagniskapital"),
        "Venture Capital",
    ),
    (("consulting", "consultant", "mckinsey", "bcg", "bain", "beratung"), "Consulting"),
    (
        (
            "founded",
            "founder",
            "co-founder",
            "cofounder",
            "started a company",
            "founding",
            "gruender",
            "gründer",
        ),
        "Founder",
    ),
    (("big tech", "google", "meta", "amazon", "microsoft", "apple"), "Big Tech"),
    (("research", "phd", "academia", "doctorate", "forschung"), "Research & Academia"),
    (("product", "engineering", "engineer"), "Product & Engineering"),
    (("corporate", "konzern"), "Corporate"),
    (("finance", "banking", "investment bank", "bank"), "Finance & Banking"),
    (("startup", "start-up"), "Startup"),
)

STUDY_KEYWORDS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("computer science", "informatics", "informatik", "cs"), "Computer Science"),
    (("business", "management", "economics", "bwl"), "Business & Management"),
    (("engineering", "mechanical", "electrical", "maschinenbau"), "Engineering"),
    (("physics", "math", "maths", "chemistry", "physik"), "Natural Sciences & Math"),
    (("medicine", "biology", "life sciences", "medizin"), "Medicine & Life Sciences"),
    (("law", "psychology", "design", "jura"), "Law & Social Sciences"),
)

INTENT_KEYWORDS: tuple[tuple[tuple[str, ...], Intent], ...] = (
    (("cofounder", "co-founder", "cofounding", "co-found", "mitgruender"), Intent.COFOUNDING),
    (("mentoring", "mentor", "mentorship"), Intent.MENTORING),
    (("hiring", "recruiting", "stellt ein"), Intent.HIRING),
    (
        ("open to roles", "looking for a job", "open to work", "job hunting", "jobsuche"),
        Intent.OPEN_TO_ROLES,
    ),
    (("speaking", "speaker", "talk at", "vortrag"), Intent.SPEAKING),
    (("investing", "angel", "invests", "investiert"), Intent.INVESTING),
)

_SCHOOL_EXPLICIT = re.compile(
    r"\b(?:studied at|study at|studying at|went to|graduated from|alumni of|alumnus of|"
    r"studiert an|studierte an)\s+"
    r"(?P<school>[a-zA-ZÀ-ÿ][\w'&.\- ]{1,60})$"
)
#: A bare "from X" is a school only when nothing else in the clause claimed it: "from my
#: class" is a cohort, "from Berlin" is a city, and both are matched before this one.
_SCHOOL_FROM = re.compile(r"^from\s+(?P<school>[a-zA-ZÀ-ÿ][\w'&.\- ]{1,60})$")
_STUDIED = re.compile(r"\b(?:studied|studying|study|degree in|major(?:ed)? in|read|studiert)\b")
_PAST_COMPANY = re.compile(
    r"\b(?:worked at|was at|used to work at|previously at|ex[- ]|war bei|frueher bei)"
    r"\s*(?P<company>[\w'&.\- ]{2,60})$"
)
_COMPANY = re.compile(
    r"\b(?:works at|work at|working at|now at|currently at|arbeitet bei|arbeiten bei|"
    r"ist bei|at|bei)\s+(?P<company>[\w'&.\- ]{2,60})$"
)
#: "at a big tech company" names a kind of employer, not an employer. Without this the
#: bare-"at" fallback would put the article and the adjective into an ILIKE and match
#: nobody, which reads as a broken search rather than a coarse one.
_ARTICLE_LED = re.compile(r"^(?:a|an|the|some|any|einer|einem|eine)\b", re.IGNORECASE)
_CLASS_OF = re.compile(r"\bclass of (?P<year>(?:19|20)\d{2})\b")
_SEASON_CLASS = re.compile(r"\b(?P<season>spring|fall|autumn) (?P<year>(?:19|20)\d{2})\b")
_SINCE_YEAR = re.compile(r"\b(?:since|after|from) (?P<year>(?:19|20)\d{2})\b")
_BEFORE_YEAR = re.compile(r"\b(?:before|until|up to) (?P<year>(?:19|20)\d{2})\b")
#: "class of 2019 or later" is an open range. Without these the year would pin both ends
#: and the answer would be one cohort, which is the opposite of what was asked.
_OR_LATER = re.compile(r"\b(?:or|and)\s+(?:later|after|newer|since)\b|\bonwards?\b")
_OR_EARLIER = re.compile(r"\b(?:or|and)\s+(?:earlier|before|older)\b")
_SPEAKS = re.compile(r"\bspeaks?\s+(?P<language>[a-zà-ÿ]{3,20})\b")
#: The skills phrase is pulled out of the whole question before it is cut into clauses,
#: because "skills in python, kubernetes" is one phrase with a comma in it and the clause
#: splitter would otherwise throw the second half away.
_SKILLS = re.compile(
    r"\b(?:skills? in|skilled in|good at|experience (?:in|with))\s+"
    r"(?P<skills>.+?)(?=\s+(?:who|that|and (?:are|is)|based|located|living)\b|$)"
)
#: A first step is only a first step when the question says so; otherwise a career group is
#: read as "where they are now", which is what people mean nine times out of ten.
_FIRST_STEP = re.compile(
    r"\b(?:first step|first job|first role|started out|straight after cdtm|right after cdtm)\b"
)
_MY_CLASS = re.compile(r"\b(?:my|our) (?:class|cohort|batch|year)\b")
_NEAR_ME = re.compile(r"\b(?:near me|in my city|around me|where i (?:am|live))\b")
#: Bare "ca" is left out on purpose: it is two letters that turn up inside ordinary
#: questions far more often than it means Center Assistant.
_CENTER_ASSISTANT = re.compile(r"\b(?:center assistants?|centre assistants?|cas)\b")

_STOP_CLAUSES = frozenset(
    {
        "",
        "a",
        "an",
        "the",
        "them",
        "someone",
        "somebody",
        "people",
        "members",
        "person",
        "now",
        "today",
        "currently",
        "later",
        "afterwards",
        "went",
        "then",
        "and",
        "ist",
        "sind",
        "die",
        "der",
    }
)


def _first(keywords: tuple[tuple[tuple[str, ...], object], ...], clause: str):
    # Word start, not whole word: "founders" and "engineers" are the same keyword as
    # "founder" and "engineer", which is how paths_classifier matches too.
    for needles, value in keywords:
        for needle in needles:
            if re.search(rf"\b{re.escape(needle)}", clause):
                return value
    return None


def _school_in(clause: str) -> str | None:
    # Longest first so "technical university of munich" wins over "tum" inside it.
    for spelling in sorted(SCHOOLS, key=len, reverse=True):
        if re.search(rf"\b{re.escape(spelling)}\b", clause):
            return SCHOOLS[spelling]
    return None


def _take_skills(text: str) -> tuple[str, list[str]]:
    """Pull a "skills in x, y" phrase out of the question, returning what is left of it."""
    match = _SKILLS.search(text)
    if match is None:
        return text, []
    skills = [s.strip() for s in re.split(r"[,/]| or | and ", match.group("skills")) if s.strip()]
    remainder = (text[: match.start()] + " " + text[match.end() :]).strip()
    return remainder, skills


def describe(query: MemberQuery) -> str:
    """A chip-friendly sentence saying what will be searched for."""
    bits: list[str] = []
    if query.study_group:
        bits.append(f"studied {query.study_group}")
    if query.school:
        bits.append(f"studied at {query.school}")
    if query.degree:
        bits.append(f"holding a degree in {query.degree}")
    if query.major:
        bits.append(f"CDTM major {query.major}")
    if query.first_step_group:
        bits.append(f"first step in {query.first_step_group}")
    if query.current_group:
        bits.append(f"now in {query.current_group}")
    if query.company:
        bits.append(f"at {query.company}")
    if query.past_company:
        bits.append(f"formerly at {query.past_company}")
    if query.title:
        bits.append(f"with the title {query.title}")
    if query.location:
        bits.append(f"in {query.location}")
    if query.class_label:
        bits.append(f"from the {query.class_label} class")
    if query.class_year_min and query.class_year_max:
        bits.append(f"from classes {query.class_year_min} to {query.class_year_max}")
    elif query.class_year_min:
        bits.append(f"from {query.class_year_min} onwards")
    elif query.class_year_max:
        bits.append(f"up to {query.class_year_max}")
    if query.intents:
        bits.append("open to " + " and ".join(i.value.replace("_", " ") for i in query.intents))
    if query.skills:
        bits.append("skilled in " + ", ".join(query.skills))
    if query.languages:
        bits.append("speaking " + ", ".join(query.languages))
    if query.roles:
        bits.append("roles: " + ", ".join(r.value for r in query.roles))
    if query.is_ca:
        bits.append("Center Assistants")
    if query.q:
        bits.append(f"matching {query.q!r}")
    if not bits:
        return "Everyone in the directory."
    return "Members " + ", ".join(bits) + "."


class RulesQueryTranslator:
    """Deterministic ``MemberQuery`` from keywords. Never raises on an odd question."""

    #: Reported in the ask log where the LLM translator reports its model.
    model_name = "-"

    def __init__(
        self,
        *,
        study_groups: tuple[str, ...],
        career_groups: tuple[str, ...],
    ) -> None:
        self._study_groups = frozenset(study_groups)
        self._career_groups = frozenset(career_groups)

    async def translate(
        self, question: str, *, viewer: ViewerContext, language: str | None = None
    ) -> AskInterpretation:
        # The summary is assembled from ``describe()``, which only speaks English. Saying
        # so in ``unresolved`` is more honest than machine-translating a chip.
        text = normalise(question)
        text, skills = _take_skills(text)
        values: dict[str, object] = {}
        intents: list[Intent] = []
        languages: list[str] = []
        unresolved: list[str] = []
        mapped = 1 if skills else 0

        for clause in split_clauses(text):
            if self._consume(clause, values, intents, languages, viewer):
                mapped += 1
            elif clause not in _STOP_CLAUSES:
                unresolved.append(clause)
                if looks_like_a_name(clause) and "q" not in values:
                    # Two or three plain words are almost always a person or a company, so
                    # they are worth a free-text pass; anything longer is a phrase we
                    # failed to parse and would only add noise to the haystack.
                    values["q"] = clause

        if intents:
            values["intents"] = intents
        if skills:
            values["skills"] = skills
        if languages:
            values["languages"] = languages

        if language and language.lower().split("-")[0] != RULES_SUMMARY_LANGUAGE:
            unresolved.append(f"summary language {language}")

        query = MemberQuery.model_validate(values)
        return AskInterpretation(
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
        intents: list[Intent],
        languages: list[str],
        viewer: ViewerContext,
    ) -> bool:
        """Apply every rule that fires on ``clause``; return whether any of them did."""
        hit = False
        studying = bool(_STUDIED.search(clause))
        # "my class" and "near me" are about the asker, so if the viewer context cannot
        # resolve them the clause is unresolved rather than fair game for the school and
        # company fallbacks, which would otherwise read "from my class" as a university.
        relative = bool(_MY_CLASS.search(clause) or _NEAR_ME.search(clause))

        if _MY_CLASS.search(clause) and viewer.class_label:
            values.setdefault("class_label", viewer.class_label)
            hit = True
        if _NEAR_ME.search(clause) and viewer.location:
            values.setdefault("location", viewer.location)
            hit = True

        hit = self._consume_years(clause, values) or hit

        school = _school_in(clause)
        if school is None:
            explicit = _SCHOOL_EXPLICIT.search(clause)
            school = explicit.group("school").strip().title() if explicit else None
        if school:
            values.setdefault("school", school)
            hit = True

        city = city_in(clause)
        if city:
            values.setdefault("location", city)
            hit = True

        if studying:
            group = _first(STUDY_KEYWORDS, clause)
            if group in self._study_groups:
                values.setdefault("study_group", group)
                hit = True
        else:
            group = _first(CAREER_KEYWORDS, clause)
            if group in self._career_groups:
                field = "first_step_group" if _FIRST_STEP.search(clause) else "current_group"
                values.setdefault(field, group)
                hit = True

        intent = _first(INTENT_KEYWORDS, clause)
        if intent is not None and intent not in intents:
            intents.append(intent)
            hit = True

        match = _SPEAKS.search(clause)
        if match:
            languages.append(match.group("language").title())
            hit = True

        match = _PAST_COMPANY.search(clause)
        if match:
            values.setdefault("past_company", match.group("company").strip().title())
            hit = True
        elif not (studying or school or relative):
            # "at <x>" is an employer unless the clause was about studying, which is what
            # keeps "studied at Stanford" from also becoming an employer. "from <x>" is a
            # school, but only when nothing else claimed the clause: "from my class" is a
            # cohort and "from Berlin" is a city, and both are matched before this.
            match = _SCHOOL_FROM.search(clause) if not hit else None
            if match:
                values.setdefault("school", match.group("school").strip().title())
                hit = True
            else:
                match = _COMPANY.search(clause)
                name = match.group("company").strip() if match else None
                if name and not _ARTICLE_LED.match(name):
                    values.setdefault("company", name.title())
                    hit = True

        if _CENTER_ASSISTANT.search(clause):
            values.setdefault("is_ca", True)
            hit = True

        if _FIRST_STEP.search(clause):
            hit = True
        return hit

    @staticmethod
    def _consume_years(clause: str, values: dict[str, object]) -> bool:
        """Class years, including the open ranges "2019 or later" and "before 2015"."""
        hit = False
        open_up = bool(_OR_LATER.search(clause))
        open_down = bool(_OR_EARLIER.search(clause))

        match = _CLASS_OF.search(clause)
        if match:
            year = int(match.group("year"))
            if not open_down:
                values.setdefault("class_year_min", year)
            if not open_up:
                values.setdefault("class_year_max", year)
            hit = True
        match = _SEASON_CLASS.search(clause)
        if match:
            season = "Fall" if match.group("season") in ("fall", "autumn") else "Spring"
            values.setdefault("class_label", f"{season} {match.group('year')}")
            hit = True
        match = _SINCE_YEAR.search(clause)
        if match and "class_year_min" not in values:
            values["class_year_min"] = int(match.group("year"))
            hit = True
        match = _BEFORE_YEAR.search(clause)
        if match and "class_year_max" not in values:
            values["class_year_max"] = int(match.group("year"))
            hit = True
        return hit
