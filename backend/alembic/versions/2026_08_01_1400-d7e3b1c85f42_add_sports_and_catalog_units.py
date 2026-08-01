"""add sports and catalog units, link disciplines to a sport

Revision ID: d7e3b1c85f42
Revises: c4f1a9d20e77
Create Date: 2026-08-01 14:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd7e3b1c85f42'
down_revision: str | None = 'c4f1a9d20e77'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Initial content only — from here on these tables are maintained through the
# platform admin UI, not by editing this file.
SPORTS: list[tuple[str, str, str | None, str, int, list[str]]] = [
    (
        "shooting",
        "Schießsport",
        "Sportschießen mit Gewehr, Pistole, Flinte und Bogen.",
        "Target",
        10,
        ["shooting"],
    ),
    (
        "other",
        "Sonstige",
        "Für Vereine, deren Sportart noch nicht hinterlegt ist.",
        "CircleDashed",
        900,
        [],
    ),
]

# Units offered per sport. Deliberately narrower than the old flat list, which
# handed every club Ringe *and* Tore *and* Körbe regardless of what they do.
UNITS: dict[str, list[tuple[str, str | None]]] = {
    "shooting": [
        ("Ringe", None),
        ("Punkte", "Pkt."),
        ("Treffer", None),
        ("Sekunden", "s"),
        ("Platzierung", None),
    ],
    "other": [
        ("Punkte", "Pkt."),
        ("Sekunden", "s"),
        ("Minuten", "min"),
        ("Meter", "m"),
        ("Platzierung", None),
    ],
}


def upgrade() -> None:
    op.create_table(
        "sports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("icon", sa.String(length=50), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "modules",
            sa.ARRAY(sa.String(length=50)),
            nullable=False,
            server_default="{}",
        ),
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
        sa.UniqueConstraint("key"),
    )

    op.create_table(
        "catalog_units",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("sport_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("symbol", sa.String(length=20), nullable=True),
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
        sa.ForeignKeyConstraint(["sport_id"], ["sports.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_catalog_units_sport_id", "catalog_units", ["sport_id"])
    op.create_index(
        "ix_catalog_units_sport_active", "catalog_units", ["sport_id", "is_active"]
    )

    op.add_column("disciplines", sa.Column("sport_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_disciplines_sport_id",
        "disciplines",
        "sports",
        ["sport_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_disciplines_sport_id", "disciplines", ["sport_id"])

    connection = op.get_bind()

    for key, name, description, icon, sort_order, modules in SPORTS:
        connection.execute(
            sa.text(
                "INSERT INTO sports (id, key, name, description, icon, sort_order,"
                " is_active, modules) VALUES (gen_random_uuid(), :key, :name,"
                " :description, :icon, :sort_order, true, :modules)"
                " ON CONFLICT (key) DO NOTHING"
            ),
            {
                "key": key,
                "name": name,
                "description": description,
                "icon": icon,
                "sort_order": sort_order,
                "modules": modules,
            },
        )

    for sport_key, units in UNITS.items():
        for index, (unit_name, symbol) in enumerate(units):
            connection.execute(
                sa.text(
                    "INSERT INTO catalog_units (id, sport_id, name, symbol, sort_order,"
                    " is_active) SELECT gen_random_uuid(), s.id, :name, :symbol,"
                    " :sort_order, true FROM sports s WHERE s.key = :sport_key"
                ),
                {
                    "name": unit_name,
                    "symbol": symbol,
                    "sort_order": index * 10,
                    "sport_key": sport_key,
                },
            )

    # Every seeded discipline is a shooting discipline — the catalog contained
    # nothing else at the time this migration was written.
    connection.execute(
        sa.text(
            "UPDATE disciplines SET sport_id = (SELECT id FROM sports WHERE key ="
            " 'shooting') WHERE sport_id IS NULL"
        )
    )


def downgrade() -> None:
    op.drop_index("ix_disciplines_sport_id", table_name="disciplines")
    op.drop_constraint("fk_disciplines_sport_id", "disciplines", type_="foreignkey")
    op.drop_column("disciplines", "sport_id")
    op.drop_index("ix_catalog_units_sport_active", table_name="catalog_units")
    op.drop_index("ix_catalog_units_sport_id", table_name="catalog_units")
    op.drop_table("catalog_units")
    op.drop_table("sports")
