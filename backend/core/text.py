"""How long the free-text fields on this platform may be.

Every board has one or two fields with no natural ceiling: an announcement's body, a job
description, what a room is like. They were unbounded, so a single request could store
megabytes of text that every later read of that row then carries. These are the two ceilings
the whole platform uses, so a new long field has an obvious answer rather than a new opinion.

Generous on purpose. ``MAX_RICH_TEXT`` is roughly four thousand words, which is longer than
any real job description; the point is a ceiling, not an editorial rule.
"""

from __future__ import annotations

#: A description, a body, an "about": prose someone wrote in a text area.
MAX_RICH_TEXT = 20_000

#: A note, a summary, a single paragraph.
MAX_NOTE = 2_000

#: The largest JSON request body any route accepts. Uploads are their own limit
#: (``StorageSettings.max_upload_bytes``) and are checked against the bytes actually read.
MAX_JSON_BODY_BYTES = 1024 * 1024
