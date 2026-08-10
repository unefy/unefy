import uuid
from datetime import date

from sqlalchemy import Boolean, Date, Integer, String, Text, Uuid, false
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

# Kept as a constant so the migration and the model carry the identical text,
# and so removing the caveat later is a single, obvious edit.
ATTENDANCE_RETENTION_COMMENT = (
    "UNVERIFIED ASSUMPTION: the default of 10 years is a deliberate choice, "
    "not a confirmed requirement. To be checked against the shooting-sport "
    "association's rules; configurable per club so it can be corrected. "
    "Remove this note once the requirement is confirmed."
)


class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    # Contact
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Address
    street: Mapped[str | None] = mapped_column(String(255), nullable=True)
    zip_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    state: Mapped[str | None] = mapped_column(String(255), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True, default="Deutschland")

    # Club details
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    founded_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    registration_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    registration_court: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tax_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tax_office: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_nonprofit: Mapped[bool] = mapped_column(default=False, nullable=False)
    nonprofit_since: Mapped[date | None] = mapped_column(Date, nullable=True)

    # SEPA creditor data (for direct debit collection of dues)
    sepa_creditor_id: Mapped[str | None] = mapped_column(String(35), nullable=True)
    iban: Mapped[str | None] = mapped_column(String(34), nullable=True)
    bic: Mapped[str | None] = mapped_column(String(11), nullable=True)

    # Member number format
    # Template with variables: {PREFIX}, {YEAR}, {NUM:3} (zero-padded to N digits)
    # Examples: "{PREFIX}-{YEAR}-{NUM:3}" → "ESV-2026-001"
    member_number_format: Mapped[str] = mapped_column(
        String(100), nullable=False, default="{NUM:3}"
    )
    member_number_prefix: Mapped[str | None] = mapped_column(String(20), nullable=True)
    member_number_next: Mapped[int] = mapped_column(default=1, nullable=False)

    # Whether the club is organised in divisions (Sparten). Divisions always
    # exist in the data model; this only controls whether the UI shows them.
    has_divisions: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Whether the public join form accepts applications for this club. Off by
    # default, and deliberately so: this is the one endpoint an unauthenticated
    # stranger can write through, and switching it on for every existing club
    # at migration time would be a decision the clubs never made.
    applications_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )

    # The club's own time zone. Everything the club sees as "the evening of the
    # 7th" is resolved against this: the server runs in UTC, and a session that
    # opens at 00:30 local would otherwise be filed under the previous day.
    # Also the zone the web client formats times in, so a board member abroad
    # reads the same attendance list as one at home.
    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, default="Europe/Berlin", server_default="Europe/Berlin"
    )

    # How long attendance records are kept before the retention job removes
    # them. The note travels into the database as a column comment, so it is
    # visible to anyone reading the schema, not just this file.
    attendance_retention_years: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=10,
        server_default="10",
        comment=ATTENDANCE_RETENTION_COMMENT,
    )

    # The second clock. The technical context of a scan — which installation,
    # which scanning device, which counter — is a behavioural trail and lives
    # for weeks, while the record it belongs to lives for years. What survives
    # the deletion is the digest and the verdict on the record itself.
    attendance_context_retention_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=90,
        server_default="90",
    )

    # Configurable member status list (JSON array of {key, label} objects).
    # The DB-level default is English for neutrality; new tenants are seeded
    # with locale-appropriate labels at creation time (see core/seeds.py).
    member_statuses: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default=(
            '[{"key":"active","label":"Active"},'
            '{"key":"inactive","label":"Inactive"},'
            '{"key":"resigned","label":"Resigned"},'
            '{"key":"terminated","label":"Terminated"},'
            '{"key":"deceased","label":"Deceased"}]'
        ),
    )
