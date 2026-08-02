"""add attendance guests

Revision ID: e5a1c73f8b92
Revises: d3f8b21c9e47
Create Date: 2026-08-02 20:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5a1c73f8b92"
down_revision: str | None = "d3f8b21c9e47"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # A club has to know who was on the range, and not everyone there is a
    # member. Guests carry a name instead of a member id; they never count
    # towards a §14 proof, which joins members and therefore skips them.
    op.add_column("attendance_records", sa.Column("guest_name", sa.String(length=255), nullable=True))
    op.alter_column("attendance_records", "member_id", existing_type=sa.Uuid(), nullable=True)

    # Enforced by the database rather than by whichever service writes the row:
    # neither set is not attendance, both set is a contradiction.
    op.create_check_constraint(
        "ck_attendance_records_member_xor_guest",
        "attendance_records",
        "(member_id IS NOT NULL) <> (guest_name IS NOT NULL)",
    )


def downgrade() -> None:
    # Guest rows have no member to fall back on, so they cannot survive the
    # column becoming NOT NULL again.
    op.execute("DELETE FROM attendance_records WHERE member_id IS NULL")
    op.drop_constraint("ck_attendance_records_member_xor_guest", "attendance_records")
    op.alter_column("attendance_records", "member_id", existing_type=sa.Uuid(), nullable=False)
    op.drop_column("attendance_records", "guest_name")
