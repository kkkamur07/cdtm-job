"""The language-model translator for directory questions. No provider, no network.

``LLM_PROVIDER=none`` everywhere else in this suite means ``LlmQueryTranslator`` is never
built and its prompt is never checked against anything but itself. Here it is built with a
fake ``StructuredCompleter`` and a vocabulary of made-up group names, so the test can tell
the difference between the runtime values reaching the prompt and the illustrative examples
that are hardcoded in the template.
"""

from __future__ import annotations

from datetime import date

import pytest

from backend.core.exceptions import ValidationError
from backend.core.llm.ask import MAX_ASK_LIMIT, ViewerContext
from backend.members.infrastructure.ask_translator_llm import (
    SCHEMA_NAME,
    LlmQueryTranslator,
    _viewer_paragraph,
    build_system_prompt,
)

#: Deliberately not the real Paths vocabulary: no name here appears in the static prompt.
STUDY_GROUPS = ("Alpha Studies", "Beta Studies")
CAREER_GROUPS = ("Gamma Careers", "Delta Careers")

VIEWER = ViewerContext(
    class_label="Fall 2019",
    class_year=2019,
    location="Munich",
    current_group="Gamma Careers",
    today=date(2026, 1, 2),
)


class FakeCompleter:
    """A ``StructuredCompleter`` that answers with a fixed object and records the call."""

    def __init__(self, answer: dict, *, model: str = "fake-model") -> None:
        self.answer = answer
        self.model = model
        self.calls: list[dict] = []

    async def complete_json(self, *, system: str, user: str, schema: dict, schema_name: str):
        self.calls.append(
            {"system": system, "user": user, "schema": schema, "schema_name": schema_name}
        )
        return self.answer


class ModellessCompleter(FakeCompleter):
    """A completer that does not advertise a model name."""

    def __init__(self, answer: dict) -> None:
        super().__init__(answer)
        del self.model


def translator(answer: dict, **kw) -> tuple[LlmQueryTranslator, FakeCompleter]:
    completer = FakeCompleter(answer)
    return (
        LlmQueryTranslator(completer, study_groups=STUDY_GROUPS, career_groups=CAREER_GROUPS, **kw),
        completer,
    )


# ---- the paragraph about the person asking ------------------------------------------------


def test_the_viewer_paragraph_lists_every_fact_that_is_known() -> None:
    assert _viewer_paragraph(VIEWER) == (
        "About the person asking, so that 'my class' and 'near me' resolve:\n"
        "- their CDTM class: Fall 2019\n"
        "- their class year: 2019\n"
        "- where they are: Munich\n"
        "- what they do now: Gamma Careers"
    )


def test_the_viewer_paragraph_names_only_the_facts_that_are_known() -> None:
    assert _viewer_paragraph(ViewerContext(location="Berlin")) == (
        "About the person asking, so that 'my class' and 'near me' resolve:\n"
        "- where they are: Berlin"
    )


def test_an_unknown_viewer_is_told_to_leave_my_class_unresolved() -> None:
    """The one wording that must never drift into a guess: nothing is known about them."""
    assert _viewer_paragraph(ViewerContext()) == (
        "You know nothing about the person asking, so treat 'my class' and 'near me' "
        "as unresolved rather than guessing."
    )


# ---- the system prompt --------------------------------------------------------------------


def test_the_prompt_carries_the_runtime_vocabulary_and_the_viewer() -> None:
    prompt = build_system_prompt(
        VIEWER, study_groups=STUDY_GROUPS, career_groups=CAREER_GROUPS, language="de"
    )

    assert "one of Alpha Studies, Beta Studies." in prompt
    assert "one of Gamma Careers, Delta Careers." in prompt
    assert "out of cofounding, mentoring, hiring, open_to_roles, speaking, investing." in prompt
    assert "any of student, ca, faculty." in prompt
    assert f"at most {MAX_ASK_LIMIT}." in prompt
    # A model that does not know today's date cannot resolve "last year's class".
    assert "Today is 2026-01-02." in prompt
    assert _viewer_paragraph(VIEWER) in prompt
    assert "Write `summary` in de." in prompt


def test_without_an_asked_for_language_the_prompt_answers_in_the_question_language() -> None:
    prompt = build_system_prompt(VIEWER, study_groups=(), career_groups=())
    assert "in the language the question is written in" in prompt
    assert "Write `summary` in None." not in prompt


def test_the_prompt_dates_itself_from_today_when_the_viewer_has_no_date() -> None:
    prompt = build_system_prompt(ViewerContext(), study_groups=(), career_groups=())
    assert f"Today is {date.today().isoformat()}." in prompt


# ---- translating --------------------------------------------------------------------------


