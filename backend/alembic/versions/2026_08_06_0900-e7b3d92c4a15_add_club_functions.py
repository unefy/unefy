"""add club functions catalog, tenant functions and member function terms

Revision ID: e7b3d92c4a15
Revises: c4a71e8b5d92
Create Date: 2026-08-06 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.function_seeds import CATALOG_FUNCTIONS

# revision identifiers, used by Alembic.
revision: str = "e7b3d92c4a15"
down_revision: str | None = "c4a71e8b5d92"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Global catalog of club offices. Initial population happens here rather
    # than at boot (same reasoning as the discipline catalog): re-seeding on
    # every start would resurrect rows an admin removed on purpose.
    op.create_table(
        "catalog_functions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("sport_id", sa.Uuid(), nullable=True),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("level", sa.String(length=20), nullable=False, server_default="club"),
        sa.Column("suggested_role", sa.String(length=20), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
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
        sa.ForeignKeyConstraint(["sport_id"], ["sports.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.create_index("ix_catalog_functions_sport_id", "catalog_functions", ["sport_id"])
    op.create_index(
        "ix_catalog_functions_sport_active", "catalog_functions", ["sport_id", "is_active"]
    )

    # The club's own list — seeded from the catalog at onboarding, owned by the
    # club from then on (copy by value, no FK back).
    op.create_table(
        "functions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("level", sa.String(length=20), nullable=False, server_default="club"),
        sa.Column("suggested_role", sa.String(length=20), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
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
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "name"),
    )
    op.create_index("ix_functions_tenant_id", "functions", ["tenant_id"])
    op.create_index("ix_functions_tenant_active", "functions", ["tenant_id", "is_active"])

    # One row per term of office. valid_to IS NULL = currently in office.
    op.create_table(
        "member_functions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("member_id", sa.Uuid(), nullable=False),
        sa.Column("function_id", sa.Uuid(), nullable=False),
        sa.Column("division_id", sa.Uuid(), nullable=True),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("note", sa.String(length=500), nullable=True),
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
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["function_id"], ["functions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["division_id"], ["divisions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_member_functions_tenant_id", "member_functions", ["tenant_id"])
    op.create_index("ix_member_functions_division_id", "member_functions", ["division_id"])
    op.create_index(
        "ix_member_functions_tenant_member", "member_functions", ["tenant_id", "member_id"]
    )
    op.create_index(
        "ix_member_functions_tenant_function_division",
        "member_functions",
        ["tenant_id", "function_id", "division_id"],
    )

    connection = op.get_bind()
    for seed in CATALOG_FUNCTIONS:
        sport_id = None
        if seed["sport_key"] is not None:
            sport_id = connection.execute(
                sa.text("SELECT id FROM sports WHERE key = :key"),
                {"key": seed["sport_key"]},
            ).scalar()
            # A sport missing from this installation simply drops its offices.
            if sport_id is None:
                continue
        connection.execute(
            sa.text(
                "INSERT INTO catalog_functions (id, sport_id, key, name, level,"
                " suggested_role, sort_order, is_active)"
                " VALUES (gen_random_uuid(), :sport_id, :key, :name, :level,"
                " :suggested_role, :sort_order, true)"
                " ON CONFLICT (key) DO NOTHING"
            ),
            {
                "sport_id": sport_id,
                "key": seed["key"],
                "name": seed["name"],
                "level": seed["level"],
                "suggested_role": seed["suggested_role"],
                "sort_order": seed["sort_order"],
            },
        )


def downgrade() -> None:
    op.drop_index("ix_member_functions_tenant_function_division", table_name="member_functions")
    op.drop_index("ix_member_functions_tenant_member", table_name="member_functions")
    op.drop_index("ix_member_functions_division_id", table_name="member_functions")
    op.drop_index("ix_member_functions_tenant_id", table_name="member_functions")
    op.drop_table("member_functions")
    op.drop_index("ix_functions_tenant_active", table_name="functions")
    op.drop_index("ix_functions_tenant_id", table_name="functions")
    op.drop_table("functions")
    op.drop_index("ix_catalog_functions_sport_active", table_name="catalog_functions")
    op.drop_index("ix_catalog_functions_sport_id", table_name="catalog_functions")
    op.drop_table("catalog_functions")
