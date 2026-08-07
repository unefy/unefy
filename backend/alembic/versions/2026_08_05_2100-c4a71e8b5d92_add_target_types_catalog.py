"""add target types catalog and free training container index

Revision ID: c4a71e8b5d92
Revises: 7c2a91d4b8e3
Create Date: 2026-08-05 21:00:00.000000

"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.core.target_type_seeds import TARGET_TYPES

# revision identifiers, used by Alembic.
revision: str = "c4a71e8b5d92"
down_revision: str | None = "7c2a91d4b8e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Ring geometry of the standard targets. Global, not tenant-scoped: the
    # dimensions come from the federations, and a club that could edit them
    # could quietly change what a 10 is worth.
    target_types = op.create_table(
        "target_types",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        # Exactly 10 outer diameters in mm, index 0 = ring 10.
        sa.Column("ring_diameters_mm", postgresql.JSONB(), nullable=False),
        sa.Column("inner_ten_diameter_mm", sa.Numeric(precision=6, scale=2), nullable=False),
        # A length, not a ring number: the ISSF 50 m rifle black (112.4 mm) falls
        # between two rings, and photo recognition needs the exact value as its
        # scale anchor.
        sa.Column("black_diameter_mm", sa.Numeric(precision=6, scale=2), nullable=False),
        # Default only — overridable per series and per shot, because one sheet
        # is shot with .22 and 9 mm, sometimes both at once.
        sa.Column("caliber_diameter_mm", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("caliber_name", sa.String(length=50), nullable=True),
        sa.Column("distance_m", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_target_types_slug"),
    )

    # Initial population happens here rather than at boot, matching how the
    # discipline catalog is handled (see app/main.py): re-seeding on every start
    # would resurrect rows an admin removed on purpose.
    op.bulk_insert(
        target_types,
        [{"id": uuid.uuid4(), **entry} for entry in TARGET_TYPES],
    )

    # At most one live "Freies Training" container per club. Without this, two
    # devices recording their first-ever free series at the same moment would
    # each create one, and the club would carry two parallel training histories
    # forever. With it, the loser hits an IntegrityError and re-reads the winner.
    op.create_index(
        "ux_competitions_free_training",
        "competitions",
        ["tenant_id"],
        unique=True,
        postgresql_where=sa.text(
            "competition_type = 'free_training' AND deleted_at IS NULL"
        ),
    )


def downgrade() -> None:
    op.drop_index("ux_competitions_free_training", table_name="competitions")
    op.drop_table("target_types")
