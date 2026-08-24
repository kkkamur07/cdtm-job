"""What the calendar's list query actually asks Postgres for.

``GET /events/`` answers with ``EventSummaryPublic``, which has no ``description``. That is
worth nothing if the query still fetches one, so the list selects the stored columns of a
row plus the three counted ones and leaves the aggregate to ``GET /events/{event_id}``.

The statement is compiled rather than executed, so this costs no database.
"""

from __future__ import annotations

from uuid import uuid4

from backend.events.domain import EventSummary
from backend.events.infrastructure.events_repository import (
    _COUNTED,
    SqlEventRepository,
    _summary_select,
)


def _selected(stmt) -> list[str]:
    return list(stmt.selected_columns.keys())


def test_the_list_query_selects_a_calendar_row_and_the_counts_and_no_more() -> None:
    """The counted three are labelled subqueries, so they arrive under their own names."""
    for viewer in (None, uuid4()):
        stmt = _summary_select(viewer)

        assert _selected(stmt) == [
            *(f for f in EventSummary.model_fields if f not in _COUNTED),
            "going",
            "interested",
            "mine",
        ]
        assert "description" not in str(stmt)


def test_reading_one_event_still_asks_for_the_whole_aggregate() -> None:
    """The detail read draws the description, so its query must keep selecting it."""
    stmt = SqlEventRepository(None)._with_counts(None)

    assert "events.description" in str(stmt)
