"""What every board's Ask shares: the question's limits and who is asking.

The filter object a question becomes belongs to the board it is about, so ``MemberQuery``
lives in ``members``, ``HousingQuery`` in ``housing`` and ``JobQuery`` in ``jobboard``.
What is here is the mechanism around them: how long a question may be, and the handful of
facts about the asker that let "my class" and "near me" resolve to concrete values before
any query runs.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict

from backend.core.exceptions import ValidationError

#: The most rows one question may ask for. Ask pages like every other list endpoint; this
#: is the ceiling on a single page, matching ``core/api/pagination.py``.
MAX_ASK_LIMIT = 100

MIN_QUESTION_LENGTH = 3
MAX_QUESTION_LENGTH = 300

#: Appended to ``unresolved`` when the provider was unreachable and keywords answered
#: instead, so the UI can say why the reading looks coarser than usual.
LLM_DOWN_NOTE = "LLM unavailable, keyword interpretation used"

QuestionSource = Literal["llm", "rules"]

#: A short BCP-47 tag ("de", "en-GB"). Kept to a pattern rather than a closed list because
#: the value is only ever interpolated into a prompt, and a closed list would mean shipping
#: a release to answer somebody in Portuguese.
LANGUAGE_PATTERN = r"^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8}){0,2}$"

#: What the rules translator writes its summary in, whatever was asked for. It has no
#: sentences of its own beyond the ones in ``describe()``, and a machine-translated chip is
#: worse than an English one.
RULES_SUMMARY_LANGUAGE = "en"


def summary_language_rule(language: str | None) -> str:
    """The one prompt line that decides what language the reader is answered in.

    Only the ``summary`` is affected. Filter values stay in the spellings the database
    uses, or "Wer arbeitet in Muenchen" would search for a city that is not in any row.
    """
    if language:
        return f"Write `summary` in {language}."
    return "Write `summary` in the language the question is written in; when in doubt, English."


class ViewerContext(BaseModel):
    """What "my class" and "near me" mean for the member who is asking.

    Assembled by the application layer from the asker's own row, and handed to the
    translator so relative phrases resolve to concrete values before any query runs. It is
    the asker's own data, never anybody else's.
    """

    model_config = ConfigDict(extra="forbid")

    class_label: str | None = None
    class_year: int | None = None
    location: str | None = None
    current_group: str | None = None
    today: date | None = None


def validate_question(question: str) -> None:
    """Reject a question before it costs a model call."""
    length = len(question.strip())
    if length < MIN_QUESTION_LENGTH:
        raise ValidationError("ask a question of at least three characters")
    if length > MAX_QUESTION_LENGTH:
        raise ValidationError(
            f"that question is {length} characters; keep it under {MAX_QUESTION_LENGTH}"
        )
