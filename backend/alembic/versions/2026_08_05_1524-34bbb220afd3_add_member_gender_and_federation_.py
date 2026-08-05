"""add member gender and federation memberships

Revision ID: 34bbb220afd3
Revises: 1efb18ecdc89
Create Date: 2026-08-05 15:24:39.332210

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "34bbb220afd3"
down_revision: str | None = "1efb18ecdc89"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("members", sa.Column("gender", sa.String(length=20), nullable=True))

    op.create_table(
        "member_federation_memberships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("member_id", sa.Uuid(), nullable=False),
        sa.Column("federation", sa.String(length=100), nullable=False),
        sa.Column("federation_number", sa.String(length=50), nullable=True),
        sa.Column("joined_at", sa.Date(), nullable=True),
        sa.Column("left_at", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "member_id", "federation"),
    )
    op.create_index(
        "ix_member_federation_memberships_tenant_id",
        "member_federation_memberships",
        ["tenant_id"],
    )
    op.create_index(
        "ix_member_federation_memberships_member_id",
        "member_federation_memberships",
        ["member_id"],
    )
    op.create_index(
        "ix_member_federation_memberships_member",
        "member_federation_memberships",
        ["tenant_id", "member_id"],
    )
    op.create_index(
        "ix_member_federation_memberships_deleted_at",
        "member_federation_memberships",
        ["deleted_at"],
    )


def downgrade() -> None:
    op.drop_table("member_federation_memberships")
    op.drop_column("members", "gender")
