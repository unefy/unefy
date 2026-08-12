"""the round mail: a message and one row per address

Revision ID: a71c3f5e8d24
Revises: f04397d49592
Create Date: 2026-08-12 22:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a71c3f5e8d24"
down_revision: str | None = "f04397d49592"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "email_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("audience", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="queued"),
        sa.Column("sent_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recipient_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("kind IN ('notice', 'newsletter')", name="ck_email_messages_kind"),
        sa.CheckConstraint(
            "status IN ('queued', 'sending', 'sent', 'failed')",
            name="ck_email_messages_status",
        ),
    )
    op.create_index("ix_email_messages_tenant_id", "email_messages", ["tenant_id"])
    # The sending loop reaches across clubs — it is one loop for the whole
    # installation — so this index deliberately does not start with tenant_id.
    op.create_index("ix_email_messages_status", "email_messages", ["status", "queued_at"])
    op.create_index(
        "ix_email_messages_tenant_queued", "email_messages", ["tenant_id", "queued_at"]
    )

    op.create_table(
        "email_recipients",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column("member_id", sa.Uuid(), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("reason", sa.String(length=30), nullable=True),
        sa.Column("error", sa.String(length=500), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["message_id"], ["email_messages.id"], ondelete="CASCADE"),
        # SET NULL: deleting a member must not rewrite what the club sent.
        sa.ForeignKeyConstraint(["member_id"], ["members.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('pending', 'sent', 'failed', 'skipped')",
            name="ck_email_recipients_status",
        ),
    )
    op.create_index("ix_email_recipients_tenant_id", "email_recipients", ["tenant_id"])
    op.create_index(
        "ix_email_recipients_message_status", "email_recipients", ["message_id", "status"]
    )
    # No address is delivered to twice. Partial, so the shared mailbox of a
    # couple still leaves both members in the record — the second as `skipped`
    # with reason `duplicate`.
    op.create_index(
        "uq_email_recipients_delivered_email",
        "email_recipients",
        ["message_id", "email"],
        unique=True,
        postgresql_where=sa.text("status <> 'skipped'"),
    )


def downgrade() -> None:
    op.drop_table("email_recipients")
    op.drop_table("email_messages")
