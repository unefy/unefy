"""Sync response shapes.

Two deliberate divergences from `app/schemas/base.py`, both worth naming so they
read as decisions rather than oversights:

1. **`SyncMeta` carries no `total` or `total_pages`.** Every other list route
   emits `PaginationMeta`. For an unbounded delta the total is meaningless — a
   client is not on page 3 of 7, it is somewhere in a stream — and computing it
   would add a `COUNT(*)` per page, which would be the most expensive part of a
   request that otherwise touches one index range.
2. **`data` is an object, not a list.** Changed rows and tombstones are different
   things and a client applies them differently. There is precedent for an object
   under `data` (`POST /members/bulk-delete` returns `{"deleted": n}`), though
   this is the first *read* collection to do it. The alternative — one
   heterogeneous list with a discriminator — is worse for the hand-written mobile
   DTOs that have to decode it.
"""

import uuid
from datetime import datetime

from app.schemas.base import BaseSchema


class Tombstone(BaseSchema):
    """A row that is gone. Id and time only — never the row body.

    The reasoning is the codebase's own, from `TenantAuditLog.changes`: storing
    the whole row turns the log into a second copy of the data, personal data
    included. A tombstone carrying a deleted member's name and IBAN, broadcast to
    every device in the club and kept there for two weeks, is that same mistake
    wearing a different hat. The client only needs the id to delete locally.
    """

    id: uuid.UUID
    deleted_at: datetime


class SyncMeta(BaseSchema):
    """Where the client got to, and whether it is caught up."""

    #: Always present — pass it back verbatim next time. On an empty page this is
    #: the cursor that was sent, so a caller can store it unconditionally.
    cursor: str

    #: The scan filled the page. Keep draining until this is false.
    has_more: bool

    #: Caught up as of `server_time`. Currently the negation of `has_more`, kept
    #: separate because they answer different questions for a UI, and because a
    #: future `resync_required` would make them diverge.
    complete: bool

    #: Lets a client measure its own clock offset without a second endpoint.
    server_time: datetime

    collection: str
