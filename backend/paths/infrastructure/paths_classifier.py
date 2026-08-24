"""Heuristic classification of a member's path into coarse groups.

Pure functions, no I/O. Kept in infrastructure because it encodes how *our* scraped
data looks (LinkedIn titles, CDTM class dates), not a domain rule.

It reads a ``CareerHistory``, not a member. That is the whole of what this context is
given about a person: four fields of a job and two of a degree, read out of the member
tables by ``CareerHistorySource``. A rule cannot start depending on a field it was never
handed, and nothing here needs to know that a Member exists.
"""

from __future__ import annotations

import re
from datetime import date

from backend.paths.domain import CareerHistory, MemberPath, StudyEntry, WorkEntry

STUDY_GROUPS: dict[str, tuple[str, ...]] = {
    "Business & Management": (
        "management",
        "business",
        "bwl",
        "economics",
        "finance",
        "tum-bwl",
        "marketing",
        "accounting",
        "entrepreneur",
        "mba",
    ),
    "Computer Science": (
        "computer science",
        "informatic",
        "informatik",
        "information systems",
        "wirtschaftsinformatik",
        "information technology",
        "software",
        "data science",
        "machine learning",
        "artificial intelligence",
        "ai",
        "robotics",
    ),
    "Engineering": (
        "engineering",
        "maschinenbau",
        "mechanical",
        "electrical",
        "elektro",
        "aerospace",
        "mechatron",
        "civil",
        "chemical",
    ),
    "Natural Sciences & Math": (
        "physics",
        "physik",
        "mathematics",
        "mathematik",
        "chemistry",
        "chemie",
        "biology",
        "biologie",
        "bioinformatics",
        "neuro",
    ),
    "Medicine & Life Sciences": ("medicine", "medizin", "pharma", "biotech", "health"),
    "Law & Social Sciences": (
        "law",
        "jura",
        "political",
        "psychology",
        "sociology",
        "philosophy",
        "design",
        "architecture",
    ),
}

CAREER_GROUPS: dict[str, tuple[str, ...]] = {
    "Founder": (
        "founder",
        "co-founder",
        "cofounder",
        "gründer",
        "ceo & founder",
        "founding",
        "own company",
        "self-employed",
        "selbstständig",
        "owner",
        "ceo",
    ),
    "Startup": (
        "startup",
        "start-up",
        "early stage",
        "seed",
        "series a",
        "scale-up",
        "scaleup",
        "stealth",
        "yc ",
        "(yc",
    ),
    "Consulting": (
        "consult",
        "mckinsey",
        "bcg",
        "bain",
        "roland berger",
        "accenture",
        "deloitte",
        "pwc",
        "kpmg",
        "ey ",
        "strategy&",
        "oliver wyman",
    ),
    "Big Tech": (
        "google",
        "microsoft",
        "amazon",
        "apple",
        "meta",
        "facebook",
        "netflix",
        "nvidia",
        "salesforce",
        "sap",
        "uber",
        "airbnb",
        "stripe",
        "palantir",
        "openai",
        "anthropic",
        "deepmind",
    ),
    "Venture Capital": (
        "venture",
        " vc",
        "capital",
        "investor",
        "investment",
        "private equity",
        "angel",
    ),
    "Corporate": (
        "bmw",
        "siemens",
        "allianz",
        "bosch",
        "audi",
        "daimler",
        "mercedes",
        "volkswagen",
        "porsche",
        "lufthansa",
        "deutsche",
        "munich re",
        "infineon",
        "airbus",
        "telekom",
        "adidas",
        "henkel",
        "bayer",
        "basf",
    ),
    "Product & Engineering": (
        "product",
        "software engineer",
        "developer",
        "engineer",
        "data scientist",
        "data analyst",
        "applied scientist",
        "member of technical staff",
        "ml engineer",
        "designer",
        "cto",
        "architect",
        "gtm",
        "growth",
    ),
    "Research & Academia": (
        "phd",
        "doctoral",
        "research",
        "professor",
        "postdoc",
        "university",
        "universität",
        "institute",
        "fellow",
    ),
    "Finance & Banking": (
        "bank",
        "goldman",
        "morgan",
        "jp morgan",
        "finance",
        "trading",
        "asset management",
        "blackrock",
    ),
    # Generic leadership and function titles land in Corporate only after every more
    # specific group has had its chance (dict order is the match order).
    "Corporate (by role)": (
        "chief",
        "head of",
        "director",
        "vice president",
        "vp",
        "manager",
        "geschäftsführer",
        "operations",
        "strategy",
        "analyst",
        "sales",
        "marketing",
        "president",
    ),
}


