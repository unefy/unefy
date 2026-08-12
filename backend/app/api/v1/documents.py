"""Templates, and the documents issued from them."""

import uuid
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.database import get_db_session
from app.dependencies import AuthContext, get_current_user, require_role
from app.models.document import IssuedDocument
from app.models.member import Member
from app.models.tenant import Tenant
from app.repositories.member import MemberRepository
from app.schemas.document import (
    IssuedDocumentResponse,
    IssueRequest,
    PreviewResponse,
    RevokeRequest,
    SignatureLinkResponse,
    StarterResponse,
    TemplateCreate,
    TemplatePreview,
    TemplateResponse,
    TemplateUpdate,
    VariableResponse,
)
from app.services import document_variables as variables
from app.services import signature_link
from app.services.document import DocumentService
from app.services.document_pdf import DocumentLetter, build_document_pdf
from app.services.document_starters import STARTERS
from app.services.qr import qr_matrix

router = APIRouter()


@router.get("/variables")
async def list_variables(
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
) -> dict[str, Any]:
    """The placeholders a template may use.

    Served from the same catalogue that validates a save and substitutes at
    issuing time. A second list maintained by the editor would be a second
    chance to disagree with the first.
    """
    del auth
    return {
        "data": [
            VariableResponse(key=v.key, description=v.description).model_dump()
            for v in variables.VARIABLES
        ]
    }


@router.get("/starter-templates")
async def list_starter_templates(
    auth: AuthContext = Depends(require_role("owner", "admin")),  # noqa: B008
) -> dict[str, Any]:
    """Ready-made wordings, as drafts.

    Read-only: choosing one opens the editor with the text in it, and the club
    saves it — or does not. Nothing is installed on a club's behalf, which is
    the only honest way to hand over a document somebody will sign.
    """
    del auth
    return {
        "data": [
            StarterResponse(
                key=s.key,
                name=s.name,
                title=s.title,
                body=s.body,
                caveat=s.caveat,
                include_letterhead=s.include_letterhead,
                include_footer=s.include_footer,
                verifiable=s.verifiable,
                signature_mode=s.signature_mode,
            ).model_dump()
            for s in STARTERS
        ]
    }


