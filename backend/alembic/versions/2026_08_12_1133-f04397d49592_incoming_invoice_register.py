"""incoming invoice register

Revision ID: f04397d49592
Revises: d2b71c4f9a30
Create Date: 2026-08-12 11:33:07.922143

Autogenerate also proposed dropping and recreating the tenant foreign keys of
five unrelated tables, and making four `library_*` timestamp columns NOT NULL.
Both are drift between other models and this dev database, and the foreign-key
pairs would have quietly dropped `ON DELETE CASCADE` from tables that have it —
deleting a club would then fail on the first orphan. Removed by hand; this
revision creates one table and nothing else.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f04397d49592"
down_revision: Union[str, None] = "d2b71c4f9a30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "incoming_invoices",
        # What the invoice says. All nullable: a scan carries no data, and the
        # file is kept while somebody types the figures in.
        sa.Column("supplier_name", sa.String(length=255), nullable=True),
        sa.Column("supplier_vat_id", sa.String(length=30), nullable=True),
        sa.Column("invoice_number", sa.String(length=100), nullable=True),
        sa.Column("invoice_date", sa.Date(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("gross_amount", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("net_amount", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("tax_amount", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="EUR"),
        sa.Column("note", sa.Text(), nullable=True),
        # Where it stands.
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column("paid_on", sa.Date(), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False, server_default="manual"),
        # The file it arrived as.
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "source IN ('manual', 'zugferd', 'xrechnung')",
            name="ck_incoming_invoices_source",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'paid', 'cancelled')", name="ck_incoming_invoices_status"
        ),
        sa.CheckConstraint(
            "gross_amount IS NULL OR gross_amount >= 0",
            name="ck_incoming_invoices_gross_not_negative",
        ),
        # CASCADE like every other tenant table: deleting a club has to be
        # possible, and an invoice belonging to no club is not a record.
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "storage_key"),
    )
    op.create_index(
        op.f("ix_incoming_invoices_deleted_at"), "incoming_invoices", ["deleted_at"]
    )
    op.create_index(op.f("ix_incoming_invoices_tenant_id"), "incoming_invoices", ["tenant_id"])
    op.create_index(
        "ix_incoming_invoices_tenant_date", "incoming_invoices", ["tenant_id", "invoice_date"]
    )
    op.create_index(
        "ix_incoming_invoices_tenant_status", "incoming_invoices", ["tenant_id", "status"]
    )
    # The check the register exists for: the same invoice entered twice, paid
    # twice. Partial, so it only applies once both parts are known — a scan
    # waiting to be typed up has neither, and several of those must coexist.
    op.create_index(
        "uq_incoming_invoices_supplier_number",
        "incoming_invoices",
        ["tenant_id", "supplier_name", "invoice_number"],
        unique=True,
        postgresql_where=sa.text(
            "deleted_at IS NULL AND supplier_name IS NOT NULL AND invoice_number IS NOT NULL"
        ),
    )


def downgrade() -> None:
    op.drop_index("uq_incoming_invoices_supplier_number", table_name="incoming_invoices")
    op.drop_index("ix_incoming_invoices_tenant_status", table_name="incoming_invoices")
    op.drop_index("ix_incoming_invoices_tenant_date", table_name="incoming_invoices")
    op.drop_index(op.f("ix_incoming_invoices_tenant_id"), table_name="incoming_invoices")
    op.drop_index(op.f("ix_incoming_invoices_deleted_at"), table_name="incoming_invoices")
    op.drop_table("incoming_invoices")
