"""Sign-in: verify the Supabase token, enforce the domain allow-list, bind the account to its member."""

from __future__ import annotations

import logging
from uuid import UUID

from backend.core.exceptions import ConflictError, ForbiddenError, NotFoundError, UnauthorizedError
from backend.core.page import PageResult
from backend.identity.application.ports import AccountRepository, MemberDirectory, TokenVerifier
from backend.identity.domain import Account, Principal

logger = logging.getLogger(__name__)


def _domain_of(email: str) -> str:
    return email.rsplit("@", 1)[-1].lower() if "@" in email else ""


class AuthService:
    def __init__(
        self,
        *,
        verifier: TokenVerifier,
        accounts: AccountRepository,
        members: MemberDirectory,
        allowed_email_domains: list[str],
        admin_emails: list[str],
    ) -> None:
        self._verifier = verifier
        self._accounts = accounts
        self._members = members
        self._allowed = {d.lower() for d in allowed_email_domains}
        self._admins = {e.lower() for e in admin_emails}

    def ensure_email_allowed(self, email: str) -> None:
        """Raise unless the address belongs to an allowed Workspace domain.

        Public because the development login has to apply the allow-list *before* it writes
        anything, and re-implementing the rule next to it is how the two would drift apart.
        """
        if self._allowed and _domain_of(email) not in self._allowed:
            raise ForbiddenError(
                "sign in with your CDTM Google account",
                details={"allowed_domains": sorted(self._allowed)},
            )

    async def authenticate(self, token: str) -> Principal:
        claims = await self._verifier.verify_async(token)
        email = claims.email.lower()
        if not email:
            raise UnauthorizedError("token has no e-mail claim")
        if not claims.email_verified:
            # An e-mail nobody has verified is not a fact about who the caller is. Trusting
            # it here would let any token with an arbitrary top-level ``email`` claim pass
            # the domain allow-list and bind to a Member's roster row - the same account
            # takeover the ``user_metadata`` fallback was closed for, one field over.
            raise UnauthorizedError("e-mail is not verified")
        self.ensure_email_allowed(email)
        bootstrap_admin = True if email in self._admins else None
        # Store the e-mail lower-cased: accounts.email is unique and the roster binding
        # compares lower-cased values, so one mailbox can never become two accounts.
        claims = claims.model_copy(update={"email": email})
        account = await self._accounts.upsert_from_claims(claims, is_admin=bootstrap_admin)
        if account.member_id is None:
            member_id = await self._members.find_member_id_by_email(email)
            if member_id is not None:
                # The roster row may already be bound to another account (an admin bound it
                # by hand, or two mailboxes share a member). Signing in must still work; the
                # account then stays unbound until an admin sorts it out. Nothing else in the
                # platform notices that state, so say so once per sign-in with both ids: an
                # unbound account can read the directory and write nothing member-owned, and
                # the member it belongs to has no way to report that themselves.
                try:
                    account = await self._accounts.bind_member(account.id, member_id)
                except ConflictError:
                    logger.warning(
                        "account %s matched member %s by e-mail but that member is already "
                        "bound to a different account; the account stays unbound until an "
                        "admin rebinds it",
                        account.id,
                        member_id,
                    )
        return Principal(account=account)

    async def claim_member(self, principal: Principal, member_id: UUID) -> Account:
        """Bind the caller's own account to a member it just created for itself.

        The self-service counterpart of ``bind_account_to_member`` (which is admin-only):
        here the account binds to a Member, but only its own, and only while it has none
        yet. An account that is already linked is a no-op-shaped mistake, not a rebind, so
        it is refused rather than silently moved.
        """
        if principal.member_id is not None:
            raise ConflictError("this account is already linked to a member")
        return await self._accounts.bind_member(principal.account.id, member_id)

    async def find_member_slug(self, principal: Principal) -> str | None:
        """The slug of the Member this Principal is bound to, if any."""
        if principal.member_id is None:
            return None
        return await self._members.find_member_slug_by_id(principal.member_id)

    async def get_account(self, account_id: UUID) -> Account:
        account = await self._accounts.get_by_id(account_id)
        if account is None:
            raise NotFoundError("account not found")
        return account

    async def list_accounts(
        self, *, actor: Principal, skip: int, limit: int, unbound_only: bool
    ) -> PageResult[Account]:
        """Accounts, for the admin page that binds the ones no roster row matched."""
        if not actor.is_admin:
            raise ForbiddenError("admin only")
        return await self._accounts.list_accounts(skip=skip, limit=limit, unbound_only=unbound_only)

    async def bind_account_to_member(
        self, *, actor: Principal, account_id: UUID, member_slug: str
    ) -> Account:
        """Admins can bind an account whose e-mail did not match any roster row."""
        if not actor.is_admin:
            raise ForbiddenError("admin only")
        member_id = await self._members.find_member_id_by_slug(member_slug)
        if member_id is None:
            raise NotFoundError(f"member {member_slug!r} not found")
        return await self._accounts.bind_member(account_id, member_id)

    async def set_admin(self, *, actor: Principal, account_id: UUID, is_admin: bool) -> Account:
        if not actor.is_admin:
            raise ForbiddenError("admin only")
        return await self._accounts.set_admin(account_id, is_admin)
