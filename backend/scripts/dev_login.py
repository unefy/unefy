"""Mint a web session for an existing user — local development only.

Web login currently runs through Google OAuth only; the magic-link endpoint the
login form posts to does not exist yet. This script fills that gap so local work
is not blocked on it.

Deliberately a script, not an HTTP endpoint: it hands out a session for an
arbitrary account, so the bar to reach it should be shell access to the backend
— the same bar as `create_superuser.py`. An endpoint would be reachable by
anything that could talk to the API if DEBUG were ever true in a deployment.

Refuses to run unless DEBUG is set.

Run inside the backend container:
    uv run python scripts/dev_login.py andreas@wdmr.de
    uv run python scripts/dev_login.py andreas@wdmr.de --tenant-slug testverein
"""

import argparse
import asyncio
import sys

from sqlalchemy import select

from app.api.v1.auth import COOKIE_NAME, SESSION_TTL, create_session
from app.config import get_settings
from app.database import async_session_factory
from app.models.tenant import Tenant
from app.models.user import TenantMembership, User
from app.redis import close_redis, init_redis


async def mint(email: str, tenant_slug: str | None) -> int:
    settings = get_settings()
    if not settings.DEBUG:
        print("Refusing to run: DEBUG is off. This is a local development tool.")
        return 1

    await init_redis()
    try:
        async with async_session_factory() as session:
            user = (
                await session.execute(select(User).where(User.email == email))
            ).scalar_one_or_none()
            if user is None:
                print(f"No user with email {email!r}.")
                return 1

            memberships = (
                (
                    await session.execute(
                        select(TenantMembership, Tenant)
                        .join(Tenant, Tenant.id == TenantMembership.tenant_id)
                        .where(TenantMembership.user_id == user.id)
                        .where(TenantMembership.is_active.is_(True))
                        .order_by(Tenant.name)
                    )
                )
                .tuples()
                .all()
            )

            chosen = None
            if tenant_slug:
                chosen = next((m for m in memberships if m[1].slug == tenant_slug), None)
                if chosen is None:
                    available = ", ".join(t.slug for _, t in memberships) or "none"
                    print(f"User has no active membership in {tenant_slug!r}.")
                    print(f"Available: {available}")
                    return 1
            elif memberships:
                chosen = memberships[0]

            membership, tenant = chosen if chosen else (None, None)
            token = await create_session(
                user_id=user.id,
                tenant_id=tenant.id if tenant else None,
                role=membership.role if membership else None,
            )

        web_url = settings.WEB_APP_URL.rstrip("/")
        print(f"\nUser:    {user.name} <{user.email}>")
        if tenant:
            print(f"Club:    {tenant.name} ({tenant.slug}), role {membership.role}")
            if len(memberships) > 1:
                others = ", ".join(t.slug for _, t in memberships if t.slug != tenant.slug)
                print(f"         other clubs: {others} — pass --tenant-slug to pick one")
        else:
            print("Club:    none — you will land on /onboarding")
        print(f"Expires: {SESSION_TTL // 3600}h\n")

        print("Paste this into the browser console on the app's origin, then reload:\n")
        print(f'  document.cookie = "{COOKIE_NAME}={token}; path=/"; location.href = "/"\n')
        print(f"App: {web_url}")
        print(f"Raw token: {token}\n")
        return 0
    finally:
        await close_redis()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("email")
    parser.add_argument(
        "--tenant-slug",
        default=None,
        help="Club to sign into, when the user belongs to several",
    )
    args = parser.parse_args()
    return asyncio.run(mint(args.email, args.tenant_slug))


if __name__ == "__main__":
    sys.exit(main())
