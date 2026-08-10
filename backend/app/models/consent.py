import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantModel

#: The consents a club asks for. Deliberately a Python constant rather than a
#: database enum: adding one is a code change, not a migration, and a club that
#: needs a fourth should not need a schema change to get it.
CONSENT_KINDS = ("photos", "newsletter", "directory")

#: Where the answer came from. "application" is the join form, "self" the
#: member's own page, "board" somebody in the club recording a paper form.
CONSENT_SOURCES = ("application", "self", "board")


class MemberConsent(TenantModel):
    """One thing a member said about one consent, at one moment.

    An append-only ledger rather than three booleans on the member, because a
    consent has to be provable and a withdrawal has to be as easy as the
    consent was — and neither survives a column that gets overwritten. The
    current answer is the newest row for that kind; everything before it is the
    record of how it got there.

    Nothing here is ever updated or deleted. A ledger you can edit proves
    nothing, which is the whole reason for having one.

    Three states, not two: granted, refused, and *never asked*. The absence of
    a row is the third, and it is not the same as a refusal — see
    `MemberRepository.directory`.
    """

    __tablename__ = "member_consents"
    __table_args__ = (
        # The lookup this table exists for: the newest row per member and kind.
        Index(
            "ix_member_consents_current",
            "tenant_id",
            "member_id",
            "kind",
            "recorded_at",
        ),
    )

    member_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("members.id", ondelete="CASCADE"), nullable=False
    )

    #: One of `CONSENT_KINDS`.
    kind: Mapped[str] = mapped_column(String(30), nullable=False)

    #: True when given, false when refused or withdrawn. One column for both
    #: directions: a withdrawal is not a different kind of event, it is the
    #: same question answered the other way.
    granted: Mapped[bool] = mapped_column(Boolean, nullable=False)

    #: When the member said it — not when the row was written. A paper form
    #: recorded weeks later carries the date it was signed.
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    #: One of `CONSENT_SOURCES`.
    source: Mapped[str] = mapped_column(String(20), nullable=False)

    #: Who entered it. Null when the member said it themselves through the
    #: public join form, where there is no account yet.
    recorded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)

    #: Free text for the club: "Papierformular vom 3.5.", "telefonisch".
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
