"""add donation receipts and the club's tax exemption data

Revision ID: f1a83c9e0b47
Revises: e07c3b5d8a19
Create Date: 2026-08-11 10:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1a83c9e0b47"
down_revision: str | None = "e07c3b5d8a19"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # What a donation receipt has to state about the club. Prescribed content:
    # the official template requires naming which notice recognises the club,
    # from when, and for what.
    op.add_column("tenants", sa.Column("nonprofit_purposes", sa.String(length=500), nullable=True))
    op.add_column("tenants", sa.Column("tax_exemption_kind", sa.String(length=30), nullable=True))
    op.add_column("tenants", sa.Column("tax_exemption_date", sa.Date(), nullable=True))
    op.add_column("tenants", sa.Column("tax_exemption_period", sa.Integer(), nullable=True))
    # Off for every existing club, and for a sports club it stays off: fees to
    # a club promoting sport are not deductible (§ 10b Abs. 1 Satz 8 EStG).
    op.add_column(
        "tenants",
        sa.Column(
            "membership_fees_deductible",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    # A prescribed form, frozen as it was issued — including the club's own tax
    # data, because a receipt from 2024 has to keep saying what was true then.
    op.create_table(
        "donation_receipts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "member_id",
            sa.Uuid(),
            sa.ForeignKey("members.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("donor_name", sa.String(length=255), nullable=False),
        sa.Column("donor_address", sa.String(length=500), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("received_on", sa.Date(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("is_expense_waiver", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("club_name", sa.String(length=255), nullable=False),
        sa.Column("club_address", sa.String(length=500), nullable=True),
        sa.Column("exemption_kind", sa.String(length=30), nullable=False),
        sa.Column("exemption_date", sa.Date(), nullable=False),
        sa.Column("exemption_period", sa.Integer(), nullable=True),
        sa.Column("tax_office", sa.String(length=255), nullable=False),
        sa.Column("tax_number", sa.String(length=100), nullable=False),
        sa.Column("purposes", sa.String(length=500), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("issued_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("revoke_reason", sa.Text(), nullable=True),
        sa.Column("verification_code", sa.String(length=32), nullable=False, unique=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        # A receipt over nothing is not a receipt.
        sa.CheckConstraint("amount > 0", name="ck_donation_receipts_amount_positive"),
        sa.CheckConstraint(
            "kind IN ('geldzuwendung', 'mitgliedsbeitrag')",
            name="ck_donation_receipts_kind",
        ),
    )
    op.create_index(
        "ix_donation_receipts_tenant_received",
        "donation_receipts",
        ["tenant_id", "received_on"],
    )
    op.create_index(
        "ix_donation_receipts_tenant_member", "donation_receipts", ["tenant_id", "member_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_donation_receipts_tenant_member", table_name="donation_receipts")
    op.drop_index("ix_donation_receipts_tenant_received", table_name="donation_receipts")
    op.drop_table("donation_receipts")
    op.drop_column("tenants", "membership_fees_deductible")
    op.drop_column("tenants", "tax_exemption_period")
    op.drop_column("tenants", "tax_exemption_date")
    op.drop_column("tenants", "tax_exemption_kind")
    op.drop_column("tenants", "nonprofit_purposes")
