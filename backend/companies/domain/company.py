from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class Company:
    """Company aggregate root (aligned with ``public.companies``).

    ``is_cdtm_startup`` maps to the DB column ``_is_cdtm_startup`` in infrastructure adapters.
    """

    id: UUID
    name: str
    slug: str
    is_cdtm_startup: bool = False
    website: str | None = None
    logo_url: str | None = None
    description: str | None = None
    headquarters_location: str | None = None
    company_size_band: str | None = None
    industry: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
