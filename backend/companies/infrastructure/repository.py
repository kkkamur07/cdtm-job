from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from postgrest.exceptions import APIError
from supabase import Client

from companies.application.commands import CreateCompanyCommand, UpdateCompanyCommand


class SupabaseCompanyRepository:
    def __init__(self, client: Client) -> None:
        self._client = client

    def insert_company(self, command: CreateCompanyCommand) -> UUID:
        row = {
            "name": command.name,
            "slug": command.slug,
            "website": command.website,
            "logo_url": command.logo_url,
            "description": command.description,
            "headquarters_location": command.headquarters_location,
            "company_size_band": command.company_size_band,
            "industry": command.industry,
            "_is_cdtm_startup": command.is_cdtm_startup,
        }
        try:
            res = self._client.table("companies").insert(row).execute()
        except APIError as e:
            raise ValueError(f"insert company failed: {e!s}") from e
        if not res.data:
            raise ValueError("Failed to insert company (no data returned)")
        return UUID(res.data[0]["id"])

    def get_by_slug(self, slug: str) -> dict[str, Any] | None:
        try:
            res = self._client.table("companies").select("*").eq("slug", slug).limit(1).execute()
        except APIError as e:
            raise ValueError(f"select company failed: {e!s}") from e
        if not res.data:
            return None
        return res.data[0]

    def get_by_id(self, company_id: UUID) -> dict[str, Any] | None:
        try:
            res = (
                self._client.table("companies").select("*").eq("id", str(company_id)).limit(1).execute()
            )
        except APIError as e:
            raise ValueError(f"select company failed: {e!s}") from e
        if not res.data:
            return None
        return res.data[0]

    def list_companies(self, *, limit: int = 100) -> list[dict[str, Any]]:
        try:
            res = self._client.table("companies").select("*").order("name").limit(limit).execute()
        except APIError as e:
            raise ValueError(f"list companies failed: {e!s}") from e
        return list(res.data or [])

    def update_company(self, company_id: UUID, command: UpdateCompanyCommand) -> None:
        patch = command.model_dump(exclude_unset=True)
        if "is_cdtm_startup" in patch:
            patch["_is_cdtm_startup"] = patch.pop("is_cdtm_startup")
        if not patch:
            return
        patch["updated_at"] = datetime.now(UTC).isoformat()
        try:
            res = self._client.table("companies").update(patch).eq("id", str(company_id)).execute()
        except APIError as e:
            raise ValueError(f"update company failed: {e!s}") from e
        if not res.data:
            raise ValueError("Company not found")

    def delete_company(self, company_id: UUID) -> bool:
        try:
            res = self._client.table("companies").delete().eq("id", str(company_id)).execute()
        except APIError as e:
            raise ValueError(f"delete company failed: {e!s}") from e
        return bool(res.data)
