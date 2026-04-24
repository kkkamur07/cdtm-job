from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class Seeker:
    """Seeker aggregate root (v1 placeholder — no ``seekers`` / ``profiles`` table yet).

    When Supabase Auth + ``profiles`` exist, ``id`` will typically align with ``auth.users``
    (or a dedicated profile PK). Fields stay minimal until applications and CV flows land.
    """

    id: UUID
    display_name: str | None = None
    created_at: datetime | None = None
