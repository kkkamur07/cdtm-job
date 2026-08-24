"""The request bodies every Ask box posts.

A question and a page, identical on the members board and the housing board, so it is one
schema rather than two that have to be kept in step. The *answer* is per board and lives
with that board's API.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from backend.core.llm.ask import LANGUAGE_PATTERN, MAX_ASK_LIMIT

#: Documented once, used on every Ask request body on every board.
_LANGUAGE_HELP = (
    "BCP-47 tag the one-sentence summary should be written in. Omit it and the summary "
    "comes back in the language the question was asked in. Filters are unaffected."
)


class AskRequest(BaseModel):
    """A plain-words question, plus where in the answer to start."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=3, max_length=300)
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=MAX_ASK_LIMIT)
    language: str | None = Field(
        default=None, max_length=16, pattern=LANGUAGE_PATTERN, description=_LANGUAGE_HELP
    )


class AskExplainRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=3, max_length=300)
    language: str | None = Field(
        default=None, max_length=16, pattern=LANGUAGE_PATTERN, description=_LANGUAGE_HELP
    )
