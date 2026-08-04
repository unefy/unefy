"""The shooting module's endpoints — the first ones behind `require_module`.

Everything here 403s for a club whose sports don't carry the module; the
role checks sit on top of that per endpoint.
"""

import csv
import io
import math
import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.dependencies import AuthContext, require_module, require_role
from app.schemas.shooting import (
    CertificateIssue,
    CertificateResponse,
    CertificateRevoke,
    ProofEvaluationResponse,
    ShootingProofRuleCreate,
    ShootingProofRuleResponse,
    ShootingProofRuleUpdate,
    ShootingRecordDetailResponse,
    ShootingRecordDetailUpdate,
)
from app.services.shooting import ShootingService

router = APIRouter(dependencies=[Depends(require_module("shooting"))])

# Issuing and evaluating the proof is board work, like scanning; configuring
# the rules is club configuration, like everything else under settings.
require_board = require_role("owner", "admin", "board")
require_admin = require_role("owner", "admin")


def _service(session: AsyncSession, auth: AuthContext) -> ShootingService:
    return ShootingService(session, auth)


# --- Record details ---


@router.patch("/records/{record_id}")
async def update_record_detail(
    record_id: uuid.UUID,
    data: ShootingRecordDetailUpdate,
    auth: AuthContext = Depends(require_board),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, object]:
    detail = await _service(session, auth).upsert_detail(record_id, data)
    return {"data": ShootingRecordDetailResponse.model_validate(detail).model_dump(mode="json")}


# --- Rules ---


@router.get("/rules")
async def list_rules(
    auth: AuthContext = Depends(require_board),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, object]:
    rules = await _service(session, auth).rules.get_all_ordered()
    return {
        "data": [
            ShootingProofRuleResponse.model_validate(rule).model_dump(mode="json") for rule in rules
        ]
    }


@router.post("/rules", status_code=201)
async def create_rule(
    data: ShootingProofRuleCreate,
    auth: AuthContext = Depends(require_admin),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, object]:
    rule = await _service(session, auth).create_rule(data)
    return {"data": ShootingProofRuleResponse.model_validate(rule).model_dump(mode="json")}


@router.patch("/rules/{rule_id}")
async def update_rule(
    rule_id: uuid.UUID,
    data: ShootingProofRuleUpdate,
    auth: AuthContext = Depends(require_admin),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, object]:
    rule = await _service(session, auth).update_rule(rule_id, data)
    return {"data": ShootingProofRuleResponse.model_validate(rule).model_dump(mode="json")}


@router.delete("/rules/{rule_id}", status_code=204)
async def delete_rule(
    rule_id: uuid.UUID,
    auth: AuthContext = Depends(require_admin),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> None:
    await _service(session, auth).delete_rule(rule_id)


# --- Evaluation & certificates ---


@router.get("/proof/{member_id}")
async def evaluate_proof(
    member_id: uuid.UUID,
    rule_key: str,
    as_of: date | None = None,
    auth: AuthContext = Depends(require_board),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, object]:
    """The live evaluation — no freeze, no certificate, just the numbers."""
    evaluation = await _service(session, auth).evaluate(member_id, rule_key, as_of)
    return {"data": ProofEvaluationResponse.model_validate(evaluation).model_dump(mode="json")}


@router.post("/certificates", status_code=201)
async def issue_certificate(
    data: CertificateIssue,
    auth: AuthContext = Depends(require_board),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, object]:
    service = _service(session, auth)
    certificate = await service.issue_certificate(data)
    name = await service.member_name(certificate.member_id)
    return {
        "data": CertificateResponse.model_validate(certificate).model_dump(mode="json")
        | {"member_name": name}
    }


@router.get("/certificates")
async def list_certificates(
    member_id: uuid.UUID | None = None,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    auth: AuthContext = Depends(require_board),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, object]:
    service = _service(session, auth)
    rows = await service.certificates.list_with_names(
        member_id=member_id, offset=(page - 1) * per_page, limit=per_page
    )
    total = await service.certificates.count_filtered(member_id=member_id)
    return {
        "data": [
            CertificateResponse.model_validate(certificate).model_dump(mode="json")
            | {"member_name": name}
            for certificate, name in rows
        ],
        "meta": {
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": math.ceil(total / per_page) if total else 0,
        },
    }


@router.post("/certificates/{certificate_id}/revoke")
async def revoke_certificate(
    certificate_id: uuid.UUID,
    data: CertificateRevoke,
    auth: AuthContext = Depends(require_board),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, object]:
    certificate = await _service(session, auth).revoke_certificate(
        certificate_id, reason=data.reason
    )
    return {"data": CertificateResponse.model_validate(certificate).model_dump(mode="json")}


# --- Range book ---


@router.get("/range-book")
async def range_book(
    from_date: date = Query(alias="from"),  # noqa: B008
    to_date: date = Query(alias="to"),  # noqa: B008
    auth: AuthContext = Depends(require_board),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> Response:
    """The Standbuch as CSV — semicolons and a BOM, because the file's whole
    purpose is to be opened in a German-locale Excel without an import wizard.
    The column set stays deliberately plain; association-specific forms (DSB,
    BDS) are formatting on top of exactly these rows.
    """
    service = _service(session, auth)
    rows = await service.proof.range_book_rows(from_date, to_date)

    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(
        [
            "Datum",
            "Einheit",
            "Ort",
            "Name",
            "Disziplin",
            "Waffenart",
            "Schusszahl",
            "Aufsicht",
            "Erfassung",
        ]
    )
    for occurred_on, title, location, name, discipline, weapon, rounds, supervisor, method in rows:
        writer.writerow(
            [
                occurred_on.isoformat() if isinstance(occurred_on, date) else occurred_on,
                title,
                location or "",
                name or "",
                discipline or "",
                weapon or "",
                rounds if rounds is not None else "",
                supervisor or "",
                method,
            ]
        )

    filename = f"standbuch_{from_date.isoformat()}_{to_date.isoformat()}.csv"
    return Response(
        content="\ufeff" + buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
