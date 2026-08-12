import uuid
from typing import Annotated, Literal

from pydantic import Field

from app.schemas.base import BaseSchema

#: What kind of message this is, and therefore who may receive it.
#:
#: `notice` is a duty communication — the invitation to the general meeting,
#: a change of the statutes. It goes to everyone the selection resolves to.
#: `newsletter` is information the club would like to send; it needs consent.
#:
#: The sender states which one it is. Deriving it from the text would be
#: guessing at a legal distinction, and guessing wrong in the direction that
#: sends advertising to somebody who said no.
MessageKind = Literal["notice", "newsletter"]

MESSAGE_KINDS: tuple[str, ...] = ("notice", "newsletter")


# --- Who the message goes to ---


class AllMembers(BaseSchema):
    """Every active member of the club."""

    type: Literal["all"] = "all"


class FunctionHolders(BaseSchema):
    """Whoever holds this office today — the board, the auditors, the youth leaders."""

    type: Literal["function"] = "function"
    id: uuid.UUID


class EventRegistrants(BaseSchema):
    """Who signed up for one event.

    The waiting list is off by default and available on purpose: for "the trip
    is full" it is the wrong audience, for "the trip is cancelled" it is
    exactly the right one.
    """

    type: Literal["event"] = "event"
    id: uuid.UUID
    include_waitlist: bool = False


class Debtors(BaseSchema):
    """Members with an open assessment in this year."""

    type: Literal["debtors"] = "debtors"
    year: int = Field(ge=2000, le=2100)


#: A club's division is deliberately absent: there is no such thing as
#: membership *in* a division yet (see docs/plans/communication.md). When it
#: exists this list gains one entry and nothing else changes.
Audience = Annotated[
    AllMembers | FunctionHolders | EventRegistrants | Debtors,
    Field(discriminator="type"),
]


# --- What resolving the selection produced ---


class RecipientPreview(BaseSchema):
    member_id: uuid.UUID
    first_name: str
    last_name: str
    email: str | None = None
    status: Literal["pending", "skipped"]
    reason: Literal["no_email", "refused", "not_asked"] | None = None


class AudienceSummary(BaseSchema):
    """The counts the compose screen shows before anything is sent.

    `not_asked` is separate from `refused` because they call for opposite
    actions: ask them, or leave them alone.
    """

    total: int
    pending: int
    skipped_no_email: int
    skipped_refused: int
    skipped_not_asked: int
