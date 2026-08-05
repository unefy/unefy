"""add external self-entries to attendance records

Revision ID: 7c2a91d4b8e3
Revises: 34bbb220afd3
Create Date: 2026-08-05 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7c2a91d4b8e3"
down_revision: str | None = "34bbb220afd3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # A member's own entry about a visit to some other range: no session, no
    # witness — origin "external", method "self", assurance "low". The proof
    # ledger stays one table, so the §14 day count, the shooting details and
    # the retention sweep cover both kinds without a second code path.
    #
    # The server default doubles as the backfill for every existing row, all of
    # which are club records, and then stays: "club" is what a record is unless
    # a code path deliberately says otherwise.
    op.add_column(
        "attendance_records",
        sa.Column("origin", sa.String(length=20), nullable=False, server_default="club"),
    )
    op.add_column(
        "attendance_records",
        sa.Column("external_location", sa.String(length=255), nullable=True),
    )
    op.alter_column(
        "attendance_records",
        "session_id",
        existing_type=sa.Uuid(),
        nullable=True,
    )

    # A club record hangs off a session; an external one names the range and
    # always belongs to a member. Enforced here rather than in whichever
    # service happens to write the row.
    op.create_check_constraint(
        "ck_attendance_records_origin_shape",
        "attendance_records",
        "(origin = 'club' AND session_id IS NOT NULL AND external_location IS NULL)"
        " OR (origin = 'external' AND session_id IS NULL"
        " AND member_id IS NOT NULL AND external_location IS NOT NULL)",
    )

    # One external entry per member and day: two ranges on one day are still
    # one §14 day, and a second row would only pad the list.
    op.create_index(
        "uq_attendance_records_external_member_day",
        "attendance_records",
        ["tenant_id", "member_id", "occurred_on"],
        unique=True,
        postgresql_where=sa.text("origin = 'external' AND deleted_at IS NULL"),
    )


    # The certificate freezes how many certified days were external claims,
    # hashed like the other qualifications. Same pattern as the self-entry
    # counts: a server default only so the column arrives NOT NULL, dropped
    # again so a future insert that forgets it fails loudly.
    op.add_column(
        "shooting_proof_certificates",
        sa.Column("external_days", sa.Integer(), nullable=False, server_default="0"),
    )
    op.alter_column("shooting_proof_certificates", "external_days", server_default=None)


def downgrade() -> None:
    op.drop_column("shooting_proof_certificates", "external_days")
    op.drop_index("uq_attendance_records_external_member_day", table_name="attendance_records")
    op.drop_constraint("ck_attendance_records_origin_shape", "attendance_records")
    # Refuses while external rows exist — which is correct: they have no
    # session to fall back to, and inventing one would forge evidence.
    op.alter_column(
        "attendance_records",
        "session_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )
    op.drop_column("attendance_records", "external_location")
    op.drop_column("attendance_records", "origin")
