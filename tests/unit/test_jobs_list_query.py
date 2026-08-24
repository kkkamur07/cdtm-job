"""What the job board's list query actually asks Postgres for.

``GET /jobs/`` answers with ``JobSummaryPublic``, which has no ``description``. That is
worth nothing if the query still fetches one: ``description`` is capped at
``MAX_RICH_TEXT`` (twenty thousand characters) and a page is a hundred rows, so a
``select(JobRow)`` behind a summary response is up to two megabytes pulled across the link
and validated into a full ``Job`` for nothing.

The statement is compiled rather than executed, so this costs no database.
"""

from __future__ import annotations

from backend.jobboard.application.ports import JobFilters
from backend.jobboard.domain import JobSummary
from backend.jobboard.infrastructure.job_repository import SqlJobRepository, _summary_select


def _selected(stmt) -> list[str]:
    return list(stmt.selected_columns.keys())


def test_the_list_query_selects_the_summary_columns_and_no_others() -> None:
    stmt = _summary_select()

    assert _selected(stmt) == list(JobSummary.model_fields)
    assert "description" not in str(stmt)


def test_searching_the_description_still_never_selects_it() -> None:
    """``?q=`` matches on the description, which is a WHERE clause, not a column to return.

    Written as its own case because the two are easy to conflate: a test that only looked
    for the word "description" anywhere in the SQL would fail here for the right reason and
    pass for the wrong one once somebody dropped the predicate.
    """
    stmt = SqlJobRepository(None)._apply(_summary_select(), JobFilters(q="python"))

    assert "lower(jobs.description) LIKE" in str(stmt)
    assert "description" not in _selected(stmt)
