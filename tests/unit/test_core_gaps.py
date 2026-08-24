"""Small core helpers every context leans on: paging defaults, the DB dump, the shared
phrase helpers and the limits on a question.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import AnyUrl, BaseModel

from backend.core.actor import Actor
from backend.core.api.pagination import PageParams, page_params
from backend.core.exceptions import ForbiddenError, ValidationError
from backend.core.llm.ask import (
    MAX_QUESTION_LENGTH,
    MIN_QUESTION_LENGTH,
    summary_language_rule,
    validate_question,
)
from backend.core.llm.phrases import city_in, looks_like_a_name, normalise, split_clauses
from backend.core.mapping import dump_for_db


class _Row(BaseModel):
    name: str
    url: AnyUrl | None = None
    price: Decimal | None = None
    starts_on: date | None = None


# ---- paging ------------------------------------------------------------------------------


def test_a_caller_who_asks_for_no_page_gets_the_first_one() -> None:
    # The defaults are the contract for every list endpoint: start at the beginning, and
    # hand back a page small enough to render.
    assert page_params() == PageParams(skip=0, limit=20)


def test_the_page_a_caller_asks_for_is_the_page_they_get() -> None:
    assert page_params(skip=40, limit=5) == PageParams(skip=40, limit=5)


# ---- dumping a model for the database --------------------------------------------------


def test_every_field_is_written_including_the_ones_left_unset() -> None:
    # A partial update passes exclude_unset; a full write must not silently skip columns.
    assert dump_for_db(_Row(name="anna")) == {
        "name": "anna",
        "url": None,
        "price": None,
        "starts_on": None,
    }


def test_only_the_fields_that_were_set_are_written_when_asked() -> None:
    assert dump_for_db(_Row(name="anna"), exclude_unset=True) == {"name": "anna"}


def test_urls_are_flattened_to_text_and_other_types_are_left_for_the_driver() -> None:
    row = _Row(
        name="anna",
        url="https://example.test/a",
        price=Decimal("12.50"),
        starts_on=date(2026, 5, 1),
    )
    data = dump_for_db(row)
    assert data["url"] == "https://example.test/a"
    assert isinstance(data["url"], str)
    # Decimal and date are what psycopg and asyncpg want; JSON mode would stringify them.
    assert data["price"] == Decimal("12.50")
    assert data["starts_on"] == date(2026, 5, 1)


# ---- the phrases the keyword translators share ------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Anna Test", True),
        # Three words is still a name: "Jane Q Public", "Bosch Rexroth Group".
        ("Jane Q Public", True),
        ("Anna", False),
        ("who works in munich now", False),
        ("Anna 2 Test", False),
    ],
)
def test_two_or_three_plain_words_read_as_a_name(text: str, expected: bool) -> None:
    assert looks_like_a_name(text) is expected


def test_a_city_is_recognised_by_its_longest_spelling() -> None:
    assert city_in("who lives in new york") == "New York"
    assert city_in("wer wohnt in münchen") == "Munich"
    assert city_in("nobody here") is None


def test_a_question_is_stripped_of_its_lead_in() -> None:
    # Every lead-in is stripped, not just the first: "show me", "people" and "who" all go.
    assert normalise("Show me people who work in Berlin?") == "work in berlin"
    assert split_clauses("anna, ben and cara") == ["anna", "ben", "cara"]


# ---- what counts as a question ----------------------------------------------------------


def test_a_question_at_the_shortest_allowed_length_is_accepted() -> None:
    validate_question("a" * MIN_QUESTION_LENGTH)
    validate_question("  " + "a" * MIN_QUESTION_LENGTH + "  ")


def test_a_question_one_character_short_is_refused() -> None:
    with pytest.raises(ValidationError):
        validate_question("a" * (MIN_QUESTION_LENGTH - 1))


def test_a_question_at_the_longest_allowed_length_is_accepted() -> None:
    validate_question("a" * MAX_QUESTION_LENGTH)


def test_a_question_one_character_too_long_is_refused() -> None:
    with pytest.raises(ValidationError):
        validate_question("a" * (MAX_QUESTION_LENGTH + 1))


def test_the_summary_language_is_named_when_the_caller_asked_for_one() -> None:
    rule = summary_language_rule("de")
    assert "de" in rule
    assert rule.startswith("Write `summary` in")


def test_without_a_language_the_model_answers_in_the_one_it_was_asked_in() -> None:
    rule = summary_language_rule(None)
    assert rule.startswith("Write `summary` in the language the question is written in")
    assert "English" in rule


# ---- who is acting -----------------------------------------------------------------------


def test_an_actor_is_not_an_admin_unless_it_is_said_so() -> None:
    # Every real call site passes the flag from the Principal; the default is what a test
    # helper or a future caller gets, and it has to be the safe one.
    actor = Actor(uuid4())
    assert actor.is_admin is False
    assert Actor(uuid4(), True).is_admin is True


def test_an_account_with_no_member_entry_cannot_act_as_one() -> None:
    member_id = uuid4()
    assert Actor(member_id).require_member() == member_id
    with pytest.raises(ForbiddenError):
        Actor(None).require_member()