@router.post("/templates/preview")
async def preview_template(
    data: TemplatePreview,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Render a draft against obviously fake values.

    Stand-ins rather than a real member: somebody proof-reading the wording
    should never have to wonder whether they are looking at a real person's
    data. Unknown names come back listed instead of raised, so the editor can
    mark all of them at once.
    """
    tenant = await session.get(Tenant, auth.tenant)
    values = variables.sample_values(
        tenant.name if tenant else "Musterverein e. V.",
        tenant.timezone if tenant else "Europe/Berlin",
    )
    return {
        "data": PreviewResponse(
            rendered=variables.render(data.body, values),
            unknown=variables.unknown_placeholders(data.body),
        ).model_dump()
    }


@router.get("/templates")
async def list_templates(
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    include_inactive: bool = Query(default=False),
) -> dict[str, Any]:
    templates = await DocumentService(session, auth.tenant).list_templates(
        include_inactive=include_inactive
    )
    return {"data": [TemplateResponse.model_validate(t).model_dump(mode="json") for t in templates]}


@router.post("/templates", status_code=201)
async def create_template(
    data: TemplateCreate,
    auth: AuthContext = Depends(require_role("owner", "admin")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Writing the club's own wording is a settings-level act, hence admin."""
    template = await DocumentService(session, auth.tenant).create_template(
        data, created_by=auth.user_id
    )
    return {"data": TemplateResponse.model_validate(template).model_dump(mode="json")}


@router.get("/templates/{template_id}")
async def get_template(
    template_id: uuid.UUID,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    template = await DocumentService(session, auth.tenant).get_template(template_id)
    return {"data": TemplateResponse.model_validate(template).model_dump(mode="json")}


@router.patch("/templates/{template_id}")
async def update_template(
    template_id: uuid.UUID,
    data: TemplateUpdate,
    auth: AuthContext = Depends(require_role("owner", "admin")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    template = await DocumentService(session, auth.tenant).update_template(
        template_id, data, updated_by=auth.user_id
    )
    return {"data": TemplateResponse.model_validate(template).model_dump(mode="json")}


@router.delete("/templates/{template_id}", status_code=204)
async def delete_template(
    template_id: uuid.UUID,
    auth: AuthContext = Depends(require_role("owner", "admin")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> Response:
    """Documents already issued from it are unaffected — they carry their own
    copy of the text."""
    await DocumentService(session, auth.tenant).delete_template(template_id)
    return Response(status_code=204)


# --- Issued documents ---
#
# `/me/...` before the parameterised routes: `/{document_id}` would parse "me"
# as a UUID and reject it before the self-service handler ever ran. The same
# ordering rule as in members.py.


async def _own_member_id(session: AsyncSession, auth: AuthContext) -> uuid.UUID:
    member = await MemberRepository(session, auth.tenant).get_by_user_id(auth.user_id)
    if member is None:
        raise NotFoundError("No member record is linked to this account")
    return member.id


@router.get("/me")
async def list_own_documents(
    auth: AuthContext = Depends(get_current_user),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """What the club has issued to the caller, newest first.

    Revoked documents stay in the list rather than disappearing from it. A
    member who was handed a certificate and can no longer find it would have to
    ask why, and "it is here, marked invalid" is the honest answer — the club
    withdrew it, it did not cease to exist.
    """
    member_id = await _own_member_id(session, auth)
    documents = await DocumentService(session, auth.tenant).list_documents(member_id=member_id)
    return {
        "data": [
            IssuedDocumentResponse.model_validate(d).model_dump(mode="json") for d in documents
        ]
    }


@router.get("/me/{document_id}/pdf")
async def download_own_document(
    document_id: uuid.UUID,
    auth: AuthContext = Depends(get_current_user),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> Response:
    """The caller's own document, as it was issued.

    A separate route rather than a role check inside the board one: the id in
    the path is not authorisation here, the session is, and a member asking for
    somebody else's document gets the same 404 as for one that does not exist.
    Answering 403 would confirm that the document is real.
    """
    member_id = await _own_member_id(session, auth)
    service = DocumentService(session, auth.tenant)
    document = await service.get_document(document_id)
    if document.member_id != member_id:
        raise NotFoundError("Document not found")
    return await _document_pdf_response(session, auth.tenant, document)


@router.get("")
async def list_documents(
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    member_id: uuid.UUID | None = Query(default=None),  # noqa: B008
) -> dict[str, Any]:
    """What the club has issued, newest first."""
    documents = await DocumentService(session, auth.tenant).list_documents(member_id=member_id)
    return {
        "data": [
            IssuedDocumentResponse.model_validate(d).model_dump(mode="json") for d in documents
        ]
    }


@router.post("/members/{member_id}/issue", status_code=201)
async def issue_document(
    member_id: uuid.UUID,
    data: IssueRequest,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Issue a document for this member and freeze its text."""
    document = await DocumentService(session, auth.tenant).issue(
        member_id, data.template_id, issued_by=auth.user_id
    )
    return {"data": IssuedDocumentResponse.model_validate(document).model_dump(mode="json")}


@router.post("/{document_id}/revoke")
async def revoke_document(
    document_id: uuid.UUID,
    data: RevokeRequest,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    document = await DocumentService(session, auth.tenant).revoke(
        document_id, reason=data.reason, revoked_by=auth.user_id
    )
    return {"data": IssuedDocumentResponse.model_validate(document).model_dump(mode="json")}


@router.post("/{document_id}/signature-link", status_code=201)
async def create_signature_link(
    document_id: uuid.UUID,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """A link that lets somebody sign this document on their own phone.

    Asked for deliberately by a signed-in board member, never handed out on a
    list page: the link is the whole authorisation, so it should exist only
    while somebody is standing there meaning to sign.
    """
    document = await DocumentService(session, auth.tenant).get_document(document_id)
    if document.signature_mode != "line":
        raise ValidationError("This document has no signature line")
    if document.signed_at is not None:
        raise ConflictError("This document is already signed")
    if document.revoked_at is not None:
        raise ConflictError("This document is revoked")

    token = await signature_link.issue(
        signature_link.SignatureTarget(tenant_id=auth.tenant, document_id=document_id)
    )
    url = f"{get_settings().WEB_APP_URL.rstrip('/')}/sign/{token}"
    return {
        "data": SignatureLinkResponse(
            url=url,
            expires_in=signature_link.TTL_SECONDS,
            qr=qr_matrix(url),
        ).model_dump()
    }


@router.get("/{document_id}/pdf")
async def download_document(
    document_id: uuid.UUID,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> Response:
    """The document as it was issued, re-rendered from the frozen text.

    Re-rendered rather than stored as a file: the bytes are cheap to make
    again, and a PDF in storage is one more thing that can drift from the row
    that is supposed to define it.
    """
    service = DocumentService(session, auth.tenant)
    document = await service.get_document(document_id)
    return await _document_pdf_response(session, auth.tenant, document)


async def _document_pdf_response(
    session: AsyncSession, tenant_id: uuid.UUID, document: IssuedDocument
) -> Response:
    """The bytes, shared by the board's route and the member's own.

    One renderer for both: a member's copy that could differ from the board's
    would make the verification code meaningless.
    """
    tenant = await session.get(Tenant, tenant_id)
    member = await session.get(Member, document.member_id)

    settings = get_settings()
    letter = DocumentLetter(
        club_name=tenant.name if tenant else "",
        title=document.title,
        body=document.body,
        # The club's day, so the printed date matches the check page.
        issued_on=document.issued_at.astimezone(
            ZoneInfo(tenant.timezone if tenant else "Europe/Berlin")
        ).date(),
        # From the document, not from the template it came out of: the template
        # is free to change afterwards, and it may be gone entirely.
        letterhead=_letterhead(tenant) if tenant and document.include_letterhead else (),
        footer=_footer(tenant) if tenant and document.include_footer else (),
        verification_code=document.verification_code,
        verification_url=(
            f"{settings.WEB_APP_URL.rstrip('/')}/verify/{document.verification_code}"
            if document.verification_code
            else None
        ),
        revoked=document.revoked_at is not None,
        signature_line=(tenant.name if document.signature_mode == "line" and tenant else None),
        signature_drawing=document.signature_png,
        machine_made=document.signature_mode == "machine",
    )

    name = f"{document.template_name}-{member.member_number if member else document.member_id}"
    return Response(
        content=build_document_pdf(letter),
        media_type="application/pdf",
        headers={
            # `inline`, so the browser's viewer opens it: the usual next step
            # after issuing a document is reading it, not filing it. The
            # filename still travels along for whoever then saves it.
            "Content-Disposition": f'inline; filename="{_ascii_filename(name)}.pdf"',
            "Cache-Control": "no-store",
        },
    )


def _letterhead(tenant: Tenant) -> tuple[str, ...]:
    """Address lines under the club name.

    The logo stays out for now: `logo_url` points anywhere, and fetching it at
    render time would mean a blocking request to a URL the club controls —
    slow at best, an SSRF at worst.
    """
    lines = []
    street = (tenant.street or "").strip()
    town = " ".join(p for p in (tenant.zip_code, tenant.city) if p).strip()
    if street:
        lines.append(street)
    if town:
        lines.append(town)
    if tenant.email:
        lines.append(tenant.email)
    return tuple(lines)


def _footer(tenant: Tenant) -> tuple[str, ...]:
    parts = []
    if tenant.registration_number:
        court = f" ({tenant.registration_court})" if tenant.registration_court else ""
        parts.append(f"{tenant.registration_number}{court}")
    if tenant.tax_number:
        parts.append(f"Steuernummer {tenant.tax_number}")
    if tenant.is_nonprofit:
        parts.append("als gemeinnützig anerkannt")
    return tuple(parts)


def _ascii_filename(value: str) -> str:
    """A filename that survives every HTTP client.

    Umlauts in a `Content-Disposition` header without the RFC 5987 form are
    read differently by different clients; the club's own name for the
    template is not worth that.
    """
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in value)
    return safe.strip("-").lower() or "dokument"
