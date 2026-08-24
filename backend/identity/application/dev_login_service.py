"""The development sign-in use case: mint a token, then take the normal path with it.

There is no Supabase project yet, so nothing can issue the JWT the API expects. Rather than
add a second way in, this mints one locally and then calls
:meth:`AuthService.authenticate` with it, so the Account is upserted and bound by exactly the
code that will run against real Supabase tokens. It exists only while
``AUTH_DEV_LOGIN_ENABLED`` is on, and ``create_app`` refuses to boot with that flag set in
production.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.core.exceptions import ConflictError, NotFoundError
from backend.identity.application.auth_service import AuthService
from backend.identity.application.ports import DevMemberDirectory
from backend.identity.domain import MemberSummary, Principal
from backend.identity.infrastructure.dev_token_issuer import DevTokenIssuer


@dataclass(frozen=True, slots=True)
class DevLoginResult:
    access_token: str
    expires_in: int
    principal: Principal
    member_slug: str | None


class DevLoginService:
    def __init__(
        self,
        *,
        auth: AuthService,
        issuer: DevTokenIssuer,
        members: DevMemberDirectory,
        default_email_domain: str,
    ) -> None:
        self._auth = auth
        self._issuer = issuer
        self._members = members
        self._default_domain = default_email_domain

    async def login(
        self, *, member_slug: str | None = None, email: str | None = None
    ) -> DevLoginResult:
        """Sign in as the Member at ``member_slug``.

        The slug is the identifier, because it is the one the picker can show without
        publishing everybody's Workspace address. The address behind it is read from the
        roster row; a row that has none is claimed by writing one derived from the slug, which
        is what lets a developer "become" any of the roughly 175 Members who never had a
        mailbox. A row that already carries a *different* address is left alone and the call
        is a 409: two Members sharing one e-mail would break the binding that
        ``authenticate`` relies on.

        ``email`` is the compatibility path while the frontend catches up. On its own it
        behaves exactly as it always did; alongside a slug it is checked against the row and
        409s when they disagree. Delete this parameter, and the branch below, once the
        frontend posts ``member_slug``.
        """
        email = email.strip().lower() if email else None

        member = None
        if member_slug:
            member = await self._members.get_member_by_slug(member_slug)
            if member is None:
                raise NotFoundError(f"member {member_slug!r} not found")
            if member.email and email and member.email.lower() != email:
                raise ConflictError(
                    f"member {member_slug!r} is already claimed by {member.email}",
                    details={"member_email": member.email},
                )
            email = email or (member.email or "").lower() or self._derived_email(member_slug)
        if not email:
            raise NotFoundError("pass member_slug (or, for now, email)")

        # The allow-list is the API's rule about who may exist at all, so it has to hold
        # before the member row is touched, not after the token comes back.
        self._auth.ensure_email_allowed(email)
        if member is not None and not member.email:
            await self._members.set_member_email(member.id, email)

        token = self._issuer.issue(email, full_name=member.name if member else None)
        principal = await self._auth.authenticate(token.access_token)
        slug = member.slug if member else await self._auth.find_member_slug(principal)
        return DevLoginResult(
            access_token=token.access_token,
            expires_in=token.expires_in,
            principal=principal,
            member_slug=slug,
        )

    def _derived_email(self, member_slug: str) -> str:
        """An address for a roster row that has none, on the first allowed domain.

        Development only, and written onto the row the same way passing that address by hand
        used to be. The slug is already unique, so the address is too.
        """
        return f"{member_slug.strip().lower()}@{self._default_domain}"

    async def search_members(self, query: str | None, *, limit: int) -> list[MemberSummary]:
        """Candidates for the impersonation picker in the local sign-in screen."""
        return await self._members.search_members(query, limit=limit)
