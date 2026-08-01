"""add attendance core tables and tenant audit log

Revision ID: a1c7f3d92b84
Revises: 84226652616f
Create Date: 2026-08-01 19:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a1c7f3d92b84'
down_revision: Union[str, None] = '84226652616f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Tenant configuration ---
    # The comment marks the default as an open question, in the schema itself.
    # It is removed only once the retention period has been confirmed with the
    # shooting-sport association.
    op.add_column(
        'tenants',
        sa.Column(
            'attendance_retention_years',
            sa.Integer(),
            server_default='10',
            nullable=False,
            comment=(
                "UNVERIFIED ASSUMPTION: the default of 10 years is a deliberate choice, "
                "not a confirmed requirement. To be checked against the shooting-sport "
                "association's rules; configurable per club so it can be corrected. "
                "Remove this note once the requirement is confirmed."
            ),
        ),
    )

    # --- Tenant-scoped audit log ---
    op.create_table('tenant_audit_log',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('actor_user_id', sa.Uuid(), nullable=True),
    sa.Column('impersonator_id', sa.Uuid(), nullable=True),
    sa.Column('action', sa.String(length=100), nullable=False),
    sa.Column('target_type', sa.String(length=50), nullable=False),
    sa.Column('target_id', sa.Uuid(), nullable=False),
    sa.Column('changes', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('reason', sa.Text(), nullable=True),
    sa.Column('ip_address', sa.String(length=45), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('tenant_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['actor_user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['impersonator_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tenant_audit_log_tenant_id'), 'tenant_audit_log', ['tenant_id'], unique=False)
    op.create_index('ix_tenant_audit_log_target', 'tenant_audit_log', ['tenant_id', 'target_type', 'target_id'], unique=False)
    op.create_index('ix_tenant_audit_log_tenant_created', 'tenant_audit_log', ['tenant_id', 'created_at'], unique=False)
    op.create_index('ix_tenant_audit_log_actor_created', 'tenant_audit_log', ['tenant_id', 'actor_user_id', 'created_at'], unique=False)

    # --- Attendance sessions ---
    op.create_table('attendance_sessions',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('division_id', sa.Uuid(), nullable=True),
    sa.Column('event_id', sa.Uuid(), nullable=True),
    sa.Column('location', sa.String(length=255), nullable=True),
    sa.Column('opens_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('closes_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('supervisor_member_id', sa.Uuid(), nullable=True),
    sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('closed_by', sa.Uuid(), nullable=True),
    sa.Column('close_hash', sa.String(length=64), nullable=True),
    sa.Column('tenant_id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by', sa.Uuid(), nullable=True),
    sa.Column('updated_by', sa.Uuid(), nullable=True),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['division_id'], ['divisions.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['event_id'], ['events.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['supervisor_member_id'], ['members.id'], ),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_attendance_sessions_tenant_id'), 'attendance_sessions', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_attendance_sessions_deleted_at'), 'attendance_sessions', ['deleted_at'], unique=False)
    op.create_index('ix_attendance_sessions_tenant_opens', 'attendance_sessions', ['tenant_id', 'opens_at'], unique=False)
    op.create_index('ix_attendance_sessions_tenant_status', 'attendance_sessions', ['tenant_id', 'status'], unique=False)
    op.create_index('ix_attendance_sessions_tenant_division', 'attendance_sessions', ['tenant_id', 'division_id'], unique=False)

    # --- Attendance records (evidence layer) ---
    op.create_table('attendance_records',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('session_id', sa.Uuid(), nullable=False),
    sa.Column('member_id', sa.Uuid(), nullable=False),
    sa.Column('occurred_on', sa.Date(), nullable=False),
    sa.Column('checked_in_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('checked_out_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('synced_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('method', sa.String(length=20), nullable=False),
    sa.Column('assurance', sa.String(length=10), nullable=False),
    sa.Column('verified_by_user_id', sa.Uuid(), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('context_digest', sa.String(length=64), nullable=True),
    sa.Column('context_verdict', sa.String(length=20), nullable=True),
    sa.Column('tenant_id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by', sa.Uuid(), nullable=True),
    sa.Column('updated_by', sa.Uuid(), nullable=True),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['session_id'], ['attendance_sessions.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['member_id'], ['members.id'], ),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_attendance_records_tenant_id'), 'attendance_records', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_attendance_records_deleted_at'), 'attendance_records', ['deleted_at'], unique=False)
    # Partial: a soft-deleted record is history. A member removed by mistake
    # must be able to check in again without resurrecting the corrected row.
    op.create_index(
        'uq_attendance_records_tenant_session_member',
        'attendance_records',
        ['tenant_id', 'session_id', 'member_id'],
        unique=True,
        postgresql_where=sa.text('deleted_at IS NULL'),
    )
    op.create_index('ix_attendance_tenant_member_date', 'attendance_records', ['tenant_id', 'member_id', 'occurred_on'], unique=False)
    op.create_index('ix_attendance_records_tenant_session', 'attendance_records', ['tenant_id', 'session_id'], unique=False)

    # --- Check-in context (short-lived layer) ---
    op.create_table('attendance_checkin_contexts',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('attendance_record_id', sa.Uuid(), nullable=False),
    sa.Column('install_id', sa.String(length=64), nullable=True),
    sa.Column('staff_device_id', sa.String(length=64), nullable=True),
    sa.Column('code_counter', sa.BigInteger(), nullable=True),
    sa.Column('user_agent', sa.String(length=512), nullable=True),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('tenant_id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['attendance_record_id'], ['attendance_records.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('attendance_record_id')
    )
    op.create_index(op.f('ix_attendance_checkin_contexts_tenant_id'), 'attendance_checkin_contexts', ['tenant_id'], unique=False)
    op.create_index('ix_attendance_contexts_expires', 'attendance_checkin_contexts', ['expires_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_attendance_contexts_expires', table_name='attendance_checkin_contexts')
    op.drop_index(op.f('ix_attendance_checkin_contexts_tenant_id'), table_name='attendance_checkin_contexts')
    op.drop_table('attendance_checkin_contexts')

    op.drop_index('ix_attendance_records_tenant_session', table_name='attendance_records')
    op.drop_index('ix_attendance_tenant_member_date', table_name='attendance_records')
    op.drop_index('uq_attendance_records_tenant_session_member', table_name='attendance_records')
    op.drop_index(op.f('ix_attendance_records_deleted_at'), table_name='attendance_records')
    op.drop_index(op.f('ix_attendance_records_tenant_id'), table_name='attendance_records')
    op.drop_table('attendance_records')

    op.drop_index('ix_attendance_sessions_tenant_division', table_name='attendance_sessions')
    op.drop_index('ix_attendance_sessions_tenant_status', table_name='attendance_sessions')
    op.drop_index('ix_attendance_sessions_tenant_opens', table_name='attendance_sessions')
    op.drop_index(op.f('ix_attendance_sessions_deleted_at'), table_name='attendance_sessions')
    op.drop_index(op.f('ix_attendance_sessions_tenant_id'), table_name='attendance_sessions')
    op.drop_table('attendance_sessions')

    op.drop_index('ix_tenant_audit_log_actor_created', table_name='tenant_audit_log')
    op.drop_index('ix_tenant_audit_log_tenant_created', table_name='tenant_audit_log')
    op.drop_index('ix_tenant_audit_log_target', table_name='tenant_audit_log')
    op.drop_index(op.f('ix_tenant_audit_log_tenant_id'), table_name='tenant_audit_log')
    op.drop_table('tenant_audit_log')

    op.drop_column('tenants', 'attendance_retention_years')
