"""``CompanyService.list_companies`` against a fake repository.

The route always spells ``skip`` and ``limit`` out and always builds a ``CompanyFilters``,
so the service's own defaults are only visible from here.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from backend.core.page import PageResult
from backend.jobboard.application.company_service import CompanyService
from backend.jobboard.application.ports import CompanyFilters
from backend.jobboard.domain import Company


def _company() -> Company:
    now = datetime.now(UTC)
    return Company(id=uuid.uuid4(), name="ACME", slug="acme", created_at=now, updated_at=now)


class FakeCompanyRepository:
    """Records the page and filters it was asked for."""

    def __init__(self, items: list[Company]) -> None:
        self._items = items
        self.calls: list[dict] = []

    async def list(self, *, skip: int, limit: int, filters: CompanyFilters) -> PageResult[Company]:
        self.calls.append({"skip": skip, "limit": limit, "filters": filters})
        return PageResult(items=list(self._items), total=len(self._items))


async def test_list_companies_asks_for_the_first_page_of_fifty_by_default() -> None:
    repo = FakeCompanyRepository([_company()])
    result = await CompanyService(repo).list_companies()

    assert repo.calls[0]["skip"] == 0
    assert repo.calls[0]["limit"] == 50
    assert result.total == 1

    await CompanyService(repo).list_companies(skip=7, limit=3)
    assert repo.calls[1]["skip"] == 7
    assert repo.calls[1]["limit"] == 3


async def test_list_companies_forwards_the_filters_it_was_given() -> None:
    """No filters means an empty filter set, not a missing one, and given ones survive."""
    repo = FakeCompanyRepository([])
    service = CompanyService(repo)

    await service.list_companies()
    assert repo.calls[0]["filters"] == CompanyFilters()

    asked = CompanyFilters(industry="fintech", hq_city="Munich", q="ledger")
    await service.list_companies(filters=asked)
    assert repo.calls[1]["filters"] == asked
