"""The golden set: thirty questions and the filters they are supposed to produce.

The keyword translator has to get every one of these right, because it is what answers
when no provider is configured. The same set doubles as the evaluation harness for a real
provider, which is opt-in (`ASK_EVAL_LLM=1`) because it costs money and needs the network.
See docs/ask.md.
"""

import os
from datetime import date

import pytest

from backend.core.llm import get_structured_completer
from backend.core.llm.ask import ViewerContext
from backend.members.domain import Intent, MemberQuery
from backend.members.infrastructure.ask_translator_llm import LlmQueryTranslator
from backend.members.infrastructure.ask_translator_rules import RulesQueryTranslator
from backend.paths.domain import CAREER_GROUP_NAMES, STUDY_GROUP_NAMES, CareerGroup, StudyGroup

#: The Paths vocabulary, injected exactly the way ``backend/members/api/deps.py`` injects
#: it. A group renamed there and not here fails this file, which is the point.
VOCABULARY = {"study_groups": STUDY_GROUP_NAMES, "career_groups": CAREER_GROUP_NAMES}

VIEWER = ViewerContext(
    class_label="Fall 2019", class_year=2019, location="Munich", today=date(2026, 8, 22)
)

# (question, the filters that must be set). Extra filters are allowed: a translator that
# also picks up something true is not wrong, one that misses the point is.
GOLDEN: list[tuple[str, dict]] = [
    (
        "who studied at Stanford and then went into VC",
        {"school": "Stanford", "current_group": CareerGroup.VENTURE_CAPITAL},
    ),
    (
        "TUM alumni working in big tech",
        {"school": "TUM", "current_group": CareerGroup.BIG_TECH},
    ),
    (
        "class of 2019 in consulting",
        {"class_year_min": 2019, "class_year_max": 2019, "current_group": CareerGroup.CONSULTING},
    ),
    ("spring 2021 founders", {"class_label": "Spring 2021"}),
    ("people from my class in Berlin", {"class_label": "Fall 2019", "location": "Berlin"}),
    ("founders in Munich", {"current_group": CareerGroup.FOUNDER, "location": "Munich"}),
    (
        "anyone who studied computer science",
        {"study_group": StudyGroup.COMPUTER_SCIENCE},
    ),
    (
        "people whose first job was in consulting",
        {"first_step_group": CareerGroup.CONSULTING},
    ),
    ("who worked at McKinsey", {"past_company": "Mckinsey"}),
    ("people at Google", {"company": "Google"}),
    ("members open to mentoring", {"intents": [Intent.MENTORING]}),
    ("who is hiring", {"intents": [Intent.HIRING]}),
    ("anyone who speaks french", {"languages": ["French"]}),
    (
        "someone with skills in python, kubernetes",
        {"skills": ["python", "kubernetes"]},
    ),
    ("Center Assistants in Munich", {"is_ca": True, "location": "Munich"}),
    ("people in München", {"location": "Munich"}),
    ("who is doing a phd", {"current_group": CareerGroup.RESEARCH_ACADEMIA}),
    ("people in banking in Zürich", {"current_group": CareerGroup.FINANCE_BANKING}),
    (
        "engineers who studied at ETH",
        {"school": "ETH", "current_group": CareerGroup.PRODUCT_ENGINEERING},
    ),
    (
        "alumni since 2020 who founded something",
        {"class_year_min": 2020, "current_group": CareerGroup.FOUNDER},
    ),
    (
        "people in Berlin open to co-founding who studied computer science",
        {
            "location": "Berlin",
            "intents": [Intent.COFOUNDING],
            "study_group": StudyGroup.COMPUTER_SCIENCE,
        },
    ),
    (
        "mentors working in venture capital",
        {"intents": [Intent.MENTORING], "current_group": CareerGroup.VENTURE_CAPITAL},
    ),
    (
        "who went from engineering into product management at a big tech company?",
        {"current_group": CareerGroup.BIG_TECH, "company": None},
    ),
    (
        "CDTM alumni in Zurich working at Google",
        {"location": "Zurich", "company": "Google"},
    ),
    (
        "class of 2019 or later, open to speaking",
        {"class_year_min": 2019, "class_year_max": None, "intents": [Intent.SPEAKING]},
    ),
    ("angels who could invest in a pre-seed round", {"intents": [Intent.INVESTING]}),
    (
        "founders from my class",
        {"class_label": "Fall 2019", "current_group": CareerGroup.FOUNDER},
    ),
    # German, because a third of the directory writes to us in it. The place name comes
    # back in the English spelling the member rows use, which is what the filter matches.
    (
        "Wer in Muenchen arbeitet bei BMW und ist offen fuer Mentoring?",
        {"location": "Munich", "company": "BMW", "intents": [Intent.MENTORING]},
    ),
    ("people who studied law", {"study_group": StudyGroup.LAW_SOCIAL_SCIENCES}),
    (
        "someone open to roles in product",
        {"intents": [Intent.OPEN_TO_ROLES]},
    ),
]


def _same(got: object, want: object) -> bool:
    # Free-text fields end up in ILIKE, so "Mckinsey" and "McKinsey" are the same answer.
    if isinstance(got, str) and isinstance(want, str):
        return got.casefold() == want.casefold()
    return got == want


def _misses(actual: MemberQuery, expected: dict) -> list[str]:
    got = actual.model_dump()
    return [
        f"{field}: expected {want!r}, got {got.get(field)!r}"
        for field, want in expected.items()
        if not _same(got.get(field), want)
    ]


@pytest.mark.parametrize(("question", "expected"), GOLDEN, ids=[c[0] for c in GOLDEN])
async def test_the_keyword_translator_reads_the_golden_set(question: str, expected: dict) -> None:
    interpretation = await RulesQueryTranslator(**VOCABULARY).translate(question, viewer=VIEWER)
    assert not _misses(interpretation.filters, expected)


def test_the_golden_set_is_thirty_questions() -> None:
    assert len(GOLDEN) == 30
    assert len({q for q, _ in GOLDEN}) == 30


# The bar is not 100%: a language model paraphrases, and one questionable reading out of
# five is still a usable feature. Below this, the prompt has regressed.
MIN_PASS_RATE = 0.8


@pytest.mark.skipif(
    os.getenv("ASK_EVAL_LLM") != "1",
    reason="set ASK_EVAL_LLM=1 with a provider configured to spend tokens on the eval",
)
async def test_the_configured_provider_reads_the_golden_set() -> None:
    completer = get_structured_completer()
    if completer is None:
        pytest.skip("no LLM provider configured")

    translator = LlmQueryTranslator(completer, **VOCABULARY)
    failures: list[str] = []
    for question, expected in GOLDEN:
        interpretation = await translator.translate(question, viewer=VIEWER)
        misses = _misses(interpretation.filters, expected)
        if misses:
            failures.append(f"{question!r}: {'; '.join(misses)}")

    passed = len(GOLDEN) - len(failures)
    assert passed / len(GOLDEN) >= MIN_PASS_RATE, f"{passed}/{len(GOLDEN)} correct\n" + "\n".join(
        failures
    )
