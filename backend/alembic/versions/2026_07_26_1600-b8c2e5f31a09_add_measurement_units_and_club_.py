"""add measurement units and club disciplines

Revision ID: b8c2e5f31a09
Revises: 6d40b7e807b3
Create Date: 2026-07-26 16:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b8c2e5f31a09'
down_revision: str | None = '6d40b7e807b3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Keep in sync with app.core.seeds.MEASUREMENT_UNIT_SEEDS at migration time
DEFAULT_UNITS: list[tuple[str, str | None]] = [
    ("Ringe", None),
    ("Punkte", "Pkt."),
    ("Treffer", None),
    ("Sekunden", "s"),
    ("Minuten", "min"),
    ("Meter", "m"),
    ("Zentimeter", "cm"),
    ("Kilometer", "km"),
    ("Kilogramm", "kg"),
    ("Tore", None),
    ("Körbe", None),
    ("Sätze", None),
    ("Runden", None),
    ("Schläge", None),
    ("Holz", None),
    ("Platzierung", None),
]


def upgrade() -> None:
    op.create_table('measurement_units',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('symbol', sa.String(length=20), nullable=True),
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
    op.create_index(op.f('ix_measurement_units_tenant_id'), 'measurement_units', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_measurement_units_deleted_at'), 'measurement_units', ['deleted_at'], unique=False)
    op.create_index('ix_measurement_units_tenant_active', 'measurement_units', ['tenant_id', 'is_active'], unique=False)

    op.create_table('club_disciplines',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('short_name', sa.String(length=100), nullable=True),
    sa.Column('default_unit', sa.String(length=100), nullable=True),
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
    op.create_index(op.f('ix_club_disciplines_tenant_id'), 'club_disciplines', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_club_disciplines_deleted_at'), 'club_disciplines', ['deleted_at'], unique=False)
    op.create_index('ix_club_disciplines_tenant_active', 'club_disciplines', ['tenant_id', 'is_active'], unique=False)

    # Backfill: seed default units for all existing tenants
    conn = op.get_bind()
    for name, symbol in DEFAULT_UNITS:
        conn.execute(
            sa.text(
                "INSERT INTO measurement_units (id, name, symbol, is_active, tenant_id) "
                "SELECT gen_random_uuid(), :name, :symbol, true, id FROM tenants "
                "ON CONFLICT (tenant_id, name) DO NOTHING"
            ),
            {"name": name, "symbol": symbol},
        )


def downgrade() -> None:
    op.drop_index('ix_club_disciplines_tenant_active', table_name='club_disciplines')
    op.drop_index(op.f('ix_club_disciplines_deleted_at'), table_name='club_disciplines')
    op.drop_index(op.f('ix_club_disciplines_tenant_id'), table_name='club_disciplines')
    op.drop_table('club_disciplines')
    op.drop_index('ix_measurement_units_tenant_active', table_name='measurement_units')
    op.drop_index(op.f('ix_measurement_units_deleted_at'), table_name='measurement_units')
    op.drop_index(op.f('ix_measurement_units_tenant_id'), table_name='measurement_units')
    op.drop_table('measurement_units')
