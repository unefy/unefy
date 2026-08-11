"""freeze the presentation flags on the issued document, not just the template

Revision ID: b58e2a04c7d1
Revises: a3d70f1c9e26
Create Date: 2026-08-11 12:15:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import true

# revision identifiers, used by Alembic.
revision: str = "b58e2a04c7d1"
down_revision: str | None = "a3d70f1c9e26"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The template says how future documents should look; this row says how
    # *this* one looked. Reading the flags back off the template at print time
    # was wrong twice over: a template changes, and a deleted one leaves
    # `template_id` null while the document has to stay printable.
    #
    # The defaults are the truth about the rows that already exist — every
    # document issued so far was rendered with letterhead, footer and a
    # signature line, whatever its template said.
    op.add_column(
        "issued_documents",
        sa.Column("include_letterhead", sa.Boolean(), nullable=False, server_default=true()),
    )
    op.add_column(
        "issued_documents",
        sa.Column("include_footer", sa.Boolean(), nullable=False, server_default=true()),
    )
    op.add_column(
        "issued_documents",
        sa.Column("signature_mode", sa.String(length=16), nullable=False, server_default="line"),
    )
    op.create_check_constraint(
        "ck_issued_documents_signature_mode",
        "issued_documents",
        "signature_mode IN ('none', 'machine', 'line')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_issued_documents_signature_mode", "issued_documents", type_="check")
    op.drop_column("issued_documents", "signature_mode")
    op.drop_column("issued_documents", "include_footer")
    op.drop_column("issued_documents", "include_letterhead")
