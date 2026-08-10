"""add member consents

Revision ID: d94b1f7c2a58
Revises: c81f4a2e6b03
Create Date: 2026-08-10 23:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d94b1f7c2a58"
down_revision: str | None = "c81f4a2e6b03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # An append-only ledger, not three booleans on the member: a consent has to
    # be provable and a withdrawal has to be as easy as the consent was, and
    # neither survives a column that gets overwritten.
    op.create_table(
        "member_consents",
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
            sa.ForeignKey("members.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("granted", sa.Boolean(), nullable=False),
        # When the member said it, not when the row was written: a paper form
        # recorded weeks later carries the date it was signed.
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("recorded_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_member_consents_current",
        "member_consents",
        ["tenant_id", "member_id", "kind", "recorded_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_member_consents_current", table_name="member_consents")
    op.drop_table("member_consents")
