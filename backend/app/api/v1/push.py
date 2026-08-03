"""`/api/v1/push/devices` — where a phone asks to be woken.

Registration is an upsert by token: `onNewToken` on the device and a plain
re-open of the app both land here, and both simply refresh the row. The stored
role filters *wake-ups* only — the sync endpoints keep checking the live role
on every read, so a stale stored role costs at most a pointless (and refused)
sync, never data.

Unregistering is a POST rather than a DELETE with a body: the token must not
appear in a URL (it would land in every access log along the way), and a
DELETE body is the one request shape proxies still mangle.
"""

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import AppError
from app.database import get_db_session
from app.dependencies import AuthContext, get_current_user
from app.repositories.push_device import PushDeviceRepository
from app.schemas.push import PushDeviceRegister, PushDeviceUnregister

router = APIRouter()


class PushDisabledError(AppError):
    """Push is deliberately off — a config state, not a failure."""

    def __init__(self) -> None:
        super().__init__(
            status_code=503,
            code="PUSH_DISABLED",
            message="Push notifications are not configured on this server",
        )


def _require_enabled() -> None:
    settings = get_settings()
    if not settings.PUSH_ENABLED or not settings.FCM_CREDENTIALS_FILE:
        # 503 with a name, not 500: a self-hosted deployment without a Firebase
        # project is a perfectly healthy server that simply does not push. The
        # client reads the code and stops asking for the session.
        raise PushDisabledError()


@router.post("/devices")
async def register_device(
    body: PushDeviceRegister,
    auth: AuthContext = Depends(get_current_user),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Register this device, or refresh its row. Idempotent by design."""
    _require_enabled()
    await PushDeviceRepository(session).upsert(
        tenant_id=auth.tenant,
        user_id=auth.user_id,
        token=body.token,
        platform=body.platform,
        role=auth.role or "member",
    )
    return {"data": {"registered": True}}


@router.post("/devices/unregister", status_code=204)
async def unregister_device(
    body: PushDeviceUnregister,
    auth: AuthContext = Depends(get_current_user),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> None:
    """Forget this device. Sign-out calls this so the old club stops waking
    a phone that now belongs to someone else's account.

    Deleting by token alone, deliberately: the token never leaves the device
    except toward FCM and this endpoint, so presenting it is ownership. Scoping
    to the caller would leave the row behind in the one case that matters —
    the device re-registered under another account and wants the old row gone.
    Answers 204 whether or not a row existed: the goal is absence.
    """
    _require_enabled()
    await PushDeviceRepository(session).delete_by_token(body.token)
