"""add generic events and registrations tables

Revision ID: e5a3c8d94f12
Revises: d8e2f7b53c21
Create Date: 2026-07-26 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5a3c8d94f12'
down_revision: Union[str, None] = 'd8e2f7b53c21'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('events',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('event_type', sa.String(length=50), nullable=False),
    sa.Column('location', sa.String(length=255), nullable=True),
    sa.Column('starts_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('ends_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('all_day', sa.Boolean(), nullable=False),
    sa.Column('registration_required', sa.Boolean(), nullable=False),
    sa.Column('registration_deadline', sa.DateTime(timezone=True), nullable=True),
    sa.Column('max_participants', sa.Integer(), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('tenant_id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by', sa.Uuid(), nullable=True),
    sa.Column('updated_by', sa.Uuid(), nullable=True),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_events_tenant_id'), 'events', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_events_deleted_at'), 'events', ['deleted_at'], unique=False)
    op.create_index('ix_events_tenant_starts', 'events', ['tenant_id', 'starts_at'], unique=False)

    op.create_table('event_registrations',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('event_id', sa.Uuid(), nullable=False),
    sa.Column('member_id', sa.Uuid(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('tenant_id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by', sa.Uuid(), nullable=True),
    sa.Column('updated_by', sa.Uuid(), nullable=True),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['event_id'], ['events.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['member_id'], ['members.id'], ),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tenant_id', 'event_id', 'member_id')
    )
    op.create_index(op.f('ix_event_registrations_tenant_id'), 'event_registrations', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_event_registrations_deleted_at'), 'event_registrations', ['deleted_at'], unique=False)
    op.create_index('ix_event_registrations_tenant_event', 'event_registrations', ['tenant_id', 'event_id'], unique=False)
    op.create_index('ix_event_registrations_tenant_member', 'event_registrations', ['tenant_id', 'member_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_event_registrations_tenant_member', table_name='event_registrations')
    op.drop_index('ix_event_registrations_tenant_event', table_name='event_registrations')
    op.drop_index(op.f('ix_event_registrations_deleted_at'), table_name='event_registrations')
    op.drop_index(op.f('ix_event_registrations_tenant_id'), table_name='event_registrations')
    op.drop_table('event_registrations')
    op.drop_index('ix_events_tenant_starts', table_name='events')
    op.drop_index(op.f('ix_events_deleted_at'), table_name='events')
    op.drop_index(op.f('ix_events_tenant_id'), table_name='events')
    op.drop_table('events')
