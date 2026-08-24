"""What the housing board's list query actually asks Postgres for.

``GET /housing/`` answers with ``HousingListingSummaryPublic``, which has no
``description``. That is worth nothing if the query still fetches one: the field is capped
at twenty thousand characters on the way in and a page is a hundred cards, so a
``select(HousingListingRow)`` behind a card response is a page of prose per card pulled
across the link for nothing.

The statement is compiled rather than executed, so this costs no database.
"""

from __future__ import annotations

from backend.housing.application.ports import HousingFilters
from backend.housing.domain import HousingListingSummary
from backend.housing.infrastructure.housing_repository import (
    SqlHousingRepository,
    _summary_select,
)


def _selected(stmt) -> list[str]:
    return list(stmt.selected_columns.keys())


def test_the_list_query_selects_the_card_columns_and_no_others() -> None:
    stmt = _summary_select()

    assert _selected(stmt) == list(HousingListingSummary.model_fields)
    assert "description" not in str(stmt)


def test_the_filters_that_read_the_description_still_never_select_it() -> None:
    """``q`` and the furnished fallback both match on the description.

    Both are WHERE clauses, not columns to return, and the distinction is easy to conflate:
    a test that only looked for the word "description" anywhere in the SQL would fail here
    for the right reason and pass for the wrong one once somebody dropped the predicate.
    """
    repo = SqlHousingRepository(None)
    for filters in (HousingFilters(q="schwabing"), HousingFilters(furnished=True)):
        stmt = repo._apply(_summary_select(), filters)

        assert "lower(housing_listings.description) LIKE" in str(stmt)
        assert "description" not in _selected(stmt)
