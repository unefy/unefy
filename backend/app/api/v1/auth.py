import json
import secrets
import uuid
from dataclasses import dataclass
from typing import Any

import structlog
from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import RedirectResponse, Response

from app.config import Settings, get_settings
from app.core.rate_limit import RateLimit
from app.database import get_db_session
from app.models.tenant import Tenant
from app.models.user import TenantMembership, User
from app.redis import get_redis
from app.services.club_access import ClubAccessService
from app.services.magic_link import (
    consume_token,
    issue_token,
    normalize_email,
    resolve_user,
    send_magic_link,
)

logger = structlog.get_logger()
router = APIRouter()

COOKIE_NAME = "unefy_session"
SESSION_TTL = 60 * 60 * 24 * 7  # 7 days

# Impersonation sessions expire far sooner than normal ones. A support session
# that outlives the support case is a standing backdoor into a customer's data.
IMPERSONATION_TTL = 60 * 60  # 1 hour

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
            client_kwargs={
                "scope": "openid email profile",
                "code_challenge_method": "S256",
            },
        )


# --- Session helpers ---


@dataclass(frozen=True)
class SessionData:
    """Decoded contents of a Redis-backed web session."""

    user_id: uuid.UUID
    tenant_id: uuid.UUID | None = None
    role: str | None = None

    # Set only while a platform admin is impersonating: the admin's own user id.
    # `user_id` stays the *impersonated* user, so every permission check keeps
    # working against the effective identity and cannot be widened by the flag.
    impersonator_id: uuid.UUID | None = None

    # The admin's original session token, so ending impersonation can hand the
    # cookie back instead of forcing a re-login.
    impersonator_session: str | None = None


async def create_session(
    user_id: uuid.UUID,
    tenant_id: uuid.UUID | None = None,
    role: str | None = None,
    impersonator_id: uuid.UUID | None = None,
    impersonator_session: str | None = None,
    ttl: int = SESSION_TTL,
) -> str:
    """Create a session in Redis and return the session token."""
    redis = get_redis()
    session_token = secrets.token_urlsafe(32)
    session_data = json.dumps(
        {
            "user_id": str(user_id),
            "tenant_id": str(tenant_id) if tenant_id else None,
            "role": role,
            "impersonator_id": str(impersonator_id) if impersonator_id else None,
            "impersonator_session": impersonator_session,
        }
    )
    await redis.set(f"session:{session_token}", session_data, ex=ttl)
    return session_token


async def get_session_data(session_token: str) -> SessionData | None:
    """Resolve a session token to its stored contents, or None if unknown."""
    redis = get_redis()
    raw = await redis.get(f"session:{session_token}")
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    try:
        user_id = uuid.UUID(data["user_id"])
    except (KeyError, TypeError, ValueError):
        return None
    tenant_id = uuid.UUID(data["tenant_id"]) if data.get("tenant_id") else None
    impersonator_id = uuid.UUID(data["impersonator_id"]) if data.get("impersonator_id") else None
    return SessionData(
        user_id=user_id,
        tenant_id=tenant_id,
        role=data.get("role"),
        impersonator_id=impersonator_id,
        impersonator_session=data.get("impersonator_session"),
    )


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
        tenant_stmt = select(Tenant).where(Tenant.id == auth.tenant_id)
        tenant_result = await session.execute(tenant_stmt)
        tenant = tenant_result.scalar_one_or_none()
        if tenant:
            tenant_name = tenant.name
            tenant_short_name = tenant.short_name

    # Surfaced so the web app can render a persistent impersonation banner.
    # Without it an admin could forget they are acting as someone else, which
    # is exactly how support sessions turn into accidental data changes.
    impersonator: dict[str, Any] | None = None
    if auth.impersonator_id is not None:
        result = await session.execute(select(User).where(User.id == auth.impersonator_id))
        admin_user = result.scalar_one_or_none()
        if admin_user is not None:
            impersonator = {
                "id": str(admin_user.id),
                "name": admin_user.name,
                "email": admin_user.email,
            }

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
            "is_superuser": user.is_superuser,
            "impersonator": impersonator,
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


# --- Magic link ---


class MagicLinkRequest(BaseModel):
    email: EmailStr


