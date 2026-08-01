import uuid
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import AuthContext
from app.models.audit import AdminAuditLog


def client_ip(request: Request) -> str | None:
    from app.core.rate_limit import _client_ip

    return _client_ip(request)


async def record_admin_action(
    session: AsyncSession,
    auth: AuthContext,
    action: str,
    *,
    request: Request | None = None,
    target_type: str | None = None,
    target_id: uuid.UUID | None = None,
    tenant_id: uuid.UUID | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    """Append an entry to the platform-admin audit log.

    The entry is added to the caller's session and therefore commits together
    with the action it describes. That coupling is intentional: an action that
    rolls back leaves no phantom log line, and a log write that fails takes the
    action down with it. An unauditable privileged action must not succeed.
    """
    session.add(
        AdminAuditLog(
            actor_user_id=auth.user_id,
            impersonator_id=auth.impersonator_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            tenant_id=tenant_id,
            payload=payload,
            ip_address=client_ip(request) if request else None,
        )
    )
    await session.flush()
