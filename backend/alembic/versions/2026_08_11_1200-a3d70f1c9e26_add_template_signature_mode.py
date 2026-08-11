"""how a document template ends: nothing, a machine-made note, or a signature line

Revision ID: a3d70f1c9e26
Revises: f1a83c9e0b47
Create Date: 2026-08-11 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3d70f1c9e26"
down_revision: str | None = "f1a83c9e0b47"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # `line` for everything that exists, because that is what the renderer did
    # for every document until now — a template that silently stopped offering
    # a place to sign would be a change the club never asked for.
    op.add_column(
        "document_templates",
        sa.Column(
            "signature_mode",
            sa.String(length=16),
            nullable=False,
            server_default="line",
        ),
    )
    op.create_check_constraint(
        "ck_document_templates_signature_mode",
        "document_templates",
        "signature_mode IN ('none', 'machine', 'line')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_document_templates_signature_mode", "document_templates", type_="check"
    )
    op.drop_column("document_templates", "signature_mode")
