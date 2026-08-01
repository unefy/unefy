"""add tenant timezone

Revision ID: b6e2f81c4a37
Revises: a1c7f3d92b84
Create Date: 2026-08-01 20:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b6e2f81c4a37'
down_revision: Union[str, None] = 'a1c7f3d92b84'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Europe/Berlin as the default rather than UTC: the server clock is not a
    # club's calendar day, and every existing tenant is a DACH club. Clubs
    # elsewhere change it; nothing else in the code assumes a zone.
    op.add_column(
        'tenants',
        sa.Column(
            'timezone',
            sa.String(length=64),
            server_default='Europe/Berlin',
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column('tenants', 'timezone')
