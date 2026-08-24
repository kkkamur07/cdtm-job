"""Magic-byte sniffing, key safety and the local adapter's path handling."""

from __future__ import annotations

import pytest

from backend.core.exceptions import ValidationError
from backend.media.infrastructure.images import (
    content_type_for_key,
    is_safe_key,
    new_key,
    sniff_image_content_type,
)
from backend.media.infrastructure.local_disk import LocalDiskStorage

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 16
WEBP = b"RIFF" + (24).to_bytes(4, "little") + b"WEBP" + b"VP8 " + b"\x00" * 8
GIF = b"GIF89a" + b"\x00" * 16
SVG = b"<svg xmlns='http://www.w3.org/2000/svg'></svg>"


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (PNG, "image/png"),
        (JPEG, "image/jpeg"),
        (WEBP, "image/webp"),
        (GIF, None),
        (SVG, None),
        (b"", None),
        (b"RIFF", None),
        (b"RIFF" + (4).to_bytes(4, "little") + b"AVI ", None),
    ],
)
def test_sniff_image_content_type(data: bytes, expected: str | None) -> None:
    assert sniff_image_content_type(data) == expected


def test_declared_type_never_wins_over_the_bytes() -> None:
    # A PHP payload announced as image/png is what the sniff exists to stop.
    assert sniff_image_content_type(b"<?php system($_GET['c']); ?>") is None


def test_new_key_round_trips_its_content_type() -> None:
    for content_type in ("image/png", "image/jpeg", "image/webp"):
        key = new_key(content_type)
        assert is_safe_key(key)
        assert content_type_for_key(key) == content_type


@pytest.mark.parametrize(
    "key",
    [
        "../../etc/passwd",
        "..%2F..%2Fetc",
        "sub/dir/file.png",
        "file.png.exe",
        "file.svg",
        "",
        ".",
        "a" * 40 + ".png",
        "/absolute.png",
    ],
)
def test_unsafe_keys_are_rejected(key: str) -> None:
    assert is_safe_key(key) is False


def test_local_disk_writes_under_the_root(tmp_path) -> None:
    storage = LocalDiskStorage(tmp_path)
    path = storage.path_for("job-images", "a.png")
    assert path.parent == tmp_path / "job-images"


@pytest.mark.parametrize("key", ["../escape.png", "../../escape.png", "/etc/passwd"])
def test_local_disk_refuses_to_escape_the_root(tmp_path, key: str) -> None:
    storage = LocalDiskStorage(tmp_path)
    with pytest.raises(ValidationError):
        storage.path_for("job-images", key)


def test_local_disk_refuses_an_escaping_bucket(tmp_path) -> None:
    storage = LocalDiskStorage(tmp_path)
    with pytest.raises(ValidationError):
        storage.path_for("..", "a.png")


async def test_local_disk_put_get_delete(tmp_path) -> None:
    storage = LocalDiskStorage(tmp_path)
    key = new_key("image/png")

    assert await storage.get("job-images", key) is None
    await storage.put("job-images", key, PNG, "image/png")
    assert await storage.get("job-images", key) == (PNG, "image/png")
    # The local adapter cannot sign, which is what makes the route stream instead.
    assert await storage.signed_url("job-images", key, 600) is None

    await storage.delete("job-images", key)
    assert await storage.get("job-images", key) is None
    # Deleting twice is not an error.
    await storage.delete("job-images", key)
