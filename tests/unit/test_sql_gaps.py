"""The one SQL fragment every board shares: "contains this term", wildcards and all.

A member may type ``%`` or ``_`` into any search box. Both are LIKE wildcards, so they
have to reach Postgres escaped or the search quietly matches every row.
"""

from __future__ import annotations

from backend.core.sql import ilike_contains


def test_a_plain_term_is_wrapped_in_wildcards() -> None:
    assert ilike_contains("munich") == "%munich%"


def test_percent_is_escaped_so_it_matches_a_literal_percent() -> None:
    assert ilike_contains("100%") == "%100\\%%"


def test_underscore_is_escaped_so_it_matches_a_literal_underscore() -> None:
    # Unescaped, "_" is LIKE's single-character wildcard: "a_c" would match "abc".
    assert ilike_contains("a_c") == "%a\\_c%"


def test_a_backslash_is_escaped_first_so_the_escape_itself_stays_literal() -> None:
    # Escaping "%" before "\" would turn the user's own backslash into an escape character.
    assert ilike_contains("a\\b") == "%a\\\\b%"


def test_every_wildcard_in_one_term_is_escaped() -> None:
    assert ilike_contains("50%\\_x") == "%50\\%\\\\\\_x%"


def test_a_term_that_is_only_wildcards_cannot_become_a_match_all_pattern() -> None:
    assert ilike_contains("%") == "%\\%%"
    assert ilike_contains("_") == "%\\_%"
