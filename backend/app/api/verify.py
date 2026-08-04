"""The public certificate check — unauthenticated, minimal, rate-limited.

Lives outside `/api/v1` like `/health`: it is not an API for clients but a
page-sized answer for whoever scans the QR on a printed proof. The likelier
forgery is a PDF built in Word, not a manipulating club — this page lets an
association clerk check a document against the issuing server in one request.

Minimal on purpose: valid yes/no, period, count, issue date, club, and an
*abbreviated* name. Whoever finds a lost PDF must not learn on which evenings
a person was where — the certificate says that, this page must not.
"""

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.rate_limit import RateLimit
from app.database import get_db_session
from app.repositories.shooting import certificate_by_verification_code

router = APIRouter(tags=["verify"])


@router.get(
    "/verify/{verification_code}",
    # Generous for a human checking a document, hostile to enumeration: the
    # code space is ~57 bits, so even at this rate guessing is not a plan.
    dependencies=[Depends(RateLimit(limit=30, window=60, scope="verify"))],
)
async def verify_certificate(
    verification_code: str,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    found = await certificate_by_verification_code(session, verification_code)
    if found is None:
        # The same 404 for "never existed" and for malformed input — this
        # endpoint answers questions about one code, never about the space.
        raise NotFoundError("Unknown verification code")

    certificate, club_name, member_name = found
    return {
        "data": {
            "valid": certificate.revoked_at is None,
            "revoked": certificate.revoked_at is not None,
            "result": certificate.result,
            "period_start": certificate.period_start.isoformat(),
            "period_end": certificate.period_end.isoformat(),
            "session_count": certificate.session_count,
            "issued_at": certificate.issued_at.date().isoformat(),
            "club_name": club_name,
            "member_name": member_name,
        }
    }
