"""add proof chain

Revision ID: c9d4e82b5f61
Revises: b6e2f47a9c15
Create Date: 2026-08-04 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9d4e82b5f61"
down_revision: str | None = "b6e2f47a9c15"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Append-only hash chain over proof events (assurance level 1). Links
    # carry hashes and ids only — no personal data, so retention never has to
    # touch them.
    op.create_table(
        "proof_chain_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("seq", sa.BigInteger(), nullable=False),
        sa.Column("entry_type", sa.String(length=30), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("prev_hash", sa.String(length=64), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
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
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
    )
    op.create_index("ix_proof_chain_entries_tenant_id", "proof_chain_entries", ["tenant_id"])
    # This uniqueness is what serializes concurrent appends.
    op.create_index(
        "uq_proof_chain_tenant_seq", "proof_chain_entries", ["tenant_id", "seq"], unique=True
    )

    op.create_table(
        "proof_chain_anchors",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("seq_to", sa.BigInteger(), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("tsa_token", sa.LargeBinary(), nullable=False),
        sa.Column("tsa_url", sa.String(length=255), nullable=False),
        sa.Column("anchored_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
    )
    op.create_index("ix_proof_chain_anchors_tenant_id", "proof_chain_anchors", ["tenant_id"])
    op.create_index("ix_proof_chain_anchors_tenant_seq", "proof_chain_anchors", ["tenant_id", "seq_to"])


def downgrade() -> None:
    op.drop_table("proof_chain_anchors")
    op.drop_table("proof_chain_entries")
