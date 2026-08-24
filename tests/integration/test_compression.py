"""Responses are compressed on the wire.

Measured before this existed: ``size_download`` was byte-identical with and without
``Accept-Encoding: gzip`` on every endpoint, because nothing in the stack compressed
anything. The list routes ship tens of kilobytes of JSON each - a members page is around
60 KB, the companies list around 49 KB - over the public internet, on every request, and
JSON compresses five to ten times over.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from tests.integration.conftest import auth, insert_member

pytestmark = pytest.mark.integration

MEMBERS = "/api/v1/members/"


def test_a_large_json_response_comes_back_gzipped(client: TestClient) -> None:
    for i in range(40):
        insert_member(f"gzip-{i}", f"Compressible Person Number {i}", f"gzip-{i}@cdtm.com")

    response = client.get(
        MEMBERS,
        params={"limit": 40},
        headers={**auth("reader@cdtm.com"), "Accept-Encoding": "gzip"},
    )

    assert response.status_code == 200, response.text
    assert response.headers["content-encoding"] == "gzip"
    # The client decodes transparently, so what arrived is still the whole document; the
    # header is the only place the saving is visible from here.
    body = response.json()
    assert body["total"] == 40
    assert int(response.headers["content-length"]) < len(json.dumps(body))


def test_a_client_that_does_not_ask_for_it_is_not_given_it(client: TestClient) -> None:
    """``identity`` is the correct answer to a request with no ``Accept-Encoding``, and a
    client that cannot decode gzip must not be handed gzip."""
    for i in range(40):
        insert_member(f"plain-{i}", f"Compressible Person Number {i}", f"plain-{i}@cdtm.com")

    response = client.get(
        MEMBERS,
        params={"limit": 40},
        headers={**auth("reader@cdtm.com"), "Accept-Encoding": "identity"},
    )

    assert response.status_code == 200, response.text
    assert "content-encoding" not in response.headers


def test_a_small_response_is_left_alone(client: TestClient) -> None:
    """Below the minimum size the gzip header and trailer cost more than they save, and the
    CPU spent compressing is on the same event loop that answers everything else."""
    response = client.get("/health", headers={"Accept-Encoding": "gzip"})

    assert response.status_code == 200, response.text
    assert len(response.content) < 1000
    assert "content-encoding" not in response.headers


def test_compression_does_not_cost_the_security_headers(client: TestClient) -> None:
    """The guards run inside the compressor, so the headers are set on the response before
    anything touches the body. A compressed response is still a hardened one."""
    for i in range(40):
        insert_member(f"hardened-{i}", f"Compressible Person Number {i}", f"hardened-{i}@cdtm.com")

    response = client.get(
        MEMBERS,
        params={"limit": 40},
        headers={**auth("reader@cdtm.com"), "Accept-Encoding": "gzip"},
    )

    assert response.headers["content-encoding"] == "gzip"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
