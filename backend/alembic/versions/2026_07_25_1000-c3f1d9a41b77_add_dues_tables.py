"""add dues tables

Revision ID: c3f1d9a41b77
Revises: a4b24ba82095
Create Date: 2026-07-25 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3f1d9a41b77'
down_revision: Union[str, None] = 'a4b24ba82095'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('fee_types',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('interval', sa.String(length=20), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('tenant_id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by', sa.Uuid(), nullable=True),
    sa.Column('updated_by', sa.Uuid(), nullable=True),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tenant_id', 'name')
    )
    op.create_index(op.f('ix_fee_types_tenant_id'), 'fee_types', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_fee_types_deleted_at'), 'fee_types', ['deleted_at'], unique=False)
    op.create_index('ix_fee_types_tenant_active', 'fee_types', ['tenant_id', 'is_active'], unique=False)

    op.create_table('member_fees',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('member_id', sa.Uuid(), nullable=False),
    sa.Column('fee_type_id', sa.Uuid(), nullable=False),
    sa.Column('valid_from', sa.Date(), nullable=False),
    sa.Column('valid_to', sa.Date(), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('tenant_id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by', sa.Uuid(), nullable=True),
    sa.Column('updated_by', sa.Uuid(), nullable=True),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['fee_type_id'], ['fee_types.id'], ),
    sa.ForeignKeyConstraint(['member_id'], ['members.id'], ),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_member_fees_tenant_id'), 'member_fees', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_member_fees_deleted_at'), 'member_fees', ['deleted_at'], unique=False)
    op.create_index('ix_member_fees_tenant_member', 'member_fees', ['tenant_id', 'member_id'], unique=False)
    op.create_index('ix_member_fees_tenant_fee_type', 'member_fees', ['tenant_id', 'fee_type_id'], unique=False)

    op.create_table('dues',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('member_id', sa.Uuid(), nullable=False),
    sa.Column('fee_type_id', sa.Uuid(), nullable=False),
    sa.Column('fee_name', sa.String(length=255), nullable=False),
    sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('period_start', sa.Date(), nullable=False),
    sa.Column('period_end', sa.Date(), nullable=False),
    sa.Column('due_date', sa.Date(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('paid_at', sa.Date(), nullable=True),
    sa.Column('payment_method', sa.String(length=50), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('tenant_id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by', sa.Uuid(), nullable=True),
    sa.Column('updated_by', sa.Uuid(), nullable=True),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['fee_type_id'], ['fee_types.id'], ),
    sa.ForeignKeyConstraint(['member_id'], ['members.id'], ),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tenant_id', 'member_id', 'fee_type_id', 'period_start')
    )
    op.create_index(op.f('ix_dues_tenant_id'), 'dues', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_dues_deleted_at'), 'dues', ['deleted_at'], unique=False)
    op.create_index('ix_dues_tenant_status', 'dues', ['tenant_id', 'status'], unique=False)
    op.create_index('ix_dues_tenant_member', 'dues', ['tenant_id', 'member_id'], unique=False)
    op.create_index('ix_dues_tenant_period', 'dues', ['tenant_id', 'period_start'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_dues_tenant_period', table_name='dues')
    op.drop_index('ix_dues_tenant_member', table_name='dues')
    op.drop_index('ix_dues_tenant_status', table_name='dues')
    op.drop_index(op.f('ix_dues_deleted_at'), table_name='dues')
    op.drop_index(op.f('ix_dues_tenant_id'), table_name='dues')
    op.drop_table('dues')
    op.drop_index('ix_member_fees_tenant_fee_type', table_name='member_fees')
    op.drop_index('ix_member_fees_tenant_member', table_name='member_fees')
    op.drop_index(op.f('ix_member_fees_deleted_at'), table_name='member_fees')
    op.drop_index(op.f('ix_member_fees_tenant_id'), table_name='member_fees')
    op.drop_table('member_fees')
    op.drop_index('ix_fee_types_tenant_active', table_name='fee_types')
    op.drop_index(op.f('ix_fee_types_deleted_at'), table_name='fee_types')
    op.drop_index(op.f('ix_fee_types_tenant_id'), table_name='fee_types')
    op.drop_table('fee_types')
