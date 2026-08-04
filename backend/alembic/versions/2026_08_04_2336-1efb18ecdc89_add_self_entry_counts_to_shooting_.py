"""add self-entry counts to shooting certificates

Revision ID: 1efb18ecdc89
Revises: c9d4e82b5f61
Create Date: 2026-08-04 23:36:47.090219

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1efb18ecdc89"
down_revision: str | None = "c9d4e82b5f61"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # How many of the certified days rest on nothing but the member's own word,
    # and how many of *those* the member spent checking other people in. Frozen
    # on the certificate and part of its `content_hash`, because a qualification
    # that can be edited away afterwards qualifies nothing.
    #
    # A server default only so the columns can be added NOT NULL. Nothing relies
    # on it: `issue_certificate` always supplies both values, and no certificate
    # existed when this ran — which is also why extending the hashed field set
    # invalidates nothing.
    op.add_column(
        "shooting_proof_certificates",
        sa.Column("self_certified_days", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "shooting_proof_certificates",
        sa.Column("corroborated_self_days", sa.Integer(), nullable=False, server_default="0"),
    )
    # Dropped again, so a future insert that forgets these fails loudly instead
    # of quietly certifying zero self-entries.
    op.alter_column("shooting_proof_certificates", "self_certified_days", server_default=None)
    op.alter_column("shooting_proof_certificates", "corroborated_self_days", server_default=None)


def downgrade() -> None:
    op.drop_column("shooting_proof_certificates", "corroborated_self_days")
    op.drop_column("shooting_proof_certificates", "self_certified_days")