@router.post(
    "/magic-link/request",
    dependencies=[
        # Two limits on purpose: per-IP stops bulk enumeration, and the shared
        # scope is what an attacker would otherwise use to mail-bomb one
        # address from many IPs.
        Depends(RateLimit(limit=5, window=300, scope="magic-link-request")),
    ],
)
async def request_magic_link(
    data: MagicLinkRequest,
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> dict[str, Any]:
    """Mail a one-time sign-in link.

    Always answers 200, whether or not an account exists. Anything else would
    turn this endpoint into an account-existence oracle. For the same reason a
    link is issued for unknown addresses too — the account is created when the
    link is actually opened, which proves the mailbox belongs to the requester.
    """
    email = normalize_email(data.email)
    token = await issue_token(email, settings)
    await send_magic_link(email, token, settings)

    logger.info("magic_link_requested")
    return {"data": {"sent": True}}


@router.get(
    "/magic-link/verify",
    dependencies=[
        Depends(RateLimit(limit=10, window=300, scope="magic-link-verify")),
    ],
)
async def verify_magic_link(
    token: str,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> RedirectResponse:
    """Redeem a sign-in link and start a session.

    Redirects rather than returning JSON: the user arrives here from their mail
    client, so the response has to be something a browser can land on.
    """
    email = await consume_token(token)
    if email is None:
        logger.info("magic_link_invalid")
        return RedirectResponse(
            url=f"{settings.WEB_APP_URL}/login?error=link_invalid", status_code=302
        )

    user = await resolve_user(session, email)

    membership = (
        await session.execute(
            select(TenantMembership)
            .where(TenantMembership.user_id == user.id)
            .where(TenantMembership.is_active.is_(True))
            .limit(1)
        )
    ).scalar_one_or_none()

    if membership:
        session_token = await create_session(user.id, membership.tenant_id, membership.role)
        redirect_url = settings.WEB_APP_URL
    else:
        session_token = await create_session(user.id)
        redirect_url = f"{settings.WEB_APP_URL}/onboarding"

    response = RedirectResponse(url=redirect_url, status_code=302)
    _set_session_cookie(response, session_token, settings)

    logger.info("user_logged_in", user_id=str(user.id), method="magic_link")
    return response


@router.get(
    "/invitation/accept",
    dependencies=[
        Depends(RateLimit(limit=10, window=300, scope="invitation-accept")),
    ],
)
async def accept_invitation(
    token: str,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> RedirectResponse:
    """Join a club through an invitation link and start a session.

    Deliberately unauthenticated: the invitee usually has no account yet, and
    the token is what proves they were invited.
    """
    result = await ClubAccessService(session).accept_invitation(token)

    if result is None:
        return RedirectResponse(
            url=f"{settings.WEB_APP_URL}/login?error=invitation_invalid",
            status_code=302,
        )

    user, membership = result
    session_token = await create_session(user.id, membership.tenant_id, membership.role)

    response = RedirectResponse(url=settings.WEB_APP_URL, status_code=302)
    _set_session_cookie(response, session_token, settings)

    logger.info(
        "user_logged_in",
        user_id=str(user.id),
        method="invitation",
        tenant_id=str(membership.tenant_id),
    )
    return response


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
    # authlib ships no stubs, so this is Any; the call does return a redirect.
    redirect: RedirectResponse = await oauth.google.authorize_redirect(request, redirect_uri)
    return redirect


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
        # Linking a Google identity to an existing account by email is only
        # safe when Google attests the email is verified — otherwise an
        # attacker with an unverified Google alias could take over the
        # account with that email.
        if userinfo.get("email_verified") is not True:
            logger.warning("oauth_unverified_email", google_sub=google_id)
            return RedirectResponse(url=f"{settings.WEB_APP_URL}/login?error=oauth_failed")

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
            logger.info("user_created", user_id=str(user.id))
        else:
            user.google_id = google_id
            if image and not user.image:
                user.image = image
            await session.flush()
            logger.info("account_linked", user_id=str(user.id), method="google")
    else:
        if name and user.name != name:
            user.name = name
        if image:
            user.image = image
        await session.flush()

    # Check for existing tenant membership
    membership_stmt = (
        select(TenantMembership)
        .where(TenantMembership.user_id == user.id)
        .where(TenantMembership.is_active.is_(True))
        .limit(1)
    )
    membership_result = await session.execute(membership_stmt)
    membership = membership_result.scalar_one_or_none()

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


@router.get(
    "/tenants",
    dependencies=[Depends(RateLimit(limit=60, window=60, scope="auth-tenants"))],
)
async def list_my_tenants(
    request: Request,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """List all active tenant memberships of the current user."""
    from app.core.exceptions import ForbiddenError
    from app.dependencies import _resolve_auth

    auth = await _resolve_auth(request, session)
    if auth is None:
        raise ForbiddenError("Not authenticated")

    stmt = (
        select(TenantMembership, Tenant)
        .join(Tenant, Tenant.id == TenantMembership.tenant_id)
        .where(TenantMembership.user_id == auth.user_id)
        .where(TenantMembership.is_active.is_(True))
        .where(Tenant.is_active.is_(True))
        .order_by(Tenant.name)
    )
    result = await session.execute(stmt)

    return {
        "data": [
            {
                "tenant_id": str(tenant.id),
                "name": tenant.name,
                "short_name": tenant.short_name,
                "role": membership.role,
                "is_current": tenant.id == auth.tenant_id,
            }
            for membership, tenant in result.all()
        ]
    }


class SwitchTenantRequest(BaseModel):
    tenant_id: uuid.UUID


@router.post(
    "/switch-tenant",
    dependencies=[Depends(RateLimit(limit=20, window=60, scope="switch-tenant"))],
)
async def switch_tenant(
    data: SwitchTenantRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> JSONResponse:
    """Switch the active tenant of a web session. Rotates the session token."""
    from app.core.exceptions import ForbiddenError
    from app.dependencies import _resolve_auth

    auth = await _resolve_auth(request, session)
    if auth is None:
        raise ForbiddenError("Not authenticated")

    # Switching rotates the session cookie, so it only works for cookie-based
    # (web) sessions — mobile clients get a tenant-scoped JWT at login instead.
    old_session_token = request.cookies.get(COOKIE_NAME)
    if not old_session_token:
        raise ForbiddenError("Tenant switching requires a session cookie")

    stmt = (
        select(TenantMembership, Tenant)
        .join(Tenant, Tenant.id == TenantMembership.tenant_id)
        .where(TenantMembership.user_id == auth.user_id)
        .where(TenantMembership.tenant_id == data.tenant_id)
        .where(TenantMembership.is_active.is_(True))
        .where(Tenant.is_active.is_(True))
    )
    result = await session.execute(stmt)
    row = result.one_or_none()
    if row is None:
        raise ForbiddenError("No active membership for this tenant")

    membership, tenant = row

    # Rotate the session token: the tenant context (and possibly the role)
    # changes, so the old token must not remain valid.
    redis = get_redis()
    await redis.delete(f"session:{old_session_token}")
    new_session_token = await create_session(
        auth.user_id, tenant_id=tenant.id, role=membership.role
    )

    logger.info(
        "tenant_switched",
        user_id=str(auth.user_id),
        tenant_id=str(tenant.id),
    )

    response = JSONResponse(
        content={
            "data": {
                "tenant_id": str(tenant.id),
                "name": tenant.name,
                "short_name": tenant.short_name,
                "role": membership.role,
            }
        }
    )
    _set_session_cookie(response, new_session_token, settings)
    return response


class ClubDivisionInput(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    sport_key: str = Field(min_length=2, max_length=50)


class CreateClubRequest(BaseModel):
    club_name: str = Field(min_length=2, max_length=255)

    # Whether the club is organised in divisions (Sparten). When false the
    # single division below is created but never surfaced in the UI.
    has_divisions: bool = False

    divisions: list[ClubDivisionInput] = Field(min_length=1, max_length=20)


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
    """Create a new club during onboarding.

    A user may own several clubs — the previous "one club per user" block was
    removed when multi-club support landed. Abuse is bounded by the rate limit
    on this endpoint rather than by a hard cap.
    """
    from app.core.exceptions import ForbiddenError
    from app.dependencies import _resolve_auth
    from app.services.onboarding import OnboardingService

    auth = await _resolve_auth(request, session)
    if auth is None:
        raise ForbiddenError("Not authenticated")

    tenant = await OnboardingService(session).create_club(
        user_id=auth.user_id,
        club_name=data.club_name,
        divisions=[(d.name, d.sport_key) for d in data.divisions],
        has_divisions=data.has_divisions,
    )

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
