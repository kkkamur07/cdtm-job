"""Language-model translation of a job question into a ``JobQuery``."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict
from pydantic import ValidationError as PydanticValidationError

from backend.core.exceptions import ValidationError
from backend.core.llm import StructuredCompleter, strict_json_schema
from backend.core.llm.ask import summary_language_rule
from backend.jobboard.domain import (
    MAX_ASK_LIMIT,
    EmploymentType,
    ExperienceLevel,
    JobAskInterpretation,
    JobQuery,
    WorkArrangement,
)

SCHEMA_NAME = "job_query"

_SYSTEM = """\
You turn a plain-words question about the CDTM job board into a filter object. You never \
see the board and you never write a query: you fill in fields, and the platform searches.

Rules that matter more than being helpful:
- Only fill a field when the question says so. Never invent a company, a city or a salary.
- Put every phrase you could not map into `unresolved`, verbatim and lower-cased.
- `summary` is one sentence, at most 25 words, shown above the results. {summary_language}
- `confidence` is 0 to 1.

The fields:
- `q`: free text over title, summary, description and the displayed location. Use it for \
the kind of work ("product", "machine learning") when no other field fits.
- `employment_type`: any of {employment_types}.
- `work_arrangement`: any of {arrangements}. `remote_only`: true when the question asks \
for remote work specifically.
- `experience_level`: any of {levels}.
- `city` / `country`: where the job is. Spell the city in English (Munich, not Muenchen; \
Vienna, Zurich), whatever language the question is in.
- `company`: the hiring company by name. `is_cdtm_startup`: true when the question asks \
for companies founded by CDTM people.
- `salary_min`: a floor, a plain number in the posting's own currency ("80k" is 80000).
- `posted_within_days`: how recent the posting must be.
- `limit`: at most {max_limit}. `sort`: "relevance", "recent" or "salary".

Today is {today}."""


class _WireInterpretation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    summary: str | None = None
    filters: JobQuery | None = None
    confidence: float | None = None
    unresolved: list[str] | None = None


def build_system_prompt(today: date | None = None, *, language: str | None = None) -> str:
    return _SYSTEM.format(
        summary_language=summary_language_rule(language),
        employment_types=", ".join(e.value for e in EmploymentType),
        arrangements=", ".join(w.value for w in WorkArrangement),
        levels=", ".join(x.value for x in ExperienceLevel),
        max_limit=MAX_ASK_LIMIT,
        today=(today or date.today()).isoformat(),
    )


class LlmJobTranslator:
    def __init__(self, completer: StructuredCompleter, *, model_name: str = "") -> None:
        self._completer = completer
        self.model_name = model_name or getattr(completer, "model", "")

    async def translate(
        self, question: str, *, language: str | None = None
    ) -> JobAskInterpretation:
        raw = await self._completer.complete_json(
            system=build_system_prompt(language=language),
            user=question,
            schema=strict_json_schema(_WireInterpretation),
            schema_name=SCHEMA_NAME,
        )
        try:
            wire = _WireInterpretation.model_validate(raw)
        except PydanticValidationError as exc:
            raise ValidationError("the language model returned filters we cannot use") from exc
        return JobAskInterpretation(
            summary=(wire.summary or "").strip()[:300] or "Reading your question as filters.",
            filters=wire.filters or JobQuery(),
            confidence=min(1.0, max(0.0, wire.confidence if wire.confidence is not None else 0.6)),
            unresolved=[u for u in (wire.unresolved or []) if u.strip()],
            source="llm",
        )
