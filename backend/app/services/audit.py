import uuid
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from typing import Any

from fastapi import Request
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import AuthContext
from app.models.audit import AdminAuditLog, TenantAuditLog
from app.models.user import User


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


def jsonable(value: Any) -> Any:
    """Reduce a value to something JSONB can hold, without losing meaning."""
    if isinstance(value, uuid.UUID | datetime | date):
        return value.isoformat() if not isinstance(value, uuid.UUID) else str(value)
    return value


def diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """Field-level before/after, limited to fields that actually changed.

    Unchanged fields are dropped on purpose: a log that repeats the whole row on
    every edit is a second copy of the data, including of personal data the
    retention job is meant to be able to remove.
    """
    return {
        field: {"from": jsonable(before[field]), "to": jsonable(value)}
        for field, value in after.items()
        if before.get(field) != value
    }


async def record_tenant_action(
    session: AsyncSession,
    auth: AuthContext,
    action: str,
    *,
    target_type: str,
    target_id: uuid.UUID,
    request: Request | None = None,
    changes: dict[str, Any] | None = None,
    reason: str | None = None,
) -> TenantAuditLog:
    """Append an entry to a club's own audit log.

    Same transactional coupling as `record_admin_action`: the entry commits with
    the action it describes, so an unauditable change does not happen. For
    attendance this is not bookkeeping but the evidence itself — the answer to
    "how do you know" is this row.
    """
    entry = TenantAuditLog(
        tenant_id=auth.tenant,
        actor_user_id=auth.user_id,
        impersonator_id=auth.impersonator_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        changes=changes or None,
        reason=reason,
        ip_address=client_ip(request) if request else None,
    )
    session.add(entry)
    await session.flush()
    return entry


async def list_tenant_audit(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    targets: Mapping[str, Sequence[uuid.UUID]],
) -> list[tuple[TenantAuditLog, str | None]]:
    """The trail for a set of objects, oldest first — a history, not a feed.

    Takes several target types at once so one screen can show one story: a
    session and the corrections to its records belong in the same list, in the
    order they happened.

    Returns each entry with the actor's name. A trail that shows a user id is
    unreadable in exactly the situation it exists for.
    """
    conditions = [
        and_(TenantAuditLog.target_type == target_type, TenantAuditLog.target_id.in_(ids))
        for target_type, ids in targets.items()
        if ids
    ]
    if not conditions:
        return []

    result = await session.execute(
        select(TenantAuditLog, User.name)
        .outerjoin(User, TenantAuditLog.actor_user_id == User.id)
        .where(TenantAuditLog.tenant_id == tenant_id)
        .where(or_(*conditions))
        .order_by(TenantAuditLog.created_at.asc())
    )
    return [(row[0], row[1]) for row in result.all()]
