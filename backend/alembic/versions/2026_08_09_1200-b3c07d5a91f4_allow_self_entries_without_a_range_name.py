"""allow self-entries without a range name

Revision ID: b3c07d5a91f4
Revises: f27bf1f0eb7f
Create Date: 2026-08-09 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b3c07d5a91f4"
down_revision: str | None = "f27bf1f0eb7f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # A member shooting alone on their own club's range has no foreign range to
    # name, and the old shape made that day unrecordable in either form: a club
    # record needs a session nobody opened, and an external one needed a
    # location that does not exist.
    #
    # The place was never what made the entry weak. The absence of supervision
    # is, and that is carried by `assurance = 'low'` and `method = 'self'`,
    # both derived server-side. Dropping the location requirement therefore
    # widens what can be recorded without widening what it claims.
    op.drop_constraint("ck_attendance_records_origin_shape", "attendance_records")
    op.create_check_constraint(
        "ck_attendance_records_origin_shape",
        "attendance_records",
        "(origin = 'club' AND session_id IS NOT NULL AND external_location IS NULL)"
        " OR (origin = 'external' AND session_id IS NULL AND member_id IS NOT NULL)",
    )


def downgrade() -> None:
    # Rows written under the wider rule would violate the narrower one, so they
    # get a name rather than blocking the downgrade or being deleted: the club
    # is where they happened, and saying so is truthful.
    op.execute(
        "UPDATE attendance_records SET external_location = 'Eigener Stand'"
        " WHERE origin = 'external' AND external_location IS NULL"
    )
    op.drop_constraint("ck_attendance_records_origin_shape", "attendance_records")
    op.create_check_constraint(
        "ck_attendance_records_origin_shape",
        "attendance_records",
        "(origin = 'club' AND session_id IS NOT NULL AND external_location IS NULL)"
        " OR (origin = 'external' AND session_id IS NULL"
        " AND member_id IS NOT NULL AND external_location IS NOT NULL)",
    )
