"""add push devices

Revision ID: a8c5e19d7f36
Revises: f2b9d84c1a07
Create Date: 2026-08-03 21:40:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a8c5e19d7f36"
down_revision: str | None = "f2b9d84c1a07"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "push_devices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("platform", sa.String(length=20), nullable=False),
        sa.Column("token", sa.String(length=512), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token"),
    )
    op.create_index("ix_push_devices_tenant_id", "push_devices", ["tenant_id"])
    op.create_index("ix_push_devices_user_id", "push_devices", ["user_id"])
    # The fan-out asks "which tokens in this club may hear about entity X".
    op.create_index("ix_push_devices_tenant_role", "push_devices", ["tenant_id", "role"])


def downgrade() -> None:
    op.drop_index("ix_push_devices_tenant_role", table_name="push_devices")
    op.drop_index("ix_push_devices_user_id", table_name="push_devices")
    op.drop_index("ix_push_devices_tenant_id", table_name="push_devices")
    op.drop_table("push_devices")
