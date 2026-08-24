"""Translating a housing question with a model, against a fake completer.

``LLM_PROVIDER=none`` everywhere else in the suite, so this is the only place the model
branch of the housing Ask runs at all. The completer is a port; the fake here implements it
and answers with whatever the test needs, including badly, because "the model said
something we cannot use" is the case that matters most.
"""

from datetime import date

import pytest

from backend.core.exceptions import LlmUnavailableError, ValidationError
from backend.core.llm.ask import MAX_ASK_LIMIT, ViewerContext
from backend.housing.domain import HousingKind
from backend.housing.infrastructure.housing_ask_translator_llm import (
    LlmHousingTranslator,
    build_system_prompt,
)

VIEWER = ViewerContext(today=date(2026, 8, 22))

ANSWER = {
    "summary": "Rooms on offer in Schwabing under 900 euros.",
    "filters": {"kind": "offer", "district": "Schwabing", "max_price": 900},
    "confidence": 0.82,
    "unresolved": ["with good vibes"],
}


class FakeCompleter:
    """A structured completer that answers with whatever the test handed it."""

    model = "fake-model-1"

    def __init__(self, answer: dict | Exception) -> None:
        self._answer = answer
        self.calls: list[dict] = []

    async def complete_json(self, *, system: str, user: str, schema: dict, schema_name: str):
        self.calls.append(
            {"system": system, "user": user, "schema": schema, "schema_name": schema_name}
        )
        if isinstance(self._answer, Exception):
            raise self._answer
        return self._answer


async def translate(answer: dict | Exception, question: str = "room in Schwabing", **kw):
    return await LlmHousingTranslator(FakeCompleter(answer)).translate(
        question, viewer=VIEWER, **kw
    )


async def test_the_models_answer_becomes_the_interpretation() -> None:
    interpretation = await translate(ANSWER)
    assert interpretation.summary == ANSWER["summary"]
    assert interpretation.filters.kind is HousingKind.OFFER
    assert interpretation.filters.district == "Schwabing"
    assert interpretation.filters.max_price == 900
    assert interpretation.confidence == 0.82
    assert interpretation.unresolved == ["with good vibes"]
    assert interpretation.source == "llm"


async def test_the_question_is_what_the_model_is_asked_about() -> None:
    completer = FakeCompleter(ANSWER)
    await LlmHousingTranslator(completer).translate("wg in Giesing", viewer=VIEWER)
    assert completer.calls[0]["user"] == "wg in Giesing"
    assert completer.calls[0]["schema_name"] == "housing_query"


async def test_the_model_is_held_to_a_strict_schema_of_the_fields_we_wrote() -> None:
    """The provider is asked for exactly this object, so a field we never wrote cannot come
    back and a field we did write cannot be left out."""
    completer = FakeCompleter(ANSWER)
    await LlmHousingTranslator(completer).translate("wg in Giesing", viewer=VIEWER)
    schema = completer.calls[0]["schema"]
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    assert "filters" in schema["properties"]


async def test_a_model_that_said_nothing_useful_still_gets_a_sentence() -> None:
    for summary in ("", "   ", None):
        interpretation = await translate({**ANSWER, "summary": summary})
        assert interpretation.summary == "Reading your question as filters."


async def test_a_summary_longer_than_the_response_allows_is_cut_to_fit() -> None:
    interpretation = await translate({**ANSWER, "summary": "x" * 400})
    assert len(interpretation.summary) == 300


async def test_a_confidence_outside_the_scale_is_pulled_back_onto_it() -> None:
    assert (await translate({**ANSWER, "confidence": 7.5})).confidence == 1.0
    assert (await translate({**ANSWER, "confidence": -3})).confidence == 0.0
    # A model that did not say gets the benefit of a middling doubt.
    assert (await translate({**ANSWER, "confidence": None})).confidence == 0.6


async def test_blank_unresolved_phrases_are_dropped_and_missing_ones_are_a_list() -> None:
    assert (await translate({**ANSWER, "unresolved": ["", "  ", "quiet"]})).unresolved == ["quiet"]
    assert (await translate({**ANSWER, "unresolved": None})).unresolved == []


async def test_a_model_that_filtered_on_nothing_filters_on_nothing() -> None:
    filters = (await translate({**ANSWER, "filters": None})).filters
    assert filters.model_dump(exclude_none=True) == {}


async def test_fields_the_model_invented_are_ignored() -> None:
    interpretation = await translate({**ANSWER, "reasoning": "because I said so"})
    assert interpretation.summary == ANSWER["summary"]


async def test_filters_we_cannot_use_are_refused_rather_than_guessed_at() -> None:
    """The refusal names the model as the thing that went wrong: the member wrote a fine
    question, so "we cannot use this" has to point at the answer, not at them."""
    why = "the language model returned filters we cannot use"
    for filters in ({"max_price": "quite a lot"}, {"district": "Schwabing", "colour": "blue"}):
        with pytest.raises(ValidationError) as refused:
            await translate({**ANSWER, "filters": filters})
        assert refused.value.message == why


async def test_a_provider_that_is_down_is_reported_as_such() -> None:
    """The Ask service catches this to fall back to keywords, so it must reach it."""
    with pytest.raises(LlmUnavailableError):
        await translate(LlmUnavailableError("provider unreachable"))


async def test_the_answer_is_attributed_to_the_model_that_wrote_it() -> None:
    assert LlmHousingTranslator(FakeCompleter(ANSWER)).model_name == "fake-model-1"
    assert LlmHousingTranslator(FakeCompleter(ANSWER), model_name="pinned").model_name == "pinned"


async def test_a_completer_that_does_not_name_its_model_leaves_the_name_empty() -> None:
    """The name is logged next to every question, so "no name" has to be a string."""

    class Nameless:
        async def complete_json(self, *, system, user, schema, schema_name):
            return ANSWER

    assert LlmHousingTranslator(Nameless()).model_name == ""


# ---- the prompt the model is given ---------------------------------------------------------


def test_the_prompt_dates_the_question_and_caps_the_page() -> None:
    prompt = build_system_prompt(VIEWER)
    assert "2026-08-22" in prompt
    assert str(MAX_ASK_LIMIT) in prompt


def test_the_asked_for_language_reaches_the_prompt() -> None:
    assert "pt-BR" in build_system_prompt(VIEWER, language="pt-BR")
    assert "pt-BR" not in build_system_prompt(VIEWER)


async def test_the_language_the_caller_asked_for_is_what_the_model_is_told() -> None:
    completer = FakeCompleter(ANSWER)
    await LlmHousingTranslator(completer).translate("room", viewer=VIEWER, language="pt-BR")
    assert "pt-BR" in completer.calls[0]["system"]
