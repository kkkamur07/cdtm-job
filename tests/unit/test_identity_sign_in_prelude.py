"""When a sign-in writes to ``accounts``, and when it does not.

``upsert_from_claims`` runs before every authenticated request, so what it decides to write
is the fixed cost of the whole API. It used to UPDATE, COMMIT and refresh unconditionally,
which made every GET a row write. The rule now is: write when the token says something new,
or when ``last_sign_in_at`` has gone stale past ``AUTH_SIGN_IN_TOUCH_SECONDS``.

The session is a fake rather than a live one because the assertion is about *statements
issued*, and counting commits on a stub is a more direct statement of that than reading an
echo log.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from backend.identity.domain import TokenClaims
from backend.identity.infrastructure.account_repository import SqlAccountRepository
from backend.identity.infrastructure.orm_models import AccountRow

SUBJECT = uuid.UUID("11111111-1111-1111-1111-111111111111")
EMAIL = "person@cdtm.com"
TOUCH_SECONDS = 900


class _FakeSession:
    """The four things ``upsert_from_claims`` asks a session for, and a tally of them."""

    def __init__(self, row: AccountRow | None) -> None:
        self._row = row
        self.commits = 0
        self.refreshes = 0
        self.added: list[AccountRow] = []

    async def scalar(self, statement: object) -> AccountRow | None:
        return self._row

    def add(self, row: AccountRow) -> None:
        self.added.append(row)
        self._row = row

    async def commit(self) -> None:
        self.commits += 1

    async def refresh(self, row: AccountRow) -> None:
        self.refreshes += 1
        # What the round trip is actually for: id, created_at and updated_at are server
        # defaults, so they hold nothing until Postgres has been asked.
        now = datetime.now(UTC)
        row.id = row.id or uuid.uuid4()
        row.created_at = row.created_at or now
        row.updated_at = row.updated_at or now


def _row(*, last_sign_in_at: datetime | None, **overrides: object) -> AccountRow:
    now = datetime.now(UTC)
    row = AccountRow(
        auth_user_id=SUBJECT,
        email=EMAIL,
        full_name="A Person",
        avatar_url="https://cdn.example.com/a.png",
        is_admin=False,
        last_sign_in_at=last_sign_in_at,
    )
    row.id = uuid.uuid4()
    row.member_id = None
    row.created_at = now
    row.updated_at = now
    for name, value in overrides.items():
        setattr(row, name, value)
    return row


def _claims(**overrides: object) -> TokenClaims:
    base: dict[str, object] = {
        "sub": SUBJECT,
        "email": EMAIL,
        "email_verified": True,
        "full_name": "A Person",
        "avatar_url": "https://cdn.example.com/a.png",
        "provider": "google",
    }
    base.update(overrides)
    return TokenClaims(**base)


def _repo(session: _FakeSession) -> SqlAccountRepository:
    return SqlAccountRepository(session, sign_in_touch_seconds=TOUCH_SECONDS)  # type: ignore[arg-type]


async def test_a_repeat_request_with_nothing_new_to_say_writes_nothing() -> None:
    """The whole point. A page load is a dozen authenticated GETs and none of them has any
    business taking a row lock on ``accounts`` or generating WAL."""
    row = _row(last_sign_in_at=datetime.now(UTC) - timedelta(seconds=60))
    session = _FakeSession(row)

    account = await _repo(session).upsert_from_claims(_claims(), is_admin=None)

    assert session.commits == 0
    assert session.refreshes == 0
    assert account.email == EMAIL


async def test_a_sign_in_after_the_touch_window_records_the_new_time() -> None:
    """``last_sign_in_at`` is what the admin worklist orders by, so it still has to move;
    it just does not have to move on every single request."""
    stale = datetime.now(UTC) - timedelta(seconds=TOUCH_SECONDS + 1)
    row = _row(last_sign_in_at=stale)
    session = _FakeSession(row)

    account = await _repo(session).upsert_from_claims(_claims(), is_admin=None)

    assert session.commits == 1
    assert account.last_sign_in_at is not None
    assert account.last_sign_in_at > stale


async def test_an_account_that_has_never_signed_in_is_touched() -> None:
    """A null column is not "recent"; a row can reach this state through the loader or an
    admin insert, and it must not stay null forever."""
    session = _FakeSession(_row(last_sign_in_at=None))

    account = await _repo(session).upsert_from_claims(_claims(), is_admin=None)

    assert session.commits == 1
    assert account.last_sign_in_at is not None


@pytest.mark.parametrize(
    ("claim", "value"),
    [
        ("email", "renamed@cdtm.com"),
        ("full_name", "Renamed Person"),
        ("avatar_url", "https://cdn.example.com/b.png"),
    ],
)
async def test_a_changed_claim_is_written_through_even_inside_the_touch_window(
    claim: str, value: str
) -> None:
    """Someone who changes their Workspace surname or their Google picture sees it on the
    next request, not up to fifteen minutes later."""
    session = _FakeSession(_row(last_sign_in_at=datetime.now(UTC) - timedelta(seconds=1)))

    account = await _repo(session).upsert_from_claims(_claims(**{claim: value}), is_admin=None)

    assert session.commits == 1
    assert getattr(account, claim) == value


async def test_the_admin_bootstrap_still_promotes_on_the_next_request() -> None:
    """``AUTH_ADMIN_EMAILS`` is how the first admin exists at all. Adding an address there
    and restarting has to take effect on that person's next request."""
    session = _FakeSession(_row(last_sign_in_at=datetime.now(UTC) - timedelta(seconds=1)))

    account = await _repo(session).upsert_from_claims(_claims(), is_admin=True)

    assert session.commits == 1
    assert account.is_admin is True


async def test_an_account_that_is_already_admin_is_not_rewritten() -> None:
    """Every request from an admin would otherwise be a write, which is the same bug one
    flag over."""
    row = _row(last_sign_in_at=datetime.now(UTC) - timedelta(seconds=1), is_admin=True)
    session = _FakeSession(row)

    await _repo(session).upsert_from_claims(_claims(), is_admin=True)

    assert session.commits == 0


async def test_a_token_that_carries_no_display_fields_does_not_erase_them() -> None:
    """Claims are the source for name and avatar only when they are there. A token minted
    without them must not blank the columns, and must not count as a change either."""
    row = _row(last_sign_in_at=datetime.now(UTC) - timedelta(seconds=1))
    session = _FakeSession(row)

    account = await _repo(session).upsert_from_claims(
        _claims(full_name=None, avatar_url=None), is_admin=None
    )

    assert session.commits == 0
    assert account.full_name == "A Person"
    assert account.avatar_url == "https://cdn.example.com/a.png"


async def test_the_first_sign_in_still_inserts_the_row() -> None:
    """No account yet is the one case that must write. The refresh stays on this path only:
    ``created_at`` and ``updated_at`` are server defaults, so they are not loaded otherwise,
    and it is paid once per account rather than once per request."""
    session = _FakeSession(None)

    account = await _repo(session).upsert_from_claims(_claims(), is_admin=None)

    assert session.commits == 1
    assert session.refreshes == 1
    assert len(session.added) == 1
    assert account.auth_user_id == SUBJECT
    assert account.last_sign_in_at is not None
