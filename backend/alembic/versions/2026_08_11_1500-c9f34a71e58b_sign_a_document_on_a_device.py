"""a signature drawn on a device, belonging to one issued document

Revision ID: c9f34a71e58b
Revises: b58e2a04c7d1
Create Date: 2026-08-11 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9f34a71e58b"
down_revision: str | None = "b58e2a04c7d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # On the document, not on the club: this is the signature that was drawn
    # for *this* piece of paper. There is no club-wide signature graphic, and
    # this column is not one — nothing reads it to sign anything else.
    op.add_column("issued_documents", sa.Column("signature_png", sa.LargeBinary(), nullable=True))
    op.add_column(
        "issued_documents",
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Both or neither. A timestamp without an image would print a document
    # claiming to be signed with nothing on the line.
    op.create_check_constraint(
        "ck_issued_documents_signature_complete",
        "issued_documents",
        "(signature_png IS NULL) = (signed_at IS NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_issued_documents_signature_complete", "issued_documents", type_="check"
    )
    op.drop_column("issued_documents", "signed_at")
    op.drop_column("issued_documents", "signature_png")
