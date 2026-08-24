"""Who is allowed to see what on a listing.

The view counter is not the same field for everybody and neither is a listing that has left
the board, so both rules live on their own rather than as private methods of one service: the
board's list, the board's detail reply and the Ask over the board all return listings, and a
rule that only one of them applies is a rule that leaks through the other two.
"""

from __future__ import annotations

import dataclasses
from typing import TypeVar

from backend.core.actor import Actor
from backend.housing.application.ports import HousingFilters
from backend.housing.domain import HousingListing, HousingListingSummary, HousingStatus
from infrastructure.repository import utc_now

#: The board's list hands back ``HousingListingSummary`` and every other read hands back
#: ``HousingListing``. Both carry the owner, the status, the expiry and the view counter,
#: which is everything the rules below read, so a rule answers the same for either and hands
#: back what it was given.
AnyListing = TypeVar("AnyListing", HousingListing, HousingListingSummary)


def is_owner(row: HousingListing | HousingListingSummary, actor: Actor | None) -> bool:
    if actor is None or actor.member_id is None:
        return False
    return row.member_id == actor.member_id


def is_on_the_board(row: HousingListing | HousingListingSummary, actor: Actor | None) -> bool:
    """A closed or expired listing is off the board, for its detail reply as much as its list.

    The owner and an admin still see it, because "my listings" is the one view that shows
    expired rows and there would otherwise be nothing left to renew.
    """
    if is_owner(row, actor) or (actor is not None and actor.is_admin):
        return True
    if row.status != HousingStatus.OPEN:
        return False
    return row.expires_at is None or row.expires_at > utc_now()


def for_viewer(row: AnyListing, actor: Actor | None) -> AnyListing:
    """Hide the view count from everyone but the owner and an admin.

    Null rather than absent: the field is in the response shape either way, and "you are not
    being told" is a different answer from "nobody has looked". A card is redacted the same
    way a listing is, because the board's list is as much a way of reading one as opening it.
    """
    if is_owner(row, actor) or (actor is not None and actor.is_admin):
        return row
    return row.model_copy(update={"view_count": None})


def sanitized_list_filters(filters: HousingFilters, actor: Actor | None) -> HousingFilters:
    """Clamp a board query to what the caller is actually allowed to see.

    ``status`` and ``include_expired`` reach here as requests from the caller, not grants:
    the API layer sets ``include_expired`` whenever a ``member_id`` filter is present (so
    "my listings" can show what there is to renew) and lets ``status`` be overridden freely.
    Neither check who is asking. Without this, a Member could set ``member_id`` to someone
    else's id to see their expired listings, or set ``status=closed`` on the whole board to
    see everyone's closed ones -- both are exactly what :func:`is_on_the_board` refuses the
    same Member by id, and a list must not be a side door around it.

    An admin, or a Member filtering on their own ``member_id``, is trusted with the request
    as given; everyone else is held to ``open`` and not-expired regardless of what they asked
    for.
    """
    is_admin = bool(actor and actor.is_admin)
    viewing_own = (
        filters.member_id is not None
        and actor is not None
        and actor.member_id is not None
        and actor.member_id == filters.member_id
    )
    if is_admin or viewing_own:
        return filters
    return dataclasses.replace(filters, status=HousingStatus.OPEN, include_expired=False)
