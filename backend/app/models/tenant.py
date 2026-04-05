import uuid
from datetime import date

from sqlalchemy import Date, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


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

    # Member number format
    # Template with variables: {PREFIX}, {YEAR}, {NUM:3} (zero-padded to N digits)
    # Examples: "{PREFIX}-{YEAR}-{NUM:3}" → "ESV-2026-001"
    member_number_format: Mapped[str] = mapped_column(
        String(100), nullable=False, default="{NUM:3}"
    )
    member_number_prefix: Mapped[str | None] = mapped_column(String(20), nullable=True)
    member_number_next: Mapped[int] = mapped_column(default=1, nullable=False)

    # Configurable member status list (JSON array of {key, label} objects)
    member_statuses: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default='[{"key":"active","label":"Aktiv"},{"key":"inactive","label":"Inaktiv"},{"key":"resigned","label":"Ausgetreten"},{"key":"terminated","label":"Gekündigt"},{"key":"deceased","label":"Verstorben"}]',
    )
