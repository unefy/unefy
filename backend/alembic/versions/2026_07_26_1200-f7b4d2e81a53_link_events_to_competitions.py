"""link events to competitions and sessions

Revision ID: f7b4d2e81a53
Revises: e5a3c8d94f12
Create Date: 2026-07-26 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f7b4d2e81a53'
down_revision: Union[str, None] = 'e5a3c8d94f12'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('events', sa.Column('competition_id', sa.Uuid(), nullable=True))
    op.add_column('events', sa.Column('session_id', sa.Uuid(), nullable=True))
    op.create_foreign_key(
        'fk_events_competition_id', 'events', 'competitions',
        ['competition_id'], ['id'], ondelete='SET NULL',
    )
    op.create_foreign_key(
        'fk_events_session_id', 'events', 'sessions',
        ['session_id'], ['id'], ondelete='SET NULL',
    )
    op.create_index('ix_events_tenant_session', 'events', ['tenant_id', 'session_id'], unique=False)
    op.create_index('ix_events_tenant_competition', 'events', ['tenant_id', 'competition_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_events_tenant_competition', table_name='events')
    op.drop_index('ix_events_tenant_session', table_name='events')
    op.drop_constraint('fk_events_session_id', 'events', type_='foreignkey')
    op.drop_constraint('fk_events_competition_id', 'events', type_='foreignkey')
    op.drop_column('events', 'session_id')
    op.drop_column('events', 'competition_id')
