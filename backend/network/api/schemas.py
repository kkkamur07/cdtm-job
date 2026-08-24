"""Public response models for the network API."""

from __future__ import annotations

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


class IntroRequestPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request: IntroRequest
    requester: NetworkMemberPublic
    target: NetworkMemberPublic
