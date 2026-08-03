"""Which collections a client may mirror, and who may mirror them.

A data table, not a route factory. The routes in `app/api/v1/sync.py` are written
out one by one on purpose — the mobile apps hand-write their DTOs and a CI test
checks them against the generated OpenAPI spec so backend drift breaks the build
(see `apps/mobile/CLAUDE.md`). Routes generated in a loop, returning
`dict[str, Any]` from a shared closure, would hand that spec nothing to check.

What the registry is for instead: answering `GET /sync/manifest`, and — once the
push channel exists — deciding which change hints a given connection is allowed
to be told about at all.
"""

from dataclasses import dataclass, field
from typing import Any

from app.models.competition import Competition, Entry
from app.models.competition import Session as CompetitionSession
from app.models.due import Due, FeeType, MemberFee
from app.models.event import Event, EventRegistration
from app.models.member import Member
from app.schemas.competition import CompetitionResponse, EntryResponse, SessionResponse
from app.schemas.due import DueResponse, FeeTypeResponse, MemberFeeResponse
from app.schemas.event import EventRegistrationResponse, EventResponse
from app.schemas.member import MemberResponse

#: Roles that may read a club's full administrative data.
BOARD_ROLES = ("owner", "admin", "board")

#: Everyone in the club, including plain members.
ALL_ROLES = ("owner", "admin", "board", "member")


@dataclass(frozen=True)
class Collection:
    """One syncable collection."""

    name: str
    model: type[Any]
    response: type[Any]

    #: Roles allowed to sync it. Narrower than "can read something related" —
    #: `MemberResponse` carries `iban` and `sepa_mandate_reference`, so the member
    #: collection is board-only even though a plain member can read the directory.
    roles: tuple[str, ...] = field(default=BOARD_ROLES)


COLLECTIONS: dict[str, Collection] = {
    c.name: c
    for c in (
        Collection("members", Member, MemberResponse),
        Collection("events", Event, EventResponse, roles=ALL_ROLES),
        Collection("event-registrations", EventRegistration, EventRegistrationResponse),
        Collection("dues", Due, DueResponse),
        Collection("fee-types", FeeType, FeeTypeResponse),
        Collection("member-fees", MemberFee, MemberFeeResponse),
        Collection("competitions", Competition, CompetitionResponse, roles=ALL_ROLES),
        Collection("competition-sessions", CompetitionSession, SessionResponse),
        Collection("entries", Entry, EntryResponse),
    )
}


def collections_for(role: str | None) -> list[Collection]:
    """The collections a role may sync, in a stable order."""
    if role is None:
        return []
    return [c for c in COLLECTIONS.values() if role in c.roles]


#: Inverted once at import: the lookup runs inside the `after_flush` listener,
#: i.e. for every object of every flush in the whole backend, synced or not.
_COLLECTION_BY_MODEL: dict[type[Any], str] = {c.model: c.name for c in COLLECTIONS.values()}


def collection_for_model(model: type[Any]) -> str | None:
    """The collection a model belongs to, or None if it is not synced.

    Used by `BaseRepository` to label its change hints. Returning None rather than
    raising is the point: plenty of models are not synced (tenants, users,
    invitations, the discipline catalog) and writing one of those must stay a
    perfectly ordinary write, not an error.
    """
    return _COLLECTION_BY_MODEL.get(model)
