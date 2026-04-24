from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class Job:
    """Core job aggregate root (minimal v1).

    The full public job text lives in the DB as ``description`` (and optional ``summary``).
    This dataclass holds the fields we model in domain code today; you can extend it as
    use cases grow (e.g. workplace_type, salary value objects).
    """

    id: UUID
    company_id: UUID
    title: str
    slug: str
    description: str
    status: str
    summary: str | None = None
    created_at: datetime | None = None
