"""add sepa fields to tenants and members

Revision ID: d8e2f7b53c21
Revises: c3f1d9a41b77
Create Date: 2026-07-25 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8e2f7b53c21'
down_revision: Union[str, None] = 'c3f1d9a41b77'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tenants', sa.Column('sepa_creditor_id', sa.String(length=35), nullable=True))
    op.add_column('tenants', sa.Column('iban', sa.String(length=34), nullable=True))
    op.add_column('tenants', sa.Column('bic', sa.String(length=11), nullable=True))
    op.add_column('members', sa.Column('iban', sa.String(length=34), nullable=True))
    op.add_column('members', sa.Column('bic', sa.String(length=11), nullable=True))
    op.add_column('members', sa.Column('account_holder', sa.String(length=255), nullable=True))
    op.add_column('members', sa.Column('sepa_mandate_reference', sa.String(length=35), nullable=True))
    op.add_column('members', sa.Column('sepa_mandate_date', sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column('members', 'sepa_mandate_date')
    op.drop_column('members', 'sepa_mandate_reference')
    op.drop_column('members', 'account_holder')
    op.drop_column('members', 'bic')
    op.drop_column('members', 'iban')
    op.drop_column('tenants', 'bic')
    op.drop_column('tenants', 'iban')
    op.drop_column('tenants', 'sepa_creditor_id')
