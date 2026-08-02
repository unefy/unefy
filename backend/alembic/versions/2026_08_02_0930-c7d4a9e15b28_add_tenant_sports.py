"""add tenant_sports

Revision ID: c7d4a9e15b28
Revises: b6e2f81c4a37
Create Date: 2026-08-02 09:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7d4a9e15b28"
down_revision: str | None = "b6e2f81c4a37"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The missing edge between a club and its sports. `sports.modules` already
    # maps a sport to the code modules it activates, but nothing said which
    # sports a club runs, so module resolution had no starting point.
    op.create_table(
        "tenant_sports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("sport_id", sa.Uuid(), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
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
        sa.ForeignKeyConstraint(["sport_id"], ["sports.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "sport_id", name="uq_tenant_sports_tenant_sport"),
    )
    op.create_index("ix_tenant_sports_tenant_id", "tenant_sports", ["tenant_id"])
    op.create_index("ix_tenant_sports_sport_id", "tenant_sports", ["sport_id"])
    op.create_index(
        "ix_tenant_sports_tenant_primary", "tenant_sports", ["tenant_id", "is_primary"]
    )


def downgrade() -> None:
    op.drop_index("ix_tenant_sports_tenant_primary", table_name="tenant_sports")
    op.drop_index("ix_tenant_sports_sport_id", table_name="tenant_sports")
    op.drop_index("ix_tenant_sports_tenant_id", table_name="tenant_sports")
    op.drop_table("tenant_sports")
