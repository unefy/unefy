"""Templates the club writes, and the documents they produce.

Two rules carry this module.

The first: a placeholder that is not in the catalogue is refused **on save**,
not silently blanked at print time. A club editing a letter finds out about a
typo while it is still a draft; discovering it on a signed certificate is too
late, and printing a gap where a name should be is worse than refusing.

The second: issuing **freezes the rendered text**. A template changes — that is
what it is for — and a re-print or a verification months later must show what
the recipient actually received, not what the template says today.
"""

import hashlib
import secrets
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.document import MAX_SIGNATURE_BYTES, DocumentTemplate, IssuedDocument
from app.models.due import FeeType, MemberFee
from app.models.function import Function, MemberFunction
from app.models.member import Member
from app.models.tenant import Tenant
from app.schemas.document import TemplateCreate, TemplateUpdate
from app.services import document_variables as variables

logger = structlog.get_logger()

#: Unambiguous in print and on the phone: no O/0, no I/1/l. Same alphabet as
#: the §14 certificate, because a member may hold both and should not have to
#: learn two ways of reading a code.
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_CODE_LENGTH = 11


class DocumentService:
    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    # --- Templates ---

    async def list_templates(self, *, include_inactive: bool = False) -> list[DocumentTemplate]:
        query = (
            select(DocumentTemplate)
            .where(DocumentTemplate.tenant_id == self.tenant_id)
            .order_by(DocumentTemplate.name)
        )
        if not include_inactive:
            query = query.where(DocumentTemplate.is_active.is_(True))
        return list((await self.session.execute(query)).scalars().all())

    async def get_template(self, template_id: uuid.UUID) -> DocumentTemplate:
        template = (
            await self.session.execute(
                select(DocumentTemplate)
                .where(DocumentTemplate.tenant_id == self.tenant_id)
                .where(DocumentTemplate.id == template_id)
            )
        ).scalar_one_or_none()
        if template is None:
            raise NotFoundError("Template not found")
        return template

    async def create_template(
        self, data: TemplateCreate, *, created_by: uuid.UUID
    ) -> DocumentTemplate:
        self._require_known_placeholders(data.body)
        template = DocumentTemplate(
            tenant_id=self.tenant_id,
            created_by=created_by,
            updated_by=created_by,
            **data.model_dump(),
        )
        self.session.add(template)
        try:
            await self.session.flush()
        except IntegrityError as error:
            raise ConflictError("A template with this name already exists") from error
        return template

    async def update_template(
        self, template_id: uuid.UUID, data: TemplateUpdate, *, updated_by: uuid.UUID
    ) -> DocumentTemplate:
        template = await self.get_template(template_id)
        fields = data.model_dump(exclude_unset=True)

        if "body" in fields:
            self._require_known_placeholders(fields["body"])

        for field, value in fields.items():
            setattr(template, field, value)
        template.updated_by = updated_by

        try:
            await self.session.flush()
        except IntegrityError as error:
            raise ConflictError("A template with this name already exists") from error
        # The flush expires `updated_at`, which the ORM set through `onupdate`.
        # Without this the caller serialising the template would have to load
        # it from inside Pydantic, where there is no greenlet to await on.
        await self.session.refresh(template)
        return template

    async def delete_template(self, template_id: uuid.UUID) -> None:
        """Remove a template. Documents it produced stay.

        The foreign key is `SET NULL` and the issued row carries its own copy
        of the name and the text, so deleting the template loses the ability to
        issue more of them and nothing else.
        """
        template = await self.get_template(template_id)
        await self.session.delete(template)
        await self.session.flush()

    def _require_known_placeholders(self, body: str) -> None:
        unknown = variables.unknown_placeholders(body)
        if unknown:
            raise ValidationError(
                "The template uses placeholders that do not exist",
                details=[{"field": "body", "message": name} for name in unknown],
            )

    # --- Issuing ---

    async def issue(
        self, member_id: uuid.UUID, template_id: uuid.UUID, *, issued_by: uuid.UUID
    ) -> IssuedDocument:
        """Render the template for this member and freeze the result.

        Issued by a person, never on a schedule: a document that goes out with
        a club's name on it is somebody's decision.
        """
        template = await self.get_template(template_id)
        if not template.is_active:
            raise ConflictError("This template is not in use", code="TEMPLATE_INACTIVE")

        member = (
            await self.session.execute(
                select(Member)
                .where(Member.tenant_id == self.tenant_id)
                .where(Member.id == member_id)
                .where(Member.deleted_at.is_(None))
            )
        ).scalar_one_or_none()
        if member is None:
            raise NotFoundError("Member not found")

        tenant = (
            await self.session.execute(select(Tenant).where(Tenant.id == self.tenant_id))
        ).scalar_one()

        issued_at = datetime.now(UTC)
        today = issued_at.astimezone(ZoneInfo(tenant.timezone)).date()
        body = variables.render(
            template.body,
            variables.build_values(
                member,
                tenant,
                fee=await self._current_fee(member_id, today),
                offices=await self._current_offices(member_id, today),
            ),
        )

        document = IssuedDocument(
            tenant_id=self.tenant_id,
            member_id=member_id,
            template_id=template.id,
            template_name=template.name,
            title=template.title,
            body=body,
            issued_at=issued_at,
            issued_by_user_id=issued_by,
            # No code when the template is not verifiable: a code that leads to
            # a page saying nothing useful is worse than no code at all.
            verification_code=self._verification_code() if template.verifiable else None,
            content_hash=hashlib.sha256(
                variables.content_hash_input(member_id, body, issued_at).encode()
            ).hexdigest(),
            # Copied, not looked up later: the template keeps changing and may
            # be deleted, this document has to keep printing as it was handed
            # over.
            include_letterhead=template.include_letterhead,
            include_footer=template.include_footer,
            signature_mode=template.signature_mode,
            created_by=issued_by,
            updated_by=issued_by,
        )
        self.session.add(document)
        await self.session.flush()

        logger.info(
            "document_issued",
            tenant_id=str(self.tenant_id),
            member_id=str(member_id),
            template=template.name,
        )
        return document

    async def revoke(
        self, document_id: uuid.UUID, *, reason: str, revoked_by: uuid.UUID
    ) -> IssuedDocument:
        """Withdraw a document. The row stays, and so does its text.

        A mistake is revoked and re-issued rather than corrected in place: the
        recipient still holds the wrong paper, and the trail has to show that
        it existed.
        """
        document = await self.get_document(document_id)
        if document.revoked_at is not None:
            raise ConflictError("This document is already revoked")

        document.revoked_at = datetime.now(UTC)
        document.revoked_by_user_id = revoked_by
        document.revoke_reason = reason
        document.updated_by = revoked_by
        await self.session.flush()
        return document

    async def attach_signature(self, document_id: uuid.UUID, png: bytes) -> IssuedDocument:
        """Put the signature somebody drew on a device onto this document.

        Refused rather than silently accepted in three cases, because each one
        would produce a piece of paper that says something untrue: a document
        that does not have a line to sign, one that was already signed, and one
        that has been revoked.
        """
        document = await self.get_document(document_id)
        if document.signature_mode != "line":
            raise ValidationError("This document has no signature line")
        if document.signed_at is not None:
            raise ConflictError("This document is already signed")
        if document.revoked_at is not None:
            raise ConflictError("This document is revoked")
        if not png.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValidationError("A signature has to be a PNG")
        if len(png) > MAX_SIGNATURE_BYTES:
            raise ValidationError("Signature too large")

        document.signature_png = png
        document.signed_at = datetime.now(UTC)
        await self.session.flush()

        logger.info(
            "document_signed",
            tenant_id=str(self.tenant_id),
            document_id=str(document.id),
            bytes=len(png),
        )
        return document

    async def get_document(self, document_id: uuid.UUID) -> IssuedDocument:
        document = (
            await self.session.execute(
                select(IssuedDocument)
                .where(IssuedDocument.tenant_id == self.tenant_id)
                .where(IssuedDocument.id == document_id)
            )
        ).scalar_one_or_none()
        if document is None:
            raise NotFoundError("Document not found")
        return document

    async def list_documents(self, *, member_id: uuid.UUID | None = None) -> list[IssuedDocument]:
        query = (
            select(IssuedDocument)
            .where(IssuedDocument.tenant_id == self.tenant_id)
            .order_by(IssuedDocument.issued_at.desc())
        )
        if member_id is not None:
            query = query.where(IssuedDocument.member_id == member_id)
        return list((await self.session.execute(query)).scalars().all())

    async def _current_fee(self, member_id: uuid.UUID, on: date) -> tuple[str, Decimal, str] | None:
        """The fee assignment in force on the given day, if there is one.

        Bounded by the validity range rather than taking the newest row: a
        certificate that names next season's fee because it was already
        entered would be wrong on the day it is handed over.
        """
        row = (
            await self.session.execute(
                select(FeeType.name, FeeType.amount, FeeType.interval)
                .join(MemberFee, MemberFee.fee_type_id == FeeType.id)
                .where(MemberFee.tenant_id == self.tenant_id)
                .where(MemberFee.member_id == member_id)
                .where(MemberFee.deleted_at.is_(None))
                .where(MemberFee.valid_from <= on)
                .where(or_(MemberFee.valid_to.is_(None), MemberFee.valid_to >= on))
                .order_by(MemberFee.valid_from.desc())
            )
        ).first()
        return (row[0], row[1], row[2]) if row else None

    async def _current_offices(self, member_id: uuid.UUID, on: date) -> list[str]:
        """Offices held on the given day, in the club's own order."""
        rows = (
            await self.session.execute(
                select(Function.name)
                .join(MemberFunction, MemberFunction.function_id == Function.id)
                .where(MemberFunction.tenant_id == self.tenant_id)
                .where(MemberFunction.member_id == member_id)
                .where(MemberFunction.valid_from <= on)
                .where(
                    or_(
                        MemberFunction.valid_to.is_(None),
                        MemberFunction.valid_to >= on,
                    )
                )
                .order_by(Function.name)
            )
        ).all()
        return [name for (name,) in rows]

    def _verification_code(self) -> str:
        return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))


async def document_by_verification_code(
    session: AsyncSession, code: str
) -> tuple[IssuedDocument, str, str, str] | None:
    """Look up a document for the public check page, across all clubs.

    Deliberately unscoped by tenant: whoever scans a QR has no club context and
    should not need one. The code is the credential, which is why it is long
    and random rather than sequential.

    Returns the document plus the club name, the member name and the club's
    time zone, so the caller can answer without a second round trip — and can
    date the document in the club's day rather than the server's.
    """
    row = (
        await session.execute(
            select(
                IssuedDocument,
                Tenant.name,
                Tenant.timezone,
                Member.first_name,
                Member.last_name,
            )
            .join(Tenant, Tenant.id == IssuedDocument.tenant_id)
            .join(Member, Member.id == IssuedDocument.member_id)
            .where(IssuedDocument.verification_code == code)
        )
    ).first()
    if row is None:
        return None

    document, club_name, timezone, first_name, last_name = row
    # Abbreviated: whoever finds a lost PDF learns that the document is real,
    # not who exactly it belongs to.
    member_name = f"{first_name[:1]}. {last_name}" if first_name else last_name
    return document, club_name, member_name, timezone
