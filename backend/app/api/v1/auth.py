import json
import secrets
import uuid
from typing import Any

import structlog
from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import RedirectResponse, Response

from app.config import Settings, get_settings
from app.core.rate_limit import RateLimit
from app.database import get_db_session
from app.models.tenant import Tenant
from app.models.user import TenantMembership, User
from app.redis import get_redis

logger = structlog.get_logger()
router = APIRouter()

COOKIE_NAME = "unefy_session"
SESSION_TTL = 60 * 60 * 24 * 7  # 7 days

# --- OAuth setup ---

oauth = OAuth()


def _ensure_google_registered(settings: Settings) -> None:
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=500,
            detail="Google OAuth is not configured: GOOGLE_CLIENT_ID is empty",
        )
    if "google" not in oauth._clients:
        oauth.register(
            name="google",
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"},
        )


# --- Session helpers ---


async def create_session(
    user_id: uuid.UUID,
    tenant_id: uuid.UUID | None = None,
    role: str | None = None,
) -> str:
    """Create a session in Redis and return the session token."""
    redis = get_redis()
    session_token = secrets.token_urlsafe(32)
    session_data = json.dumps(
        {
            "user_id": str(user_id),
            "tenant_id": str(tenant_id) if tenant_id else None,
            "role": role,
        }
    )
    await redis.set(f"session:{session_token}", session_data, ex=SESSION_TTL)
    return session_token


async def get_session_data(
    session_token: str,
) -> tuple[uuid.UUID, uuid.UUID | None, str | None] | None:
    """Resolve session token → (user_id, tenant_id | None, role | None)."""
    redis = get_redis()
    raw = await redis.get(f"session:{session_token}")
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    user_id = uuid.UUID(data["user_id"])
    tenant_id = uuid.UUID(data["tenant_id"]) if data.get("tenant_id") else None
    role = data.get("role")
    return user_id, tenant_id, role


def _set_session_cookie(
    response: RedirectResponse | Response,
    session_token: str,
    settings: Settings,
) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=session_token,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="lax",
        max_age=SESSION_TTL,
        path="/",
        domain=settings.COOKIE_DOMAIN,
    )


# --- Endpoints ---