async def test_the_prompt_the_question_and_the_schema_reach_the_provider() -> None:
    llm, completer = translator({"summary": "ok", "filters": {}, "confidence": 0.9})

    await llm.translate("who studied at Stanford", viewer=VIEWER, language="de")

    call = completer.calls[0]
    assert call["user"] == "who studied at Stanford"
    assert call["schema_name"] == SCHEMA_NAME
    assert call["system"] == build_system_prompt(
        VIEWER, study_groups=STUDY_GROUPS, career_groups=CAREER_GROUPS, language="de"
    )
    # The object the model is allowed to answer with, strict and nothing extra.
    assert set(call["schema"]["properties"]) == {"summary", "filters", "confidence", "unresolved"}
    assert call["schema"]["additionalProperties"] is False


async def test_the_answer_becomes_an_interpretation() -> None:
    llm, _ = translator(
        {
            "summary": "  Members who studied at Stanford.  ",
            "filters": {"school": "Stanford", "limit": 5, "intents": ["mentoring"]},
            "confidence": 0.8,
            "unresolved": ["   ", "somewhere warm"],
        }
    )

    interpretation = await llm.translate("who studied at Stanford", viewer=VIEWER)

    assert interpretation.source == "llm"
    assert interpretation.summary == "Members who studied at Stanford."
    assert interpretation.filters.school == "Stanford"
    assert interpretation.filters.limit == 5
    assert [i.value for i in interpretation.filters.intents or []] == ["mentoring"]
    assert interpretation.confidence == 0.8
    # A blank phrase is not something the model failed to map.
    assert interpretation.unresolved == ["somewhere warm"]


async def test_a_model_with_no_opinion_still_produces_a_usable_interpretation() -> None:
    llm, _ = translator({})

    interpretation = await llm.translate("hello", viewer=ViewerContext())

    assert interpretation.summary == "Reading your question as filters."
    assert interpretation.confidence == 0.6
    assert interpretation.unresolved == []
    assert interpretation.filters.school is None


@pytest.mark.parametrize(("answered", "expected"), [(7.5, 1.0), (-3.0, 0.0)])
async def test_confidence_outside_zero_to_one_is_clamped(answered: float, expected: float) -> None:
    llm, _ = translator({"confidence": answered})
    assert (await llm.translate("hello", viewer=ViewerContext())).confidence == expected


async def test_a_summary_longer_than_the_chip_is_trimmed_rather_than_refused() -> None:
    llm, _ = translator({"summary": "x" * 400})
    assert len((await llm.translate("hello", viewer=ViewerContext())).summary) == 300


async def test_an_answer_that_is_not_a_member_query_is_refused() -> None:
    """422, not 500: the model answered, the answer was not something we can search with."""
    llm, _ = translator({"filters": {"favourite_colour": "green"}})
    with pytest.raises(ValidationError):
        await llm.translate("hello", viewer=ViewerContext())


async def test_group_names_paths_has_no_column_for_are_dropped() -> None:
    """A drifting prompt should broaden the search, not filter nobody out of it."""
    llm, _ = translator(
        {
            "filters": {
                "study_group": "Omega Studies",
                "first_step_group": "Omega Careers",
                "current_group": "Omega Careers",
                "school": "Stanford",
            }
        }
    )

    filters = (await llm.translate("hello", viewer=ViewerContext())).filters

    assert filters.study_group is None
    assert filters.first_step_group is None
    assert filters.current_group is None
    # Only the group names are dropped; the rest of the reading survives.
    assert filters.school == "Stanford"


async def test_group_names_paths_knows_are_kept() -> None:
    llm, _ = translator(
        {
            "filters": {
                "study_group": "Beta Studies",
                "first_step_group": "Gamma Careers",
                "current_group": "Delta Careers",
            }
        }
    )

    filters = (await llm.translate("hello", viewer=ViewerContext())).filters

    assert filters.study_group == "Beta Studies"
    assert filters.first_step_group == "Gamma Careers"
    assert filters.current_group == "Delta Careers"


async def test_one_unknown_group_does_not_drop_the_others() -> None:
    llm, _ = translator(
        {"filters": {"study_group": "Beta Studies", "current_group": "Omega Careers"}}
    )

    filters = (await llm.translate("hello", viewer=ViewerContext())).filters

    assert filters.study_group == "Beta Studies"
    assert filters.current_group is None


def test_the_model_name_recorded_in_the_ask_log_comes_from_the_adapter() -> None:
    answer: dict = {}
    named, _ = translator(answer, model_name="gpt-test")
    assert named.model_name == "gpt-test"

    inferred, completer = translator(answer)
    assert inferred.model_name == completer.model

    anonymous = LlmQueryTranslator(
        ModellessCompleter(answer), study_groups=STUDY_GROUPS, career_groups=CAREER_GROUPS
    )
    assert anonymous.model_name == ""
