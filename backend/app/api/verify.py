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
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.rate_limit import RateLimit
from app.database import get_db_session
from app.repositories.shooting import certificate_by_verification_code
from app.services.document import document_by_verification_code
from app.services.donation import receipt_by_verification_code

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
    """Check one code, whatever kind of document it belongs to.

    Three kinds share this path: the §14 proof, the club's own certificates
    and donation receipts.
    One page for both, because the person scanning the QR is holding a piece
    of paper and does not know — or care — which of our tables it came from.
    The codes come from the same alphabet and the same length, so a collision
    is a lottery win rather than a design problem.
    """
    found = await certificate_by_verification_code(session, verification_code)
    if found is not None:
        certificate, club_name, member_name = found
        return {
            "data": {
                "kind": "shooting_proof",
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

    issued = await document_by_verification_code(session, verification_code)
    if issued is not None:
        document, club_name, member_name, timezone = issued
        return {
            "data": {
                "kind": "document",
                "valid": document.revoked_at is None,
                "revoked": document.revoked_at is not None,
                # The title, never the text. Whoever holds the paper can read
                # it; whoever merely found a code should learn that the
                # document is genuine and nothing further.
                "title": document.title,
                # The club's day, not the server's: a document issued at
                # 00:30 in Berlin is dated the 11th on the paper and must not
                # read as the 10th here.
                "issued_at": document.issued_at.astimezone(ZoneInfo(timezone)).date().isoformat(),
                "club_name": club_name,
                "member_name": member_name,
            }
        }

    donation = await receipt_by_verification_code(session, verification_code)
    if donation is not None:
        receipt, donor_name = donation
        return {
            "data": {
                "kind": "donation_receipt",
                "valid": receipt.revoked_at is None,
                "revoked": receipt.revoked_at is not None,
                # No amount. Whoever merely found a code learns that the
                # receipt is genuine, not what somebody gave — and a donation
                # is nobody else's business.
                "issued_at": receipt.issued_at.date().isoformat(),
                "received_on": receipt.received_on.isoformat(),
                "club_name": receipt.club_name,
                "member_name": donor_name,
            }
        }

    # The same 404 for "never existed" and for malformed input — this
    # endpoint answers questions about one code, never about the space.
    raise NotFoundError("Unknown verification code")
