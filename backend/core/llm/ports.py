"""The one thing the platform asks a language model to do: emit a JSON object.

There is deliberately no "give me some text" port. Everything the model produces is
validated against a schema we wrote before it is allowed anywhere near the database.
"""

from __future__ import annotations

from typing import Protocol


class StructuredCompleter(Protocol):
    async def complete_json(
        self, *, system: str, user: str, schema: dict, schema_name: str
    ) -> dict:
        """Return the model's answer as a parsed JSON object matching ``schema``.

        Raises :class:`backend.core.exceptions.LlmUnavailableError` (503) when the
        provider cannot be reached or refuses the credentials, and
        :class:`backend.core.exceptions.ValidationError` (422) when it answers with
        something that is not the requested object.
        """
        ...


class QuestionMeter(Protocol):
    """How many questions one caller has asked this minute, across every board.

    A member who spends their allowance on the job board does not then get a fresh one on
    the directory: the cost is the same call to the same provider, so the count is one
    number per caller and not one per board.
    """

    async def allow(self, key: str, *, rate_per_minute: int) -> bool:
        """Count this question and return whether it was within the allowance."""
        ...
