import uuid
from datetime import datetime

from pydantic import Field

from app.models.consent import CONSENT_KINDS
from app.schemas.base import BaseSchema

KIND_PATTERN = f"^({'|'.join(CONSENT_KINDS)})$"


class ConsentRecord(BaseSchema):
    """Recording an answer. Granting and withdrawing are the same call.

    No separate "revoke" endpoint on purpose: a withdrawal that is harder to
    perform than the consent was is not a valid withdrawal, and two endpoints
    would invite exactly that asymmetry.
    """

    kind: str = Field(pattern=KIND_PATTERN)
    granted: bool
    #: When the member said it. Defaults to now; a board recording a paper form
    #: passes the date it was signed.
    recorded_at: datetime | None = None
    note: str | None = Field(default=None, max_length=1000)


class ConsentEntry(BaseSchema):
    """One row of the ledger."""

    id: uuid.UUID
    kind: str
    granted: bool
    recorded_at: datetime
    source: str
    note: str | None = None


class ConsentState(BaseSchema):
    """The current answer for one kind.

    `granted` is null when the member was never asked — which is not the same
    as a refusal, and the two must not collapse into one boolean.
    """

    kind: str
    granted: bool | None
    since: datetime | None = None
    source: str | None = None


class ConsentOverview(BaseSchema):
    current: list[ConsentState]
    history: list[ConsentEntry]
