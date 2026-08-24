"""The one log line per asked question.

It is read with grep (``docs/ask.md``), so its shape is a contract: the same question asked
twice has to produce the same bytes, whatever order the filter dictionary happens to be
built in, and a filter value that is not JSON has to be rendered rather than crash the
request it was logging.
"""

from __future__ import annotations

import logging
from datetime import date

import pytest

from backend.core.llm.observability import log_ask

LOGGER = "backend.ask"


def _line(caplog: pytest.LogCaptureFixture, **overrides: object) -> str:
    call: dict = {
        "board": "members",
        "actor": "member-1",
        "question_length": 42,
        "source": "llm",
        "model": "claude-test",
        "latency_ms": 7,
        "filters": {"school": "TUM", "company": "Bosch", "since": date(2026, 1, 2)},
        "total": 3,
        "unresolved": ["quantum"],
    }
    call.update(overrides)
    caplog.clear()
    with caplog.at_level(logging.INFO, logger=LOGGER):
        log_ask(**call)
    records = [r for r in caplog.records if r.name == LOGGER]
    assert len(records) == 1
    return records[0].getMessage()


def test_the_line_carries_every_fact_a_reader_counts_on(caplog: pytest.LogCaptureFixture) -> None:
    assert _line(caplog) == (
        "ask board=members actor=member-1 question_length=42 source=llm model=claude-test "
        'latency_ms=7 total=3 unresolved=["quantum"] '
        'filters={"company": "Bosch", "school": "TUM", "since": "2026-01-02"}'
    )


def test_two_identical_questions_produce_identical_bytes(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Same filters, different insertion order: sorted keys are what makes the two lines
    # countable as one.
    first = _line(caplog, filters={"school": "TUM", "company": "Bosch"})
    second = _line(caplog, filters={"company": "Bosch", "school": "TUM"})
    assert first == second
    assert 'filters={"company": "Bosch", "school": "TUM"}' in first


def test_a_missing_model_and_an_uncounted_result_read_as_a_dash(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # The keyword translator answers with no model, and an explain call counts no rows.
    line = _line(caplog, model="", total=None)
    assert "model=- " in line
    assert " total=- " in line


def test_a_filter_value_that_is_not_json_is_rendered_rather_than_raised(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Dates and UUIDs land in filters all the time; logging must never be what fails a request.
    line = _line(caplog, filters={"today": date(2026, 5, 1)})
    assert 'filters={"today": "2026-05-01"}' in line
