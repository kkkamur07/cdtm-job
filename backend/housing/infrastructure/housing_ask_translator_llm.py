"""Language-model translation of a housing question into a ``HousingQuery``."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict
from pydantic import ValidationError as PydanticValidationError

from backend.core.exceptions import ValidationError
from backend.core.llm import StructuredCompleter, strict_json_schema
from backend.core.llm.ask import MAX_ASK_LIMIT, ViewerContext, summary_language_rule
from backend.housing.domain import (
    HousingAskInterpretation,
    HousingQuery,
)

SCHEMA_NAME = "housing_query"

_SYSTEM = """\
You turn a CDTM community member's plain-words question into a filter object for the \
housing board, where members post rooms they are offering and rooms they are looking for.

Rules that matter more than being helpful:
- Only fill a field when the question says so. Never invent a city, a district or a price.
- Put every phrase you could not map into `unresolved`, verbatim and lower-cased.
- `summary` is one sentence, at most 25 words, shown above the results. {summary_language}
- `confidence` is 0 to 1.

The fields:
- `kind`: "offer" for a room somebody is offering, "looking" for somebody searching. \
Somebody asking for a room wants "offer".
- `city` and `district`: the city, and the part of it ("Schwabing", "Kreuzberg"). Spell the city \
in English (Munich, not Muenchen; Vienna, Zurich), whatever language the question is in.
- `min_price` / `max_price`: euros per month.
- `available_from`: the listing must be free by this date. `available_until`: it must \
still be free on this date. Both ISO dates; read "from October" as the first of that \
month, in the next occurrence of it.
- `min_rooms`: number of rooms, at least.
- `furnished`: true or false only if the question says so.
- `q`: free text over title, description and area, for anything more specific.
- `limit`: at most {max_limit}.

Today is {today}."""


class _WireInterpretation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    summary: str | None = None
    filters: HousingQuery | None = None
    confidence: float | None = None
    unresolved: list[str] | None = None


def build_system_prompt(viewer: ViewerContext, *, language: str | None = None) -> str:
    return _SYSTEM.format(
        max_limit=MAX_ASK_LIMIT,
        today=(viewer.today or date.today()).isoformat(),
        summary_language=summary_language_rule(language),
    )


class LlmHousingTranslator:
    def __init__(self, completer: StructuredCompleter, *, model_name: str = "") -> None:
        self._completer = completer
        self.model_name = model_name or getattr(completer, "model", "")

    async def translate(
        self, question: str, *, viewer: ViewerContext, language: str | None = None
    ) -> HousingAskInterpretation:
        raw = await self._completer.complete_json(
            system=build_system_prompt(viewer, language=language),
            user=question,
            schema=strict_json_schema(_WireInterpretation),
            schema_name=SCHEMA_NAME,
        )
        try:
            wire = _WireInterpretation.model_validate(raw)
        except PydanticValidationError as exc:
            raise ValidationError("the language model returned filters we cannot use") from exc
        return HousingAskInterpretation(
            summary=(wire.summary or "").strip()[:300] or "Reading your question as filters.",
            filters=wire.filters or HousingQuery(),
            confidence=min(1.0, max(0.0, wire.confidence if wire.confidence is not None else 0.6)),
            unresolved=[u for u in (wire.unresolved or []) if u.strip()],
            source="llm",
        )