def _matches(haystack: str, needles: tuple[str, ...]) -> bool:
    # Needles match at a word start so "informatic" covers Informatics/Informatik while a
    # short needle such as "ai" does not fire inside "maintenance" or "retail".
    return any(re.search(rf"\b{re.escape(n)}", haystack) for n in needles)


_CDTM = re.compile(r"cdtm|center for digital technology|technology management", re.IGNORECASE)
# Entries that say nothing about the field of study (school-leaving certificates, stays
# abroad). They are skipped rather than classified as "Other".
_NOT_A_DEGREE = re.compile(
    r"abitur|high school|visiting|exchange|semester abroad|summer school|erasmus", re.IGNORECASE
)


def _classify_text(text: str, groups: dict[str, tuple[str, ...]]) -> str | None:
    haystack = text.lower()
    if not haystack.strip():
        return None
    for group, needles in groups.items():
        if _matches(haystack, needles):
            # "<Group> (by role)" entries are fallbacks that share the label of their group.
            return group.split(" (")[0]
    return "Other"


def classify_study(educations: list[StudyEntry], major: str | None) -> str | None:
    """Field of study, from the roster major first and then each non-CDTM degree.

    Every member holds the CDTM "Honours Degree, Technology Management", so a single
    concatenated haystack would classify the whole community as Business & Management.
    Candidates are therefore judged one at a time, in priority order, and the first one
    that lands in a real group wins.
    """
    candidates = [major or ""]
    for e in educations:
        blob = f"{e.degree or ''} {e.school or ''}"
        if _CDTM.search(blob) or _NOT_A_DEGREE.search(blob):
            continue
        candidates.append(blob)
    verdicts = [_classify_text(c, STUDY_GROUPS) for c in candidates]
    verdicts = [v for v in verdicts if v is not None]
    if not verdicts:
        return None
    return next((v for v in verdicts if v != "Other"), "Other")


def classify_career(title: str | None, company: str | None) -> str | None:
    return _classify_text(f"{title or ''} {company or ''}", CAREER_GROUPS)


def _is_cdtm_or_student(p: WorkEntry) -> bool:
    blob = f"{p.title or ''} {p.company or ''}".lower()
    return bool(_CDTM.search(blob)) or any(
        w in blob for w in ("student", "intern", "werkstudent", "working student", "praktik")
    )


def _class_end(class_year: int | None, season: str | None) -> date | None:
    """CDTM classes run ~1.5 years; approximate the end of the class."""
    if class_year is None:
        return None
    # Spring class starts ~April, ends ~Sept next year; Fall starts ~Oct, ends ~March +2.
    if (season or "").lower().startswith("spring"):
        return date(class_year + 1, 9, 30)
    return date(class_year + 2, 3, 31)


def compute_member_path(history: CareerHistory) -> MemberPath:
    """Study group, first non-student step after CDTM, current position group."""
    positions = history.work
    study = classify_study(history.study, history.major)

    dated = [p for p in positions if p.start_date is not None]
    dated.sort(key=lambda p: p.start_date or date.min)
    class_end = _class_end(history.class_year, history.class_season)

    first_step: WorkEntry | None = None
    for p in dated:
        if _is_cdtm_or_student(p):
            continue
        if class_end is not None and p.start_date is not None and p.start_date < class_end:
            # Started before the class ended: not the "first step after CDTM".
            continue
        first_step = p
        break
    if first_step is None:
        # fall back to the earliest non-student job at all
        first_step = next((p for p in dated if not _is_cdtm_or_student(p)), None)

    # People often hold several current roles (founder + advisor + board seat). Prefer the
    # one the classifier can name, then the first non-student one, then anything current.
    current_candidates = [p for p in positions if p.is_current and not _is_cdtm_or_student(p)]
    current = next(
        (p for p in current_candidates if classify_career(p.title, p.company) != "Other"),
        current_candidates[0] if current_candidates else None,
    )
    if current is None:
        current = next((p for p in positions if p.is_current), None)

    return MemberPath(
        member_id=history.member_id,
        study_group=study,
        first_step_group=classify_career(first_step.title, first_step.company)
        if first_step
        else None,
        first_step_title=first_step.title if first_step else None,
        first_step_company=first_step.company if first_step else None,
        current_group=classify_career(current.title, current.company) if current else None,
        current_title=current.title if current else None,
        current_company=current.company if current else None,
    )
