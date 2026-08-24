"""Uploads through the API and back out of it, against the local disk adapter."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.core.settings import reset_settings_caches

pytestmark = pytest.mark.integration

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
GIF = b"GIF89a" + b"\x00" * 64


def _upload(client: TestClient, kind: str, data: bytes, headers: dict, name: str = "a.png"):
    return client.post(
        f"/api/v1/media/{kind}",
        files={"file": (name, data, "image/png")},
        headers=headers,
    )


def test_upload_then_read_round_trips_the_bytes(client: TestClient, member_anna: dict) -> None:
    r = _upload(client, "job-image", PNG, member_anna["headers"])
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["bucket"] == "job-images"
    assert body["content_type"] == "image/png"
    assert body["size"] == len(PNG)
    assert body["url"].endswith(f"/api/v1/media/job-images/{body['key']}")

    # The URL is absolute and points back at the API; follow its path.
    got = client.get(f"/api/v1/media/job-images/{body['key']}")
    assert got.status_code == 200, got.text
    assert got.content == PNG
    assert got.headers["content-type"] == "image/png"
    assert got.headers["cache-control"] == "public, max-age=31536000, immutable"


def test_each_kind_lands_in_its_own_bucket(client: TestClient, member_anna: dict) -> None:
    buckets = {}
    for kind, data in (("job-image", PNG), ("housing-photo", JPEG), ("avatar", PNG)):
        r = _upload(client, kind, data, member_anna["headers"])
        assert r.status_code == 201, r.text
        buckets[kind] = r.json()["bucket"]
    assert buckets == {
        "job-image": "job-images",
        "housing-photo": "housing-photos",
        "avatar": "avatars",
    }


def test_reading_is_public_so_img_tags_work(client: TestClient, member_anna: dict) -> None:
    key = _upload(client, "avatar", PNG, member_anna["headers"]).json()["key"]
    assert client.get(f"/api/v1/media/avatars/{key}").status_code == 200


def test_unknown_bucket_and_unknown_key_are_not_found(
    client: TestClient, member_anna: dict
) -> None:
    key = _upload(client, "avatar", PNG, member_anna["headers"]).json()["key"]
    assert client.get(f"/api/v1/media/secrets/{key}").status_code == 404
    assert client.get("/api/v1/media/avatars/not-a-key.png").status_code == 404
    assert client.get(f"/api/v1/media/avatars/{key.replace('.png', '.webp')}").status_code == 404


def test_a_non_image_is_rejected(client: TestClient, member_anna: dict) -> None:
    r = _upload(client, "job-image", GIF, member_anna["headers"])
    assert r.status_code == 422, r.text
    assert r.json()["error"]["code"] == "validation_error"


def test_an_unknown_kind_is_rejected(client: TestClient, member_anna: dict) -> None:
    assert _upload(client, "resume", PNG, member_anna["headers"]).status_code == 422


def test_oversize_upload_is_413(
    client: TestClient, member_anna: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("STORAGE_MAX_UPLOAD_BYTES", "32")
    reset_settings_caches()
    r = _upload(client, "job-image", PNG, member_anna["headers"])
    assert r.status_code == 413, r.text
    assert r.json()["error"]["code"] == "payload_too_large"


def test_unauthenticated_upload_is_401(client: TestClient) -> None:
    assert _upload(client, "job-image", PNG, {}).status_code == 401


def test_delete_is_admin_only(client: TestClient, member_anna: dict, admin_headers: dict) -> None:
    key = _upload(client, "job-image", PNG, member_anna["headers"]).json()["key"]
    path = f"/api/v1/media/job-images/{key}"

    assert client.delete(path).status_code == 401
    assert client.delete(path, headers=member_anna["headers"]).status_code == 403

    assert client.delete(path, headers=admin_headers).status_code == 204
    assert client.get(path).status_code == 404


def test_the_declared_content_type_does_not_decide(client: TestClient, member_anna: dict) -> None:
    # A JPEG announced as image/png is stored as what it is, not as what it claims.
    r = client.post(
        "/api/v1/media/job-image",
        files={"file": ("lying.png", JPEG, "image/png")},
        headers=member_anna["headers"],
    )
    assert r.status_code == 201, r.text
    assert r.json()["content_type"] == "image/jpeg"
    assert r.json()["key"].endswith(".jpg")


def test_empty_upload_is_rejected(client: TestClient, member_anna: dict) -> None:
    assert _upload(client, "job-image", b"", member_anna["headers"]).status_code == 422
