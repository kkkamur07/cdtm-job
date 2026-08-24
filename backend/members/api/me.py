"""What the signed-in member maintains about themselves: their profile, entry and intents.

Saved members and intro requests used to live here. They are the network context now, at
``/api/v1/network/saved`` and ``/api/v1/network/intros``.
"""

from __future__ import annotations

from fastapi import APIRouter

from backend.core.actor import Actor
from backend.core.exceptions import ConflictError
from backend.identity.api.deps import AuthServiceDep, MemberActorDep, PrincipalDep
from backend.members.api.deps import EntryServiceDep, MemberServiceDep
from backend.members.api.schemas import EntryPublic, IntentsPublic, MemberProfilePublic
from backend.members.application.commands import (
    EntryUpsert,
    IntentsUpsert,
    SelfProfileCreate,
    SelfProfileUpdate,
)

router = APIRouter(prefix="/members/me", tags=["members"])


@router.get("", response_model=MemberProfilePublic)
async def my_member(actor: MemberActorDep, members: MemberServiceDep) -> MemberProfilePublic:
    return MemberProfilePublic.model_validate(
        await members.get_profile_by_id(actor.require_member(), actor)
    )


@router.post("", response_model=MemberProfilePublic, status_code=201)
async def create_my_profile(
    body: SelfProfileCreate,
    principal: PrincipalDep,
    members: MemberServiceDep,
    auth: AuthServiceDep,
) -> MemberProfilePublic:
    """Claim a fresh member profile for a signed-in account no roster row matched.

    Checked before anything is written: an account that is already linked cannot make a
    second member. The member is created first, then the account is bound to it, so the two
    steps cannot half-succeed into an orphan the caller can never reach.
    """
    if principal.member_id is not None:
        raise ConflictError("your account is already linked to a member")
    member_id = await members.create_self_profile(
        body, email=principal.email, avatar_url=principal.account.avatar_url
    )
    await auth.claim_member(principal, member_id)
    actor = Actor(member_id, principal.is_admin)
    return MemberProfilePublic.model_validate(await members.get_profile_by_id(member_id, actor))


@router.put("", response_model=MemberProfilePublic)
async def update_my_profile(
    body: SelfProfileUpdate,
    actor: MemberActorDep,
    members: MemberServiceDep,
) -> MemberProfilePublic:
    """Edit your own profile after it exists.

    The same form as create, so an imported member who just signed in and a self-created
    one maintain the same fields. ``MemberActorDep`` already requires a linked member, so
    there is nothing to claim here: it only writes.
    """
    member_id = actor.require_member()
    await members.update_self_profile(member_id, body)
    return MemberProfilePublic.model_validate(await members.get_profile_by_id(member_id, actor))


@router.get("/entry", response_model=EntryPublic | None)
async def my_entry(actor: MemberActorDep, service: EntryServiceDep) -> EntryPublic | None:
    entry = await service.get_entry(actor)
    return EntryPublic.model_validate(entry) if entry else None


@router.put("/entry", response_model=EntryPublic)
async def upsert_my_entry(
    body: EntryUpsert, actor: MemberActorDep, service: EntryServiceDep
) -> EntryPublic:
    return EntryPublic.model_validate(await service.upsert_entry(actor, body))


@router.get("/intents", response_model=IntentsPublic | None)
async def my_intents(actor: MemberActorDep, service: EntryServiceDep) -> IntentsPublic | None:
    intents = await service.get_intents(actor)
    return IntentsPublic.model_validate(intents) if intents else None


@router.put("/intents", response_model=IntentsPublic)
async def upsert_my_intents(
    body: IntentsUpsert, actor: MemberActorDep, service: EntryServiceDep
) -> IntentsPublic:
    return IntentsPublic.model_validate(await service.upsert_intents(actor, body))
