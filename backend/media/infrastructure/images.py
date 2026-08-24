"""Image type detection and key safety, kept free of FastAPI so both are unit testable."""

from __future__ import annotations

import re
import uuid

#: The three formats the platform accepts. Anything else (GIF, SVG, HEIC, PDF) is rejected:
#: SVG in particular is a script carrier, and the frontend only ever renders these three.
ALLOWED_IMAGE_TYPES: frozenset[str] = frozenset({"image/jpeg", "image/png", "image/webp"})

#: Extension per content type. The extension is the only place the type is recorded, so the
#: local adapter can answer ``get()`` with a content type without keeping a sidecar file.
EXTENSIONS: dict[str, str] = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}

CONTENT_TYPES: dict[str, str] = {ext: ct for ct, ext in EXTENSIONS.items()}

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_JPEG_MAGIC = b"\xff\xd8\xff"

#: ``<uuid4>.<ext>``: hex, dashes and one extension. Everything the media routes accept as a
#: key must match, which is what keeps ``..`` and path separators out of the storage adapters.
_KEY_RE = re.compile(r"^[0-9a-fA-F-]{36}\.(jpg|png|webp)$")


def sniff_image_content_type(data: bytes) -> str | None:
    """Return the content type implied by the leading bytes, or ``None`` if unrecognised.

    The multipart ``Content-Type`` header is attacker-controlled, so it decides nothing; a
    ``.php`` payload labelled ``image/png`` has to fail here rather than land in a bucket.
    """
    if data.startswith(_PNG_MAGIC):
        return "image/png"
    if data.startswith(_JPEG_MAGIC):
        return "image/jpeg"
    # RIFF container: "RIFF" <4-byte little-endian size> "WEBP".
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def new_key(content_type: str) -> str:
    """A fresh, unguessable key for a blob of this type."""
    return f"{uuid.uuid4()}.{EXTENSIONS[content_type]}"


def is_safe_key(key: str) -> bool:
    return bool(_KEY_RE.match(key))


def content_type_for_key(key: str) -> str:
    ext = key.rsplit(".", 1)[-1].lower() if "." in key else ""
    return CONTENT_TYPES.get(ext, "application/octet-stream")
