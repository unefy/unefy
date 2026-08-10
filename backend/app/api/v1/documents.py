"""Templates, and the documents issued from them."""

import uuid
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db_session
from app.dependencies import AuthContext, require_role
from app.models.member import Member
from app.models.tenant import Tenant
from app.schemas.document import (
    IssuedDocumentResponse,
    IssueRequest,
    PreviewResponse,
    RevokeRequest,
    TemplateCreate,
    TemplatePreview,
    TemplateResponse,
    TemplateUpdate,
    VariableResponse,
)
from app.services import document_variables as variables
from app.services.document import DocumentService
from app.services.document_pdf import DocumentLetter, build_document_pdf

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
    tenant = await session.get(Tenant, auth.tenant)
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
        letterhead=_letterhead(tenant) if tenant else (),
        footer=_footer(tenant) if tenant else (),
        verification_code=document.verification_code,
        verification_url=(
            f"{settings.WEB_APP_URL.rstrip('/')}/verify/{document.verification_code}"
            if document.verification_code
            else None
        ),
        revoked=document.revoked_at is not None,
        signature_line=tenant.name if tenant else None,
    )

    name = f"{document.template_name}-{member.member_number if member else document.member_id}"
    return Response(
        content=build_document_pdf(letter),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{_ascii_filename(name)}.pdf"',
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
