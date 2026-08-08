"""add last_seed_fetch_at to members

The app refreshes a member's check-in seed from three places, none of which is
guaranteed to run: the foreground keeper needs the app open, the periodic worker
is deferred by Doze and by each vendor's battery manager, and the push wake-up
only fires when something happens in the club. Whether that adds up to a fresh
seed on real phones is not answerable from here — this column is what makes it
measurable, one row per member, written on handout.

Revision ID: 52566de238f5
Revises: e7b3d92c4a15
Create Date: 2026-08-09 01:05:26.082694

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "52566de238f5"
down_revision: str | None = "e7b3d92c4a15"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "members", sa.Column("last_seed_fetch_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("members", "last_seed_fetch_at")
