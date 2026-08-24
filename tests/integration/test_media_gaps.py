"""Media behaviour the local adapter's incidental answers hide.

``test_media.py`` already asks for an unknown bucket and gets a 404, but only because there
is no such directory on disk. These put a real object where the caller points and configure a
base URL with a trailing slash, so the allow-list and the URL normalisation are the things
actually being observed.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.core.settings import get_storage_settings, reset_settings_caches

pytestmark = pytest.mark.integration

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def _upload(client: TestClient, headers: dict) -> dict:
    response = client.post(
        "/api/v1/media/job-image",
        files={"file": ("a.png", PNG, "image/png")},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_a_bucket_outside_the_allow_list_is_refused_even_when_the_object_is_there(
    client: TestClient, member_anna: dict, admin_headers: dict
) -> None:
    """The bucket name arrives straight off the URL and the allow-list is the only thing
    scoping it. On the production Supabase backend every bucket in the project is reachable
    with the same credentials, so an object that exists under an unlisted name must still be
    refused: it is the list that says no, not the storage happening to come up empty."""
    key = _upload(client, member_anna["headers"])["key"]
    root = Path(get_storage_settings().local_dir).expanduser().resolve()
    (root / "secrets").mkdir(parents=True, exist_ok=True)
    (root / "secrets" / key).write_bytes(PNG)

    assert client.get(f"/api/v1/media/secrets/{key}").status_code == 404

    # And the admin-only delete is scoped the same way, so the object is still there.
    assert client.delete(f"/api/v1/media/secrets/{key}", headers=admin_headers).status_code == 404
    assert (root / "secrets" / key).exists()


def test_the_stored_url_is_built_from_the_configured_public_base(
    client: TestClient, member_anna: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The URL an upload returns is what gets written into ``jobs.image_url``, so it has to
    be a URL that works. A base configured with a trailing slash is ordinary, and joining it
    naively would store a doubled slash in every row for as long as the setting stands."""
    monkeypatch.setenv("APP_PUBLIC_BASE_URL", "https://api.example.com/")
    reset_settings_caches()

    body = _upload(client, member_anna["headers"])

    assert body["url"] == f"https://api.example.com/api/v1/media/job-images/{body['key']}"
