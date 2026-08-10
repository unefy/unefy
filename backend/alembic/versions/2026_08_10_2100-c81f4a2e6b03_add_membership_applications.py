"""add membership applications

Revision ID: c81f4a2e6b03
Revises: b3c07d5a91f4
Create Date: 2026-08-10 21:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c81f4a2e6b03"
down_revision: str | None = "b3c07d5a91f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Applicants, not members: admission is a decision the board takes, and a
    # public form takes no decisions. Their own table because their data has a
    # different purpose and a different retention than a member's, and because
    # a pending row must never reach a member list, a due or a §14 evaluation.
    op.create_table(
        "membership_applications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("first_name", sa.String(length=255), nullable=False),
        sa.Column("last_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("mobile", sa.String(length=50), nullable=True),
        sa.Column("birthday", sa.Date(), nullable=True),
        sa.Column("gender", sa.String(length=20), nullable=True),
        sa.Column("street", sa.String(length=255), nullable=True),
        sa.Column("zip_code", sa.String(length=20), nullable=True),
        sa.Column("city", sa.String(length=255), nullable=True),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column(
            "fee_type_id",
            sa.Uuid(),
            sa.ForeignKey("fee_types.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "division_id",
            sa.Uuid(),
            sa.ForeignKey("divisions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("iban", sa.String(length=34), nullable=True),
        sa.Column("bic", sa.String(length=11), nullable=True),
        sa.Column("account_holder", sa.String(length=255), nullable=True),
        sa.Column("sepa_mandate_date", sa.Date(), nullable=True),
        sa.Column("privacy_accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consent_photos", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("consent_newsletter", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("consent_directory", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column(
            "member_id",
            sa.Uuid(),
            sa.ForeignKey("members.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        # Enforced here rather than in whichever service happens to write the
        # row: a decided application names who decided it, and exactly the
        # accepted ones point at a member.
        sa.CheckConstraint(
            "(status = 'pending' AND decided_at IS NULL)"
            " OR (status IN ('accepted', 'rejected') AND decided_at IS NOT NULL)",
            name="ck_applications_decision_shape",
        ),
        sa.CheckConstraint(
            "(status = 'accepted') = (member_id IS NOT NULL)",
            name="ck_applications_member_shape",
        ),
    )
    op.create_index(
        "ix_applications_tenant_status", "membership_applications", ["tenant_id", "status"]
    )

    # Off for every existing club. This is the only endpoint an unauthenticated
    # stranger can write through, so switching it on by migration would be a
    # decision taken on behalf of clubs that never asked for it.
    op.add_column(
        "tenants",
        sa.Column(
            "applications_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("tenants", "applications_enabled")
    op.drop_index("ix_applications_tenant_status", table_name="membership_applications")
    op.drop_table("membership_applications")
