"""What a shared cache is allowed to do with ``GET /companies``, and what a caller may send.

The company list is the one route on the platform with no auth dependency at all, which is
why it is the one route that answers ``Cache-Control: public``. Public means a proxy may
keep it and hand it to somebody else, and that only stays correct if the answer says which
request headers it depends on. CORS puts ``Access-Control-Allow-Origin`` on it only when the
request carried an ``Origin``, so without ``Vary: Origin`` a browser could be served the
copy a server-to-server call made and then refuse to read its own data.

The length caps at the bottom are the second half of the same reading: every one of these
values becomes an ILIKE pattern, and the ones that were capped and the ones that were not
had nothing to do with how expensive they are. ``?skill=`` on the directory is here rather
than with the other member tests because it is the same finding and the same fix.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration
API = "/api/v1/companies/"

#: The one origin the test settings allow, so CORS actually answers rather than staying quiet.
ALLOWED_ORIGIN = "http://localhost:3000"


def _vary(response) -> set[str]:
    return {v.strip().casefold() for v in response.headers.get("vary", "").split(",") if v.strip()}


def test_the_public_company_list_varies_on_origin(client: TestClient) -> None:
    plain = client.get(API)
    assert plain.status_code == 200, plain.text
    assert plain.headers["cache-control"] == "public, max-age=300"
    # No Origin was sent, so CORS added no allow header, and the answer says so.
    assert "access-control-allow-origin" not in plain.headers
    assert "origin" in _vary(plain)

    from_a_browser = client.get(API, headers={"Origin": ALLOWED_ORIGIN})
    assert from_a_browser.status_code == 200
    assert from_a_browser.headers["access-control-allow-origin"] == ALLOWED_ORIGIN
    # Same URL, a different set of headers: the two must not share a cache entry.
    assert "origin" in _vary(from_a_browser)


def test_the_vary_header_keeps_whatever_else_already_varied(client: TestClient) -> None:
    """Appended, not assigned. Compression varies the same answer on Accept-Encoding.

    Clobbering that would let a proxy hand a gzipped body to a client that cannot read one,
    which is the same class of bug as the missing Origin, one layer down.
    """
    r = client.get(API, headers={"Origin": ALLOWED_ORIGIN, "Accept-Encoding": "gzip"})
    assert r.status_code == 200
    assert "origin" in _vary(r)
    assert _vary(r) >= {"origin"}
    # Nothing was dropped: every value is still a single well-formed token list.
    assert all(v for v in _vary(r))


@pytest.mark.parametrize("field", ["industry", "hq_city", "q"])
def test_a_filter_longer_than_the_cap_is_refused_before_it_reaches_a_query(
    client: TestClient, field: str
) -> None:
    """Each of these becomes an ILIKE pattern over every company row.

    ``q`` was capped and the other two were not, so the cheapest way to make the database
    do a lot of work was to send a megabyte-long ``?industry=``.
    """
    assert client.get(API, params={field: "x" * 128}).status_code == 200
    assert client.get(API, params={field: "x" * 129}).status_code == 422


def test_the_directory_caps_a_skill_by_length_and_by_how_many(
    client: TestClient, member_anna: dict
) -> None:
    """``?skill=`` is repeatable and each value is matched against every member's skills.

    Neither half was bounded: one megabyte-long value, or ten thousand short ones, and a
    single query string turned into that much pattern matching over the whole directory.
    """
    headers = member_anna["headers"]
    members = "/api/v1/members/"

    assert client.get(members, params={"skill": ["Python"]}, headers=headers).status_code == 200
    assert client.get(members, params={"skill": ["x" * 128]}, headers=headers).status_code == 200
    assert client.get(members, params={"skill": ["x" * 129]}, headers=headers).status_code == 422

    assert (
        client.get(members, params={"skill": [f"s{i}" for i in range(20)]}, headers=headers)
    ).status_code == 200
    assert (
        client.get(members, params={"skill": [f"s{i}" for i in range(21)]}, headers=headers)
    ).status_code == 422
