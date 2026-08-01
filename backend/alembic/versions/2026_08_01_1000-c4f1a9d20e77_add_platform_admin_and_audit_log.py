"""add platform admin flag and admin audit log

Revision ID: c4f1a9d20e77
Revises: b8c2e5f31a09
Create Date: 2026-08-01 10:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c4f1a9d20e77'
down_revision: str | None = 'b8c2e5f31a09'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "is_superuser",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    # The server default exists only to backfill existing rows. Dropping it
    # forces the application to state the value explicitly, so a future insert
    # path cannot create a superuser by omission.
    op.alter_column("users", "is_superuser", server_default=None)

    op.create_table(
        "admin_audit_log",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("impersonator_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("target_type", sa.String(length=50), nullable=True),
        sa.Column("target_id", sa.Uuid(), nullable=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["impersonator_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_admin_audit_log_actor_user_id", "admin_audit_log", ["actor_user_id"]
    )
    op.create_index(
        "ix_admin_audit_log_impersonator_id", "admin_audit_log", ["impersonator_id"]
    )
    op.create_index("ix_admin_audit_log_created_at", "admin_audit_log", ["created_at"])
    op.create_index(
        "ix_admin_audit_log_actor_created",
        "admin_audit_log",
        ["actor_user_id", "created_at"],
    )
    op.create_index(
        "ix_admin_audit_log_tenant_created",
        "admin_audit_log",
        ["tenant_id", "created_at"],
    )
    op.create_index(
        "ix_admin_audit_log_action_created",
        "admin_audit_log",
        ["action", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_admin_audit_log_action_created", table_name="admin_audit_log")
    op.drop_index("ix_admin_audit_log_tenant_created", table_name="admin_audit_log")
    op.drop_index("ix_admin_audit_log_actor_created", table_name="admin_audit_log")
    op.drop_index("ix_admin_audit_log_created_at", table_name="admin_audit_log")
    op.drop_index("ix_admin_audit_log_impersonator_id", table_name="admin_audit_log")
    op.drop_index("ix_admin_audit_log_actor_user_id", table_name="admin_audit_log")
    op.drop_table("admin_audit_log")
    op.drop_column("users", "is_superuser")
