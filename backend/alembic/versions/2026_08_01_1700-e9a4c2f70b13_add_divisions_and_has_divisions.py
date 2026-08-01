"""add divisions table and tenants.has_divisions, backfill a primary division

Revision ID: e9a4c2f70b13
Revises: d7e3b1c85f42
Create Date: 2026-08-01 17:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e9a4c2f70b13'
down_revision: str | None = 'd7e3b1c85f42'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column(
            "has_divisions", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.alter_column("tenants", "has_divisions", server_default=None)

    op.create_table(
        "divisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("sport_id", sa.Uuid(), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
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
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["sport_id"], ["sports.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "name"),
    )
    op.create_index("ix_divisions_tenant_id", "divisions", ["tenant_id"])
    op.create_index("ix_divisions_sport_id", "divisions", ["sport_id"])
    op.create_index(
        "ix_divisions_tenant_primary", "divisions", ["tenant_id", "is_primary"]
    )

    # Existing clubs predate the concept. They are all shooting clubs (that was
    # the only sport in the catalog), so each gets one primary division named
    # after itself — the same shape `create_club` produces from now on.
    op.get_bind().execute(
        sa.text(
            "INSERT INTO divisions (id, tenant_id, name, sport_id, is_primary)"
            " SELECT gen_random_uuid(), t.id, t.name,"
            " (SELECT id FROM sports WHERE key = 'shooting'), true"
            " FROM tenants t"
            " WHERE NOT EXISTS (SELECT 1 FROM divisions d WHERE d.tenant_id = t.id)"
        )
    )


def downgrade() -> None:
    op.drop_index("ix_divisions_tenant_primary", table_name="divisions")
    op.drop_index("ix_divisions_sport_id", table_name="divisions")
    op.drop_index("ix_divisions_tenant_id", table_name="divisions")
    op.drop_table("divisions")
    op.drop_column("tenants", "has_divisions")
