"""Public response models for the network API."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict

from backend.network.domain import IntroRequest, MemberCard, SavedMember


class NetworkMemberPublic(MemberCard):
    """The person on the other end of a saved row or an intro request.

    A card, not a profile: this context is only allowed to know enough about a member to
    draw them in a list. ``GET /api/v1/members/{slug}`` is the profile.
    """

    model_config = ConfigDict(title="NetworkMemberPublic")


class SavedMemberPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    saved: SavedMember
    member: NetworkMemberPublic


class SavedMembersPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[SavedMemberPublic]
    total: int


class SavedMemberIdsPublic(BaseModel):
    """The shortlist as bare ids, next to the paged list of cards.

    Two answers to two questions. The page is what a member reads, so it is cut and carries
    a whole card per row. This is what the Save button needs, and a button is either filled
    or it is not: reading membership off a page meant everybody past the first hundred rows
    was drawn as unsaved. One column and one row per saved person, so the whole list fits in
    an answer that does not need paging.
    """

    model_config = ConfigDict(extra="forbid")

    member_ids: list[UUID]


class IntroRequestPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request: IntroRequest
    requester: NetworkMemberPublic
    target: NetworkMemberPublic


class IntroRequestsPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[IntroRequestPublic]
    total: int
