"""Language-model translation of a directory question into a ``MemberQuery``.

The model is given a schema and a paragraph of context and asked for one object. It is not
given the directory, it is not given a database connection, and the object it returns is
validated by pydantic before anything is queried. The worst a bad answer can do is search
for the wrong school.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict
from pydantic import ValidationError as PydanticValidationError

from backend.core.exceptions import ValidationError
from backend.core.llm import StructuredCompleter, strict_json_schema
from backend.core.llm.ask import MAX_ASK_LIMIT, ViewerContext, summary_language_rule
from backend.members.domain import AskInterpretation, Intent, MemberQuery, Role

SCHEMA_NAME = "member_query"

_SYSTEM = """\
You turn a CDTM community member's plain-words question into a filter object for the \
member directory. You never see the directory and you never write a query: you only fill \
in fields, and the platform runs the search.

Rules that matter more than being helpful:
- Only fill a field when the question actually says so. Never invent a school, a company, \
a city or a class that the question did not name.
- Put every phrase you could not map into `unresolved`, verbatim and lower-cased. A short \
`unresolved` list with correct filters beats a guess.
- `summary` is one sentence, at most 25 words, written for the person who asked: "Members \
who studied at Stanford and are now in Venture Capital." It is shown above the results. \
{summary_language}
- `confidence` is 0 to 1: how sure you are that the filters are what was asked for.

The fields:
- `q`: free text, matched against a haystack of name, headline, company, title, class, \
skills, past positions and schools. Use it only for a name or a company you cannot place \
in a more specific field.
- `school` / `degree`: matched against education history. `school` is a university name; \
keep it as short as the question had it ("ETH", not "ETH Zurich"), since it is a substring \
match and umlauts vary.
- `major`: the CDTM roster major, not a university degree.
- `company`: where the person is now. `past_company`: anywhere they have worked.
- `title`: a job title, current or past.
- `location`: a city, region or country the person is in. Spell places the way LinkedIn \
does in English (Munich, not Muenchen; Cologne, Vienna, Zurich), whatever language the \
question is in.
- `class_label`: a CDTM class, spelled "Spring 2021" or "Fall 2019". \
`class_year_min` / `class_year_max`: a range of class years, inclusive.
- `study_group`: one of {study_groups}.
- `first_step_group`: the first job after CDTM, one of {career_groups}.
- `current_group`: what the person does now, same list. Prefer `current_group` unless the \
question is explicitly about the first step after CDTM. Plain role words map to groups: \
engineers, developers, product people -> "Product & Engineering"; founders -> "Founder"; \
consultants -> "Consulting"; investors, VCs -> "Venture Capital"; researchers, PhDs -> \
"Research & Academia"; bankers -> "Finance & Banking".
- `skills` / `languages`: a person matches if they have any one of them.
- `intents`: what a member has said they are open to, out of {intents}. A person must \
have all of the ones you list.
- `roles`: any of {roles}. `is_ca`: true for Center Assistants only.
- `limit`: at most {max_limit}. `sort`: "relevance", "name" or "class".

Today is {today}.
{viewer}"""


class _WireInterpretation(BaseModel):
    """What the model is asked for. Every field nullable: a null means "no opinion"."""

    model_config = ConfigDict(extra="ignore")

    summary: str | None = None
    filters: MemberQuery | None = None
    confidence: float | None = None
    unresolved: list[str] | None = None


def _viewer_paragraph(viewer: ViewerContext) -> str:
    known = [
        ("their CDTM class", viewer.class_label),
        ("their class year", str(viewer.class_year) if viewer.class_year else None),
        ("where they are", viewer.location),
        ("what they do now", viewer.current_group),
    ]
    lines = [f"- {label}: {value}" for label, value in known if value]
    if not lines:
        return (
            "You know nothing about the person asking, so treat 'my class' and 'near me' "
            "as unresolved rather than guessing."
        )
    return "About the person asking, so that 'my class' and 'near me' resolve:\n" + "\n".join(lines)


def build_system_prompt(
    viewer: ViewerContext,
    *,
    study_groups: tuple[str, ...],
    career_groups: tuple[str, ...],
    language: str | None = None,
) -> str:
    return _SYSTEM.format(
        summary_language=summary_language_rule(language),
        study_groups=", ".join(study_groups),
        career_groups=", ".join(career_groups),
        intents=", ".join(i.value for i in Intent),
        roles=", ".join(r.value for r in Role),
        max_limit=MAX_ASK_LIMIT,
        today=(viewer.today or date.today()).isoformat(),
        viewer=_viewer_paragraph(viewer),
    )


class LlmQueryTranslator:
    """Asks a model for a ``MemberQuery``.

    The career and study group names are constructor arguments rather than an import: they
    are the Paths read model's vocabulary, and this context is only allowed to pass them
    through. A name the model returns that is not in the list is dropped, so a prompt that
    drifts produces a broader search rather than a filter that matches nobody.
    """

    def __init__(
        self,
        completer: StructuredCompleter,
        *,
        study_groups: tuple[str, ...],
        career_groups: tuple[str, ...],
        model_name: str = "",
    ) -> None:
        self._completer = completer
        self._study_groups = frozenset(study_groups)
        self._career_groups = frozenset(career_groups)
        self._study_group_names = study_groups
        self._career_group_names = career_groups
        self.model_name = model_name or getattr(completer, "model", "")

    async def translate(
        self, question: str, *, viewer: ViewerContext, language: str | None = None
    ) -> AskInterpretation:
        raw = await self._completer.complete_json(
            system=build_system_prompt(
                viewer,
                study_groups=self._study_group_names,
                career_groups=self._career_group_names,
                language=language,
            ),
            user=question,
            schema=strict_json_schema(_WireInterpretation),
            schema_name=SCHEMA_NAME,
        )
        try:
            wire = _WireInterpretation.model_validate(raw)
        except PydanticValidationError as exc:
            # 422 rather than 500: the model answered, the answer was not a MemberQuery.
            raise ValidationError("the language model returned filters we cannot use") from exc
        filters = self._drop_unknown_groups(wire.filters or MemberQuery())
        return AskInterpretation(
            summary=(wire.summary or "").strip()[:300] or "Reading your question as filters.",
            filters=filters,
            confidence=min(1.0, max(0.0, wire.confidence if wire.confidence is not None else 0.6)),
            unresolved=[u for u in (wire.unresolved or []) if u.strip()],
            source="llm",
        )

    def _drop_unknown_groups(self, filters: MemberQuery) -> MemberQuery:
        """Unset any group name Paths does not have a column for."""
        update: dict[str, None] = {}
        if filters.study_group and filters.study_group not in self._study_groups:
            update["study_group"] = None
        for field in ("first_step_group", "current_group"):
            value = getattr(filters, field)
            if value and value not in self._career_groups:
                update[field] = None
        return filters.model_copy(update=update) if update else filters