@router.get(
    "/me",
    # High limit because /me is polled from the BFF on every page navigation.
    dependencies=[Depends(RateLimit(limit=300, window=60, scope="auth-me"))],
)
async def get_me(
    request: Request,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Return current user info. Supports both full sessions and onboarding sessions."""
    from app.dependencies import _resolve_auth

    auth = await _resolve_auth(request, session)

    if auth is None:
        return {"data": None}

    # Load user details from DB
    stmt = select(User).where(User.id == auth.user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        return {"data": None}

    # Load tenant name if user has a tenant
    tenant_name = None
    tenant_short_name = None
    if auth.tenant_id:
        stmt = select(Tenant).where(Tenant.id == auth.tenant_id)
        result = await session.execute(stmt)
        tenant = result.scalar_one_or_none()
        if tenant:
            tenant_name = tenant.name
            tenant_short_name = tenant.short_name

    return {
        "data": {
            "user": {
                "id": str(user.id),
                "name": user.name,
                "email": user.email,
                "image": user.image,
                "locale": user.locale,
            },
            "tenant_id": str(auth.tenant_id) if auth.tenant_id else None,
            "tenant_name": tenant_name,
            "tenant_short_name": tenant_short_name,
            "role": auth.role,
            "needs_onboarding": auth.tenant_id is None,
        }
    }


class UpdateLocaleRequest(BaseModel):
    locale: str = Field(min_length=2, max_length=5, pattern="^(de|en)$")


@router.patch("/me/locale")
async def update_locale(
    data: UpdateLocaleRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Update the current user's locale preference."""
    from app.dependencies import _resolve_auth

    auth = await _resolve_auth(request, session)
    if auth is None:
        from app.core.exceptions import ForbiddenError

        raise ForbiddenError("Not authenticated")

    stmt = select(User).where(User.id == auth.user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user:
        user.locale = data.locale
        await session.flush()

    return {"data": {"locale": data.locale}}


@router.get(
    "/oauth/google",
    dependencies=[Depends(RateLimit(limit=20, window=60, scope="oauth-start"))],
)
async def google_login(
    request: Request,
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> RedirectResponse:
    """Start Google OAuth flow — redirects user to Google."""
    _ensure_google_registered(settings)
    redirect_uri = f"{settings.BACKEND_URL}/api/v1/auth/oauth/google/callback"
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get(
    "/oauth/google/callback",
    dependencies=[Depends(RateLimit(limit=20, window=60, scope="oauth-callback"))],
)
async def google_callback(
    request: Request,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> RedirectResponse:
    """Handle Google OAuth callback — create/find user, issue session."""
    _ensure_google_registered(settings)
    token = await oauth.google.authorize_access_token(request)
    userinfo = token.get("userinfo")

    if not userinfo or not userinfo.get("email"):
        return RedirectResponse(url=f"{settings.WEB_APP_URL}/login?error=oauth_failed")

    google_id = userinfo["sub"]
    email = userinfo["email"]
    name = userinfo.get("name", email.split("@")[0])
    image = userinfo.get("picture")

    # Find or create user
    stmt = select(User).where(User.google_id == google_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    is_new_user = False

    if user is None:
        # Check if user exists by email (link accounts)
        stmt = select(User).where(User.email == email)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if user is None:
            user = User(
                email=email,
                name=name,
                image=image,
                email_verified=True,
                google_id=google_id,
            )
            session.add(user)
            await session.flush()
            is_new_user = True
            logger.info("user_created", user_id=str(user.id), email=email)
        else:
            user.google_id = google_id
            if image and not user.image:
                user.image = image
            await session.flush()
    else:
        if name and user.name != name:
            user.name = name
        if image:
            user.image = image
        await session.flush()

    # Check for existing tenant membership
    stmt = (
        select(TenantMembership)
        .where(TenantMembership.user_id == user.id)
        .where(TenantMembership.is_active.is_(True))
        .limit(1)
    )
    result = await session.execute(stmt)
    membership = result.scalar_one_or_none()

    if membership:
        # Existing user with tenant — create full session, go to dashboard
        session_token = await create_session(user.id, membership.tenant_id, membership.role)
        redirect_url = settings.WEB_APP_URL
    else:
        # New user or no tenant — create tenant-less session, go to onboarding
        session_token = await create_session(user.id)
        redirect_url = f"{settings.WEB_APP_URL}/onboarding"

    response = RedirectResponse(url=redirect_url, status_code=302)
    _set_session_cookie(response, session_token, settings)

    # Set locale cookie from user preference if available.
    # Not sensitive, but we still harden it — no JS access, HTTPS-only
    # outside dev, and lax SameSite to survive top-level navigation from
    # the OAuth redirect.
    if user.locale:
        response.set_cookie(
            key="locale",
            value=user.locale,
            max_age=60 * 60 * 24 * 365,
            path="/",
            httponly=True,
            secure=not settings.DEBUG,
            samesite="lax",
            domain=settings.COOKIE_DOMAIN,
        )

    logger.info("user_logged_in", user_id=str(user.id), method="google", new=is_new_user)
    return response


class CreateClubRequest(BaseModel):
    club_name: str = Field(min_length=2, max_length=255)


@router.post(
    "/onboarding/create-club",
    dependencies=[
        Depends(RateLimit(limit=5, window=3600, by="user", scope="create-club")),
    ],
)
async def create_club(
    data: CreateClubRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> JSONResponse:
    """Create a new club/tenant during onboarding."""
    from app.dependencies import _resolve_auth

    auth = await _resolve_auth(request, session)

    if auth is None:
        from app.core.exceptions import ForbiddenError

        raise ForbiddenError("Not authenticated")

    # Check user doesn't already have a tenant
    stmt = (
        select(TenantMembership)
        .where(TenantMembership.user_id == auth.user_id)
        .where(TenantMembership.is_active.is_(True))
    )
    result = await session.execute(stmt)
    if result.scalar_one_or_none():
        from app.core.exceptions import ConflictError

        raise ConflictError("User already has a club")

    # Seed member_statuses using the owner's locale so labels are sensible
    # in their language out of the box.
    from app.core.seeds import member_statuses_seed
    from app.models.user import User as UserModel

    user_stmt = select(UserModel).where(UserModel.id == auth.user_id)
    user_result = await session.execute(user_stmt)
    owner = user_result.scalar_one_or_none()
    owner_locale = owner.locale if owner else None

    # Create tenant
    tenant = Tenant(
        name=data.club_name.strip(),
        slug=f"club-{uuid.uuid4().hex[:8]}",
        member_statuses=member_statuses_seed(owner_locale),
    )
    session.add(tenant)
    await session.flush()

    # Create ownership
    membership = TenantMembership(
        user_id=auth.user_id,
        tenant_id=tenant.id,
        role="owner",
    )
    session.add(membership)
    await session.flush()

    # Rotate the session token on this privilege upgrade (user is now an
    # owner of a tenant). Old token is invalidated so a leaked pre-onboarding
    # cookie can't be used to access the new tenant.
    old_session_token = request.cookies.get(COOKIE_NAME)
    if old_session_token:
        redis = get_redis()
        await redis.delete(f"session:{old_session_token}")

    new_session_token = await create_session(auth.user_id, tenant_id=tenant.id, role="owner")

    logger.info(
        "club_created",
        user_id=str(auth.user_id),
        tenant_id=str(tenant.id),
        name=data.club_name,
    )

    response = JSONResponse(
        content={
            "data": {
                "tenant_id": str(tenant.id),
                "name": tenant.name,
                "slug": tenant.slug,
            }
        }
    )
    _set_session_cookie(response, new_session_token, settings)
    return response


@router.post(
    "/logout",
    dependencies=[Depends(RateLimit(limit=20, window=60, scope="logout"))],
)
async def logout(
    request: Request,
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> JSONResponse:
    """Invalidate session and clear cookie."""
    session_token = request.cookies.get(COOKIE_NAME)
    if session_token:
        redis = get_redis()
        await redis.delete(f"session:{session_token}")

    response = JSONResponse(content={"data": {"message": "Logged out"}})
    response.delete_cookie(COOKIE_NAME, path="/", domain=settings.COOKIE_DOMAIN)
    return response
