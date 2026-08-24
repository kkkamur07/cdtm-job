"""Who is acting on a request: a member id and an admin flag.

Every board takes an ``Actor``, never a ``Principal``. It carries the two facts about the
caller that authorization anywhere in the platform turns on, and nothing else an Account
happens to know. It lives in ``core`` because all ten contexts need it and none of them
owns it: ``backend/identity/api/deps.py`` is the one place a Principal becomes one.
"""

from __future__ import annotations

from uuid import UUID

from backend.core.exceptions import ForbiddenError


class Actor:
    __slots__ = ("is_admin", "member_id")

    def __init__(self, member_id: UUID | None, is_admin: bool = False) -> None:
        self.member_id = member_id
        self.is_admin = is_admin

    def require_member(self) -> UUID:
        if self.member_id is None:
            raise ForbiddenError("your account is not linked to a member entry yet")
        return self.member_id
