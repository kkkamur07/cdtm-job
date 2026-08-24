"""Cross-cutting core behaviour against the real app and a real Postgres.

Three things live here that no domain test can prove: the Ask spend ceiling is counted in
the database rather than in one worker's memory, a search term that is a LIKE wildcard
matches literally, and the error envelope carries a message and details, not just a code.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from backend.core.llm import quota
from backend.core.llm.quota import SqlQuestionMeter
from backend.core.settings import get_database_settings
from tests.integration.conftest import insert_member

pytestmark = pytest.mark.integration
API = "/api/v1/members"


class _AlwaysAllows:
    """Stands in for the in-process fallback bucket, so only the SQL meter can refuse.

    The two limiters enforce the same ceiling, which is why a broken UPSERT is invisible in
    the HTTP tests: the bucket refuses in its place. Made permissive here, every refusal
    below has to have come from the row in ``ask_quota``.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    def allow(self, key: str, *, rate_per_minute: int) -> bool:
        self.calls.append((key, rate_per_minute))
        return True


@pytest.fixture
def durable_only(monkeypatch: pytest.MonkeyPatch) -> _AlwaysAllows:
    fallback = _AlwaysAllows()
    monkeypatch.setattr(quota, "ask_limiter", fallback)
    return fallback


async def _session() -> AsyncSession:
    engine = create_async_engine(get_database_settings().async_url, poolclass=None)
    return AsyncSession(engine)


async def test_the_question_ceiling_is_enforced_by_the_row_in_the_database(
    client: TestClient, durable_only: _AlwaysAllows
) -> None:
    session = await _session()
    try:
        meter = SqlQuestionMeter(session)
        answers = [await meter.allow("member-1", rate_per_minute=2) for _ in range(3)]
        assert answers == [True, True, False]

        counted = await session.scalar(
            text("select asked from ask_quota where member_key = :k"), {"k": "member-1"}
        )
        assert counted == 3
        # The fallback never had to decide anything: the database did.
        assert durable_only.calls == []
    finally:
        await session.close()
        await session.bind.dispose()


async def test_the_count_is_kept_per_caller_and_per_minute(
    client: TestClient, durable_only: _AlwaysAllows
) -> None:
    session = await _session()
    try:
        meter = SqlQuestionMeter(session)
        assert await meter.allow("member-1", rate_per_minute=1) is True
        assert await meter.allow("member-1", rate_per_minute=1) is False
        # A second caller starts with their own full allowance.
        assert await meter.allow("member-2", rate_per_minute=1) is True

        rows = (
            await session.execute(
                text("select member_key, asked from ask_quota order by member_key")
            )
        ).all()
        assert [tuple(r) for r in rows] == [("member-1", 2), ("member-2", 1)]

        # A stale window is a fresh allowance, not an accumulated one.
        await session.execute(
            text("update ask_quota set window_start = now() - interval '5 minutes'")
        )
        await session.commit()
        assert await meter.allow("member-1", rate_per_minute=1) is True
        counted = await session.scalar(
            text("select asked from ask_quota where member_key = :k"), {"k": "member-1"}
        )
        assert counted == 1
    finally:
        await session.close()
        await session.bind.dispose()


def test_a_wildcard_in_the_search_box_matches_itself(client: TestClient, member_anna: dict) -> None:
    insert_member("cotton-test", "Cotton 100% Test")
    insert_member("deep-test", "Deep_Learning Test")
    h = member_anna["headers"]

    # "%" is LIKE's match-anything; escaped, it can only find the member who has one.
    r = client.get(f"{API}/", params={"q": "%"}, headers=h)
    assert r.status_code == 200, r.text
    assert [m["slug"] for m in r.json()["items"]] == ["cotton-test"]

    # "_" is LIKE's match-one-character; escaped, it finds only the underscore.
    r = client.get(f"{API}/", params={"q": "_"}, headers=h)
    assert [m["slug"] for m in r.json()["items"]] == ["deep-test"]

    # And a term that is only a backslash matches nobody rather than erroring.
    r = client.get(f"{API}/", params={"q": "\\"}, headers=h)
    assert r.status_code == 200
    assert r.json()["items"] == []


def test_the_error_envelope_carries_a_readable_message(
    client: TestClient, member_anna: dict
) -> None:
    r = client.get(f"{API}/no-such-member", headers=member_anna["headers"])
    assert r.status_code == 404
    error = r.json()["error"]
    assert error["code"] == "not_found"
    # A code alone is not an answer: the envelope carries a message the UI can show, and it
    # is not the identifier repeated back.
    assert isinstance(error["message"], str)
    assert error["message"].strip() != ""
    assert error["message"] != error["code"]
    assert "details" not in error


def test_a_validation_error_says_which_field_was_wrong(
    client: TestClient, member_anna: dict
) -> None:
    r = client.get(f"{API}/", params={"class_id": "not-a-number"}, headers=member_anna["headers"])
    assert r.status_code == 422
    error = r.json()["error"]
    assert error["code"] == "validation_error"
    assert error["message"]
    errors = error["details"]["errors"]
    assert errors, error
    assert any("class_id" in str(item.get("loc", "")) for item in errors)


def test_an_unauthenticated_call_is_told_so_in_words(client: TestClient) -> None:
    r = client.get(f"{API}/")
    assert r.status_code == 401
    error = r.json()["error"]
    assert error["code"] == "unauthorized"
    assert error["message"] != error["code"]
    assert error["ref"] == r.headers["X-Error-ID"]
