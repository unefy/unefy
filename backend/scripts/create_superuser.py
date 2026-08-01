"""Grant, revoke and list platform administrators.

A platform admin operates across all tenants and maintains global master data,
so the flag is deliberately not settable through any HTTP endpoint — there is
no tenant-scoped role that could imply it. This script is the only way in, and
it needs shell access to the backend to run.

Run inside the backend container:
    uv run python scripts/create_superuser.py grant andreas@wdmr.de
    uv run python scripts/create_superuser.py revoke andreas@wdmr.de
    uv run python scripts/create_superuser.py list
"""

import argparse
import asyncio
import sys
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.user import User


async def _find_user(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def grant(email: str, name: str | None, create_missing: bool) -> int:
    async with async_session_factory() as session:
        user = await _find_user(session, email)

        if user is None:
            if not create_missing:
                print(f"No user with email {email!r}.")
                print("Pass --create to create the account, or have them sign in once first.")
                return 1
            user = User(
                id=uuid.uuid4(),
                email=email,
                name=name or email.split("@")[0],
                # Sign-in is passwordless, so the account is usable immediately:
                # the magic link goes to this address and proves ownership.
                email_verified=False,
                is_superuser=True,
            )
            session.add(user)
            await session.commit()
            print(f"Created {email} as platform admin.")
            return 0

        if user.is_superuser:
            print(f"{email} is already a platform admin.")
            return 0

        user.is_superuser = True
        await session.commit()
        print(f"{email} is now a platform admin.")
        return 0


async def revoke(email: str) -> int:
    async with async_session_factory() as session:
        user = await _find_user(session, email)
        if user is None:
            print(f"No user with email {email!r}.")
            return 1
        if not user.is_superuser:
            print(f"{email} is not a platform admin.")
            return 0

        # Refuse to remove the last one: without a platform admin nobody can
        # reach the admin area again, and there is no HTTP path back in.
        remaining = await session.execute(
            select(User).where(User.is_superuser.is_(True)).where(User.id != user.id)
        )
        if remaining.scalars().first() is None:
            print(f"Refusing to revoke {email} — it is the only platform admin left.")
            print("Grant another one first.")
            return 1

        user.is_superuser = False
        await session.commit()
        print(f"{email} is no longer a platform admin.")
        return 0


async def list_admins() -> int:
    async with async_session_factory() as session:
        result = await session.execute(
            select(User).where(User.is_superuser.is_(True)).order_by(User.email)
        )
        admins = list(result.scalars().all())

    if not admins:
        print("No platform admins yet.")
        print("Create one with: create_superuser.py grant <email> --create")
        return 0

    print(f"{len(admins)} platform admin(s):")
    for admin in admins:
        print(f"  {admin.email}  ({admin.name})")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    grant_parser = sub.add_parser("grant", help="Make a user a platform admin")
    grant_parser.add_argument("email")
    grant_parser.add_argument("--name", default=None, help="Display name for a new account")
    grant_parser.add_argument(
        "--create",
        action="store_true",
        help="Create the account if no user with that email exists",
    )

    revoke_parser = sub.add_parser("revoke", help="Remove platform admin rights")
    revoke_parser.add_argument("email")

    sub.add_parser("list", help="List all platform admins")

    args = parser.parse_args()

    if args.command == "grant":
        return asyncio.run(grant(args.email, args.name, args.create))
    if args.command == "revoke":
        return asyncio.run(revoke(args.email))
    return asyncio.run(list_admins())


if __name__ == "__main__":
    sys.exit(main())
