"""add seed_version to members

Revoking a member's check-in codes. A seed is a bearer credential, and until
this column the only way to take one away from a lost phone was to wait out the
grace window — three days in which whoever found it could check that member in.
Bumping the version rehashes the seed, so every device holding an old one is cut
off at once.

Zero is the default and hashes exactly as before the column existed, so applying
this invalidates nothing already out on a phone.

Revision ID: f27bf1f0eb7f
Revises: 52566de238f5
Create Date: 2026-08-09 08:50:48.167494

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "f27bf1f0eb7f"
down_revision: str | None = "52566de238f5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "members",
        sa.Column("seed_version", sa.Integer(), server_default="0", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("members", "seed_version")
