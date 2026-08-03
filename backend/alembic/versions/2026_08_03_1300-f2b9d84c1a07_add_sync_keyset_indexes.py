"""add sync keyset indexes

Revision ID: f2b9d84c1a07
Revises: e5a1c73f8b92
Create Date: 2026-08-03 13:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f2b9d84c1a07"
down_revision: str | None = "e5a1c73f8b92"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Every table `/api/v1/sync/*` can page over.
SYNCED_TABLES = (
    "members",
    "events",
    "event_registrations",
    "dues",
    "fee_types",
    "member_fees",
    "competitions",
    "sessions",
    "entries",
)


def upgrade() -> None:
    # Delta sync pages with a keyset predicate, not an offset:
    #
    #   WHERE tenant_id = ? AND (updated_at, id) > (?, ?) AND updated_at <= ?
    #   ORDER BY updated_at, id LIMIT n
    #
    # A composite btree on (tenant_id, updated_at, id) answers all four parts in
    # one forward index range scan: equality on tenant_id, the range on
    # updated_at, the ordering, and the id tiebreak that makes the ordering
    # total. No sort node, and the scan stops at the LIMIT instead of
    # materialising the tenant's whole table.
    #
    # tenant_id has to lead. It is the isolation predicate, and putting it first
    # also gives each club its own contiguous stretch of the index, so one large
    # club's activity does not push another's pages out of cache.
    #
    # id is the third column rather than a filter applied afterwards — that is
    # what keeps the tiebreak inside the index.
    #
    # Without this, every sync page is a sequential scan plus a sort of the
    # tenant's entire table. Unnoticeable on a dev database with twenty members;
    # steadily worse on a three-thousand-member club with forty phones polling.
    #
    # Plain CREATE INDEX, not CONCURRENTLY: club-sized tables build in well under
    # a second, and `run_migrations()` runs this at boot where a brief write lock
    # costs nothing. CONCURRENTLY cannot run inside Alembic's transaction anyway —
    # it would need an autocommit block and an if_not_exists guard, because a
    # failed concurrent build leaves an INVALID index behind.
    for table in SYNCED_TABLES:
        op.create_index(
            f"ix_{table}_sync",
            table,
            ["tenant_id", "updated_at", "id"],
        )


def downgrade() -> None:
    for table in SYNCED_TABLES:
        op.drop_index(f"ix_{table}_sync", table_name=table)
