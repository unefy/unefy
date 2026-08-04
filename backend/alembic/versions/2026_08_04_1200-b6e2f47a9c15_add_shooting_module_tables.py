"""add shooting module tables

Revision ID: b6e2f47a9c15
Revises: a8c5e19d7f36
Create Date: 2026-08-04 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b6e2f47a9c15"
down_revision: str | None = "a8c5e19d7f36"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1:1 extension of an attendance record with what was shot. Module data,
    # so a separate table rather than columns on the core record.
    op.create_table(
        "shooting_record_details",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("attendance_record_id", sa.Uuid(), nullable=False),
        sa.Column("club_discipline_id", sa.Uuid(), nullable=True),
        # Typed column, not JSONB: the §14 evaluation filters on it.
        sa.Column("weapon_category", sa.String(length=20), nullable=True),
        sa.Column("rounds_fired", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(
            ["attendance_record_id"], ["attendance_records.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["club_discipline_id"], ["club_disciplines.id"], ondelete="SET NULL"
        ),
        sa.UniqueConstraint("attendance_record_id"),
        sa.CheckConstraint(
            "weapon_category IN ('kurzwaffe', 'langwaffe', 'luftdruck')",
            name="ck_shooting_details_weapon_category",
        ),
        sa.CheckConstraint("rounds_fired >= 0", name="ck_shooting_details_rounds_nonnegative"),
    )
    op.create_index(
        "ix_shooting_record_details_tenant_id", "shooting_record_details", ["tenant_id"]
    )

    # Evaluation thresholds are configuration, never code: the §14 rule varies
    # by state and authority, so deliberately no numbers in this migration —
    # clubs create their rules themselves.
    op.create_table(
        "shooting_proof_rules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("rule_key", sa.String(length=50), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("window_months", sa.Integer(), nullable=False),
        sa.Column("min_total_days", sa.Integer(), nullable=True),
        sa.Column("min_distinct_months", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.CheckConstraint(
            "min_total_days IS NOT NULL OR min_distinct_months IS NOT NULL",
            name="ck_shooting_rules_has_criterion",
        ),
        sa.CheckConstraint("window_months > 0", name="ck_shooting_rules_window_positive"),
    )
    op.create_index("ix_shooting_proof_rules_tenant_id", "shooting_proof_rules", ["tenant_id"])
    op.create_index(
        "uq_shooting_rules_tenant_key",
        "shooting_proof_rules",
        ["tenant_id", "rule_key"],
        unique=True,
    )

    # The issued proof, frozen at the moment of issuing. `record_ids` are
    # plain UUIDs, not foreign keys — the retention job must be able to remove
    # the records years later without tearing out the certificate's anchor.
    op.create_table(
        "shooting_proof_certificates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("member_id", sa.Uuid(), nullable=False),
        sa.Column("rule_key", sa.String(length=50), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("session_count", sa.Integer(), nullable=False),
        sa.Column("months_covered", sa.Integer(), nullable=False),
        sa.Column("result", sa.String(length=10), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("issued_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("revoke_reason", sa.Text(), nullable=True),
        sa.Column("record_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("verification_code", sa.String(length=32), nullable=False),
        sa.Column("document_ref", sa.String(length=255), nullable=True),
        sa.Column("seal", sa.LargeBinary(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"]),
        # Globally unique: the public verify page is unauthenticated and has
        # no tenant context to scope the lookup by.
        sa.UniqueConstraint("verification_code"),
        sa.CheckConstraint(
            "result IN ('passed', 'failed')", name="ck_shooting_certificates_result"
        ),
    )
    op.create_index(
        "ix_shooting_proof_certificates_tenant_id", "shooting_proof_certificates", ["tenant_id"]
    )
    op.create_index(
        "ix_shooting_certificates_tenant_member",
        "shooting_proof_certificates",
        ["tenant_id", "member_id"],
    )


def downgrade() -> None:
    op.drop_table("shooting_proof_certificates")
    op.drop_table("shooting_proof_rules")
    op.drop_table("shooting_record_details")
