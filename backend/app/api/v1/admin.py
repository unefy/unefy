import math
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import COOKIE_NAME, _set_session_cookie
from app.config import get_settings
from app.core.exceptions import ValidationError
from app.core.rate_limit import RateLimit
from app.database import get_db_session
from app.dependencies import AuthContext, get_authenticated_user, require_platform_admin
from app.schemas.admin import ImpersonateRequest
from app.services.admin import AdminService

router = APIRouter()


def _meta(total: int, page: int, per_page: int) -> dict[str, Any]:
    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": math.ceil(total / per_page) if per_page else 0,
    }


# --- Clubs and users ---


@router.get("/tenants")
async def list_tenants(
    _auth: AuthContext = Depends(require_platform_admin),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None),
) -> dict[str, Any]:
    """List every club on the platform."""
    tenants, total = await AdminService(session).list_tenants(
        offset=(page - 1) * per_page, limit=per_page, search=search
    )
    return {"data": tenants, "meta": _meta(total, page, per_page)}


@router.get("/tenants/{tenant_id}")
async def get_tenant(
    tenant_id: uuid.UUID,
    _auth: AuthContext = Depends(require_platform_admin),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Fetch a single club."""
    return {"data": await AdminService(session).get_tenant(tenant_id)}


@router.get("/tenants/{tenant_id}/users")
async def list_tenant_users(
    tenant_id: uuid.UUID,
    _auth: AuthContext = Depends(require_platform_admin),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Login accounts attached to a club."""
    return {"data": await AdminService(session).list_tenant_users(tenant_id)}


@router.get("/tenants/{tenant_id}/members")
async def list_tenant_members(
    tenant_id: uuid.UUID,
    _auth: AuthContext = Depends(require_platform_admin),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Members of a club, without personal or banking details."""
    return {"data": await AdminService(session).list_tenant_members(tenant_id)}


@router.get("/users")
async def list_users(
    _auth: AuthContext = Depends(require_platform_admin),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None),
) -> dict[str, Any]:
    """List every user account on the platform."""
    users, total = await AdminService(session).list_users(
        offset=(page - 1) * per_page, limit=per_page, search=search
    )
    return {
        "data": [
            {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "image": user.image,
                "email_verified": user.email_verified,
                "locale": user.locale,
                "is_superuser": user.is_superuser,
                "created_at": user.created_at,
            }
            for user in users
        ],
        "meta": _meta(total, page, per_page),
    }


@router.get("/users/{user_id}")
async def get_user(
    user_id: uuid.UUID,
    _auth: AuthContext = Depends(require_platform_admin),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Fetch a single user account."""
    user = await AdminService(session).get_user(user_id)
    return {
        "data": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "image": user.image,
            "email_verified": user.email_verified,
            "locale": user.locale,
            "is_superuser": user.is_superuser,
            "created_at": user.created_at,
        }
    }


@router.get("/users/{user_id}/memberships")
async def list_user_memberships(
    user_id: uuid.UUID,
    _auth: AuthContext = Depends(require_platform_admin),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Clubs a user belongs to — the choices offered before impersonating."""
    return {"data": await AdminService(session).list_user_memberships(user_id)}


# --- Impersonation ---


@router.post(
    "/impersonate",
    dependencies=[Depends(RateLimit(limit=20, window=3600, scope="impersonate"))],
)
async def impersonate(
    payload: ImpersonateRequest,
    request: Request,
    auth: AuthContext = Depends(require_platform_admin),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> JSONResponse:
    """Assume a user's identity for support purposes.

    Cookie-session only. Mobile bearer tokens are deliberately unsupported —
    impersonation relies on parking the admin's original session token so it
    can be handed back, which has no equivalent in the stateless JWT flow.
    """
    current_token = request.cookies.get(COOKIE_NAME)
    if not current_token:
        raise ValidationError("Impersonation requires a browser session")

    token, body, ttl = await AdminService(session).start_impersonation(
        auth, payload, current_token, request
    )
    await session.commit()

    settings = get_settings()
    response = JSONResponse(content=jsonable_encoder({"data": body}))
    # Deliberately not `_set_session_cookie`: the cookie must expire with the
    # impersonation session, not after the normal seven days.
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="lax",
        max_age=ttl,
        path="/",
        domain=settings.COOKIE_DOMAIN,
    )
    return response


@router.post("/impersonate/stop")
async def stop_impersonation(
    request: Request,
    auth: AuthContext = Depends(get_authenticated_user),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> JSONResponse:
    """End impersonation and restore the admin's own session.

    Guarded by plain authentication rather than `require_platform_admin`: the
    caller is, by construction, running as the impersonated (non-admin) user,
    so the admin guard would reject the very request meant to undo that state.
    The service verifies that the session really is an impersonation session.
    """
    current_token = request.cookies.get(COOKIE_NAME)
    if not current_token:
        raise ValidationError("Not an impersonation session")

    original = await AdminService(session).stop_impersonation(auth, current_token, request)
    await session.commit()

    settings = get_settings()
    if original is None:
        # The admin's own session expired while they were impersonating.
        response = JSONResponse(content={"data": {"restored": False}})
        response.delete_cookie(key=COOKIE_NAME, path="/", domain=settings.COOKIE_DOMAIN)
        return response

    response = JSONResponse(content={"data": {"restored": True}})
    _set_session_cookie(response, original, settings)
    return response


# --- Audit log ---


@router.get("/audit-log")
async def list_audit_log(
    _auth: AuthContext = Depends(require_platform_admin),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=100),
    action: str | None = Query(default=None),
    tenant_id: uuid.UUID | None = Query(default=None),  # noqa: B008
) -> dict[str, Any]:
    """Read the platform-admin audit trail. Append-only — no write path exists."""
    entries, total = await AdminService(session).list_audit_log(
        offset=(page - 1) * per_page,
        limit=per_page,
        action=action,
        tenant_id=tenant_id,
    )
    return {"data": entries, "meta": _meta(total, page, per_page)}
