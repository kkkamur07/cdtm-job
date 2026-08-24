"""One structured log line per asked question.

What is logged is the *question's shape* and the *filters it became*, never a row that
came back. Filters carry the words the member typed (a school, a company, a district), so
they are the caller's own input and not somebody else's data; the result set is only ever
a count. ``docs/ask.md`` explains how to read these lines to tune the prompt.
"""

from __future__ import annotations

import json
import logging

logger = logging.getLogger("backend.ask")


def log_ask(
    *,
    board: str,
    actor: str,
    question_length: int,
    source: str,
    model: str,
    latency_ms: int,
    filters: dict,
    total: int | None,
    unresolved: list[str],
) -> None:
    logger.info(
        "ask board=%s actor=%s question_length=%d source=%s model=%s latency_ms=%d "
        "total=%s unresolved=%s filters=%s",
        board,
        actor,
        question_length,
        source,
        model or "-",
        latency_ms,
        "-" if total is None else total,
        json.dumps(unresolved, sort_keys=True),
        # Sorted keys so two identical questions produce byte-identical lines and can be
        # counted with grep alone.
        json.dumps(filters, default=str, sort_keys=True),
    )
