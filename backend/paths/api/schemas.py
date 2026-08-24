"""Public response models for the paths API."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from backend.paths.domain import MemberCard, MemberPath, PathFlow


class PathMemberPublic(MemberCard):
    """A member as the Paths view draws them.

    Narrower than ``MemberPublic`` on the members board on purpose: this is what fits on a
    card in a Sankey box, and the full profile is one call away at
    ``GET /api/v1/members/{slug}``.
    """

    model_config = ConfigDict(title="PathMemberPublic")


class PathMembersPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[PathMemberPublic]
    total: int


class MemberPathPublic(MemberPath):
    model_config = ConfigDict(title="MemberPathPublic")


class PathFlowPublic(PathFlow):
    model_config = ConfigDict(title="PathFlowPublic")


class PathGroupsPublic(BaseModel):
    """The boxes each column of the Sankey can have, for the filter chips."""

    model_config = ConfigDict(extra="forbid")

    study: list[str]
    first_step: list[str]
    current: list[str]
    intent: list[str]
