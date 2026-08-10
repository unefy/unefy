"""add document templates and issued documents

Revision ID: e07c3b5d8a19
Revises: d94b1f7c2a58
Create Date: 2026-08-11 00:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e07c3b5d8a19"
down_revision: str | None = "d94b1f7c2a58"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The club's wording, with placeholders. Text rather than a layout: the
    # club owns what the document says, the page it prints on stays ours.
    op.create_table(
        "document_templates",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "include_letterhead", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column("include_footer", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("verifiable", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("tenant_id", "name", name="uq_document_templates_tenant_name"),
    )
    op.create_index(
        "ix_document_templates_tenant_active", "document_templates", ["tenant_id", "is_active"]
    )

    # What was actually handed out, frozen as it was handed out. The rendered
    # text is stored rather than a reference to the template, because a
    # template changes and a re-print must not.
    op.create_table(
        "issued_documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "member_id",
            sa.Uuid(),
            sa.ForeignKey("members.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "template_id",
            sa.Uuid(),
            sa.ForeignKey("document_templates.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("template_name", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("issued_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("revoke_reason", sa.Text(), nullable=True),
        # Globally unique: the check page is unauthenticated and has no tenant
        # to scope by. Null when the template is not verifiable.
        sa.Column("verification_code", sa.String(length=32), nullable=True, unique=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_issued_documents_tenant_member", "issued_documents", ["tenant_id", "member_id"]
    )
    op.create_index(
        "ix_issued_documents_tenant_issued", "issued_documents", ["tenant_id", "issued_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_issued_documents_tenant_issued", table_name="issued_documents")
    op.drop_index("ix_issued_documents_tenant_member", table_name="issued_documents")
    op.drop_table("issued_documents")
    op.drop_index("ix_document_templates_tenant_active", table_name="document_templates")
    op.drop_table("document_templates")
