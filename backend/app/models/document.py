import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, TenantModel

#: How a document ends. No fourth value: a stored signature graphic would be a
#: reusable forgery tool sitting on our side, and every PDF it was drawn into
#: would carry it straight back out. The check code replaces it — verifiable
#: beats looking-signed.
SIGNATURE_MODES = ("none", "machine", "line")


class DocumentTemplate(TenantModel, AuditMixin):
    """The club's own wording for a certificate, with placeholders in it.

    Text, not a layout. The club owns what the document says; the page it is
    printed on stays ours. That split is what keeps the result predictable in
    print and translatable, and it means changing a sentence does not wait for
    a release.

    Only the free forms live here. A donation receipt or the §14 proof follows
    a prescribed form and stays built in code — a template there would be an
    invitation to produce an invalid document.
    """

    __tablename__ = "document_templates"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name"),
        Index("ix_document_templates_tenant_active", "tenant_id", "is_active"),
        CheckConstraint(
            f"signature_mode IN ({', '.join(repr(m) for m in SIGNATURE_MODES)})",
            name="ck_document_templates_signature_mode",
        ),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    #: What the club is going to hand somebody — printed as the heading.
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    #: Flowing text with `{{platzhalter}}`. Blank lines separate paragraphs;
    #: nothing else in here is markup.
    body: Mapped[str] = mapped_column(Text, nullable=False)

    #: The club's letterhead and register data, from the settings rather than
    #: from this text. Off per template, because not every document wants them.
    include_letterhead: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )
    include_footer: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )
    #: Whether an issued document carries a QR and a check code. On by default:
    #: a certificate an employer can verify is worth more than a PDF anybody
    #: can rebuild in Word.
    verifiable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )
    #: How the document ends: `none`, `machine` — the sentence that says it was
    #: machine-made and is valid without a signature — or `line`, a ruled line
    #: to sign by hand.
    #:
    #: Deliberately **no stored signature graphic**. A club's signature kept on
    #: our side would be a reusable forgery tool, and every PDF it went into
    #: would carry it back out again. What replaces the signature here is the
    #: check code: verifiable beats looking-signed.
    signature_mode: Mapped[str] = mapped_column(
        String(16), nullable=False, default="line", server_default="line"
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )


class IssuedDocument(TenantModel, AuditMixin):
    """A document that was actually handed out, frozen as it was handed out.

    The rendered text is stored, not a reference to the template: a template
    changes, and then a re-print or a verification would show something the
    recipient never received. What was issued is what this row says.

    Nothing here is edited. A mistake is revoked and re-issued, so the trail
    keeps both — the wrong one and its replacement.
    """

    __tablename__ = "issued_documents"
    __table_args__ = (
        Index("ix_issued_documents_tenant_member", "tenant_id", "member_id"),
        Index("ix_issued_documents_tenant_issued", "tenant_id", "issued_at"),
        CheckConstraint(
            f"signature_mode IN ({', '.join(repr(m) for m in SIGNATURE_MODES)})",
            name="ck_issued_documents_signature_mode",
        ),
    )

    member_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("members.id", ondelete="CASCADE"), nullable=False
    )

    #: Which template it came from, for the club's own overview. Nullable and
    #: SET NULL: deleting a template must not take the documents it produced.
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("document_templates.id", ondelete="SET NULL"), nullable=True
    )
    #: The template's name at the time, so the history stays readable after the
    #: template is renamed or removed.
    template_name: Mapped[str] = mapped_column(String(255), nullable=False)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    #: The rendered text — placeholders already replaced.
    body: Mapped[str] = mapped_column(Text, nullable=False)

    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    issued_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)

    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    revoke_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    #: Short and unguessable, never the UUID: this is what the QR carries and
    #: what the public check page accepts. Globally unique, because that page
    #: is unauthenticated and has no tenant to scope by. Null when the template
    #: is not verifiable — then there is no QR and nothing to look up.
    verification_code: Mapped[str | None] = mapped_column(String(32), nullable=True, unique=True)

    #: SHA-256 over member, issue time and the rendered text.
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    # How this document looked, copied from the template when it was issued.
    # Frozen here for the same reason the text is: the template goes on
    # changing, and a deleted one leaves `template_id` null while this document
    # still has to print exactly as it was handed over.
    include_letterhead: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )
    include_footer: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )
    signature_mode: Mapped[str] = mapped_column(
        String(16), nullable=False, default="line", server_default="line"
    )
