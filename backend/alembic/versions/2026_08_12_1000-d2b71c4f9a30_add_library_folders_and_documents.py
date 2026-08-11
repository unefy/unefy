"""the club's filing cabinet: folders and uploaded documents

Revision ID: d2b71c4f9a30
Revises: c9f34a71e58b
Create Date: 2026-08-12 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d2b71c4f9a30"
down_revision: str | None = "c9f34a71e58b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "library_folders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        # RESTRICT, not CASCADE: emptying a folder is a decision somebody
        # makes, not a side effect of deleting the drawer above it.
        sa.ForeignKeyConstraint(["parent_id"], ["library_folders.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_library_folders_tenant_id", "library_folders", ["tenant_id"])
    op.create_index(
        "ix_library_folders_tenant_parent", "library_folders", ["tenant_id", "parent_id"]
    )
    # NULLS NOT DISTINCT is the whole point of writing this by hand: without it
    # the uniqueness rule would hold everywhere except the root, where
    # `parent_id` is NULL and every NULL counts as different from every other.
    op.execute(
        "ALTER TABLE library_folders ADD CONSTRAINT uq_library_folders_parent_name "
        "UNIQUE NULLS NOT DISTINCT (tenant_id, parent_id, name)"
    )

    op.create_table(
        "library_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("folder_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("visibility", sa.String(length=20), nullable=False, server_default="board"),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("replaces_id", sa.Uuid(), nullable=True),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["folder_id"], ["library_folders.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["replaces_id"], ["library_documents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "visibility IN ('board', 'members')", name="ck_library_documents_visibility"
        ),
        sa.CheckConstraint("byte_size >= 0", name="ck_library_documents_byte_size"),
    )
    op.create_index("ix_library_documents_tenant_id", "library_documents", ["tenant_id"])
    op.create_index("ix_library_documents_deleted_at", "library_documents", ["deleted_at"])
    op.create_index(
        "ix_library_documents_tenant_folder", "library_documents", ["tenant_id", "folder_id"]
    )
    op.create_index(
        "ix_library_documents_tenant_current", "library_documents", ["tenant_id", "superseded_at"]
    )


def downgrade() -> None:
    op.drop_table("library_documents")
    op.drop_table("library_folders")
