"""What the four cacheable read endpoints let a client keep, and for how long.

Each of these answers is derived from tables no request writes, and each is already held in
process for a few minutes (``backend/core/cache.py``). The header is the second half of
that: without it the browser re-asks for the directory's filter bar and the whole Sankey on
every navigation, and the in-process cache only makes the answer cheap to repeat rather
than unnecessary to ask for.

The three behind a bearer token say ``private``, so no shared cache may keep a copy of a
per-caller answer; the companies list, the one list on the platform with no authentication
at all, says ``public`` and varies on ``Origin``. A directive flipped the wrong way is
invisible in every functional test and is a correctness problem in somebody's CDN, which is
why it is pinned here.

No database: the services are replaced through FastAPI's dependency overrides, because what
is under test is the header the route sets and not the rows behind it.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.core.app import create_app
from backend.core.page import PageResult
from backend.core.settings import reset_settings_caches
from backend.identity.api.deps import get_current_principal
from backend.identity.domain import Account, Principal
from backend.jobboard.api.deps import get_company_service
from backend.jobboard.application.company_service import COMPANIES_TTL_SECONDS
from backend.members.api.deps import get_member_service
from backend.members.application.member_service import FACETS_TTL_SECONDS
from backend.members.application.ports import Facets
from backend.paths.api.deps import build_path_service
from backend.paths.application.path_service import FLOW_TTL_SECONDS, GROUPS_TTL_SECONDS
from backend.paths.domain import PathFlow

SECRET = "unit-test-secret-at-least-32-bytes-long"

COMPANIES = "/api/v1/companies/"
FACETS = "/api/v1/members/facets"
FLOW = "/api/v1/paths/flow"
GROUPS = "/api/v1/paths/groups"


class _Companies:
    async def list_companies(self, *, skip: int, limit: int, filters: object) -> PageResult:
        return PageResult(items=[], total=0)


class _Members:
    async def facets(self) -> Facets:
        return Facets(classes=(), majors=(), members_total=0)


class _Paths:
    async def flow(self, filters: object) -> PathFlow:
        return PathFlow(members_counted=0)

    async def groups(self) -> dict[str, list[str]]:
        return {"study": [], "first_step": [], "current": [], "intent": []}


def _principal() -> Principal:
    now = datetime.now(UTC)
    return Principal(
        account=Account(
            id=uuid4(),
            auth_user_id=uuid4(),
            email="reader@cdtm.com",
            created_at=now,
            updated_at=now,
        )
    )


@pytest.fixture(autouse=True)
def _fresh_settings() -> Iterator[None]:
    reset_settings_caches()
    yield
    reset_settings_caches()


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """The real application, with the four services and the sign-in replaced.

    A complete environment is set explicitly so no developer's ``.env`` decides the prefix
    these URLs are asserted against. The lifespan is never entered: nothing here needs the
    database, and its shutdown hook disposes the engine the integration suite holds open.
    """
    for key, value in {
        "APP_ENVIRONMENT": "development",
        "APP_API_PREFIX": "/api/v1",
        "APP_CORS_ORIGINS": "http://localhost:3000",
        "AUTH_DEV_LOGIN_ENABLED": "false",
        "SUPABASE_JWT_SECRET": SECRET,
        "STORAGE_BACKEND": "local",
    }.items():
        monkeypatch.setenv(key, value)
    reset_settings_caches()

    app: FastAPI = create_app()
    app.dependency_overrides[get_company_service] = lambda: _Companies()
    app.dependency_overrides[get_member_service] = lambda: _Members()
    app.dependency_overrides[build_path_service] = lambda: _Paths()
    app.dependency_overrides[get_current_principal] = _principal
    return TestClient(app, raise_server_exceptions=False)


# ---- the public one -----------------------------------------------------------------------


def test_the_companies_list_may_be_held_by_a_shared_cache(client: TestClient) -> None:
    """No authentication dependency at all on this route, so the answer really is the same
    for everybody and a CDN in front of the API may keep one copy for all of them."""
    response = client.get(COMPANIES)

    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == f"public, max-age={COMPANIES_TTL_SECONDS}"


def test_the_companies_list_varies_on_origin(client: TestClient) -> None:
    """CORS adds ``Access-Control-Allow-Origin`` only when the request carried an ``Origin``,
    so one URL has two sets of headers. Cached without this, the copy a server-side fetch
    made gets replayed to a browser, which then refuses data it is allowed to read."""
    response = client.get(COMPANIES)

    varies_on = {v.strip().lower() for v in response.headers["vary"].split(",")}
    assert "origin" in varies_on


def test_the_advertised_lifetime_is_the_one_the_server_holds_it_for(client: TestClient) -> None:
    """The header and the in-process cache are two halves of one decision: a browser told to
    keep the list longer than the server does would show a company that was just edited."""
    assert COMPANIES_TTL_SECONDS == 300
    assert f"max-age={COMPANIES_TTL_SECONDS}" in client.get(COMPANIES).headers["cache-control"]


# ---- the three behind a token ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("url", "ttl"),
    [
        (FACETS, FACETS_TTL_SECONDS),
        (FLOW, FLOW_TTL_SECONDS),
        (GROUPS, GROUPS_TTL_SECONDS),
    ],
)
def test_an_authenticated_read_is_cacheable_only_by_the_browser_that_asked(
    client: TestClient, url: str, ttl: int
) -> None:
    """``private``, never ``public``: these routes are behind a bearer token, and a shared
    cache holding one caller's answer is how a signed-in view reaches somebody else. The
    answer happens to be the same for everybody today, which is not a property a cache
    directive may be written against."""
    response = client.get(url, headers={"Authorization": "Bearer stub"})

    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == f"private, max-age={ttl}"


@pytest.mark.parametrize("url", [FACETS, FLOW, GROUPS])
def test_none_of_the_authenticated_reads_says_public(client: TestClient, url: str) -> None:
    directives = client.get(url, headers={"Authorization": "Bearer stub"}).headers["cache-control"]
    assert "public" not in directives


def test_the_sankey_and_its_group_names_expire_on_their_own_schedules(
    client: TestClient,
) -> None:
    """The group names change only when the classifier reruns and the flow changes with any
    member edit, so they are deliberately not the same number."""
    assert (FLOW_TTL_SECONDS, GROUPS_TTL_SECONDS) == (300, 600)
