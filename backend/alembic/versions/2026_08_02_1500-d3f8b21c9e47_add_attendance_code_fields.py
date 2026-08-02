"""add attendance code fields

Revision ID: d3f8b21c9e47
Revises: c7d4a9e15b28
Create Date: 2026-08-02 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d3f8b21c9e47"
down_revision: str | None = "c7d4a9e15b28"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The pseudonym the rotating QR carries instead of a member id. Nullable:
    # it is minted the first time a member asks for a seed, so clubs that never
    # scan never grow one.
    op.add_column("members", sa.Column("attendance_ref", sa.String(length=16), nullable=True))
    # Partial, because "no ref yet" is the normal state and NULLs must not
    # collide with each other.
    op.create_index(
        "uq_members_tenant_attendance_ref",
        "members",
        ["tenant_id", "attendance_ref"],
        unique=True,
        postgresql_where=sa.text("attendance_ref IS NOT NULL"),
    )

    # The short clock for the check-in context. The evidence layer already has
    # `attendance_retention_years`; this is the weeks-not-years counterpart.
    op.add_column(
        "tenants",
        sa.Column(
            "attendance_context_retention_days",
            sa.Integer(),
            nullable=False,
            server_default="90",
        ),
    )


def downgrade() -> None:
    op.drop_column("tenants", "attendance_context_retention_days")
    op.drop_index("uq_members_tenant_attendance_ref", table_name="members")
    op.drop_column("members", "attendance_ref")
