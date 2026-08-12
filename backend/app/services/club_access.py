"""Who may sign in to a club, and with which role.

Every method is tenant-scoped by argument, never by ambient state — this
service runs behind `require_role`, which authorises the *caller*, and nothing
here may be reachable with a tenant id the caller did not prove access to.
"""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.integrations.email import EmailError, send_email
from app.models.invitation import Invitation
from app.models.member import Member
from app.models.tenant import Tenant
from app.models.user import TenantMembership, User

logger = structlog.get_logger()

# Mirrors the RBAC roles in the auth design. `owner` is included so ownership
# can be handed over, which a club needs when the founder leaves.
ASSIGNABLE_ROLES = ("owner", "admin", "board", "member")

INVITATION_TTL = timedelta(days=7)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _normalize(email: str) -> str:
    return email.strip().lower()


class ClubAccessService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- Reading ---

    async def list_members(self, tenant_id: uuid.UUID) -> list[dict[str, Any]]:
        """Accounts that can sign in to this club.

        `member_id` names the member record the account is linked to, so the
        UI can tell which accounts are still free to link and which member a
        login belongs to — without a second request per row.
        """
        rows = await self.session.execute(
            select(TenantMembership, User, Member.id)
            .join(User, User.id == TenantMembership.user_id)
            .outerjoin(
                Member,
                (Member.user_id == User.id)
                & (Member.tenant_id == tenant_id)
                & (Member.deleted_at.is_(None)),
            )
            .where(TenantMembership.tenant_id == tenant_id)
            .order_by(User.name.asc())
        )
        return [
            {
                "user_id": user.id,
                "name": user.name,
                "email": user.email,
                "image": user.image,
                "role": membership.role,
                "is_active": membership.is_active,
                "joined_at": membership.joined_at,
                "member_id": member_id,
            }
            for membership, user, member_id in rows.all()
        ]

    async def list_invitations(self, tenant_id: uuid.UUID) -> list[dict[str, Any]]:
        """Invitations that are still open — neither accepted nor withdrawn."""
        rows = await self.session.execute(
            select(Invitation)
            .where(Invitation.tenant_id == tenant_id)
            .where(Invitation.accepted_at.is_(None))
            .where(Invitation.revoked_at.is_(None))
            .order_by(Invitation.created_at.desc())
        )
        now = datetime.now(UTC)
        return [
            {
                "id": inv.id,
                "email": inv.email,
                "role": inv.role,
                "expires_at": inv.expires_at,
                "created_at": inv.created_at,
                "is_expired": inv.expires_at < now,
                "member_id": inv.member_id,
            }
            for inv in rows.scalars().all()
        ]

    # --- Guards ---

    def _validate_role(self, role: str) -> None:
        if role not in ASSIGNABLE_ROLES:
            raise ValidationError(f"Unknown role: {role}")

    async def _count_active_owners(self, tenant_id: uuid.UUID) -> int:
        return (
            await self.session.execute(
                select(func.count(TenantMembership.id))
                .where(TenantMembership.tenant_id == tenant_id)
                .where(TenantMembership.role == "owner")
                .where(TenantMembership.is_active.is_(True))
            )
        ).scalar_one()

    async def _assert_not_last_owner(
        self, tenant_id: uuid.UUID, membership: TenantMembership
    ) -> None:
        """Refuse changes that would leave the club without an active owner.

        Without this a club can be locked out of its own administration, and
        recovering it needs a platform admin — exactly the situation
        self-hosting is supposed to avoid.
        """
        if membership.role != "owner" or not membership.is_active:
            return
        if await self._count_active_owners(tenant_id) <= 1:
            raise ConflictError("A club must keep at least one active owner")

    # --- Membership changes ---

    async def _get_membership(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> TenantMembership:
        membership = (
            await self.session.execute(
                select(TenantMembership)
                .where(TenantMembership.tenant_id == tenant_id)
                .where(TenantMembership.user_id == user_id)
            )
        ).scalar_one_or_none()
        if membership is None:
            raise NotFoundError("Membership not found")
        return membership

    async def set_role(self, tenant_id: uuid.UUID, user_id: uuid.UUID, role: str) -> dict[str, Any]:
        self._validate_role(role)
        membership = await self._get_membership(tenant_id, user_id)

        if membership.role != role:
            await self._assert_not_last_owner(tenant_id, membership)

        membership.role = role
        await self.session.flush()
        logger.info(
            "club_role_changed",
            tenant_id=str(tenant_id),
            user_id=str(user_id),
            role=role,
        )
        return {"user_id": user_id, "role": role, "is_active": membership.is_active}

    async def set_active(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID, is_active: bool
    ) -> dict[str, Any]:
        """Enable or revoke an account's access without deleting history."""
        membership = await self._get_membership(tenant_id, user_id)

        if not is_active:
            await self._assert_not_last_owner(tenant_id, membership)

        membership.is_active = is_active
        await self.session.flush()
        logger.info(
            "club_access_changed",
            tenant_id=str(tenant_id),
            user_id=str(user_id),
            is_active=is_active,
        )
        return {"user_id": user_id, "role": membership.role, "is_active": is_active}

    async def _get_member(self, tenant_id: uuid.UUID, member_id: uuid.UUID) -> Member:
        member = (
            await self.session.execute(
                select(Member)
                .where(Member.id == member_id)
                # Scoped by tenant so a member id from another club is unusable.
                .where(Member.tenant_id == tenant_id)
                .where(Member.deleted_at.is_(None))
            )
        ).scalar_one_or_none()
        if member is None:
            raise NotFoundError("Member not found")
        return member

    # --- Linking accounts to member records ---

    async def link_member(
        self, tenant_id: uuid.UUID, member_id: uuid.UUID, user_id: uuid.UUID
    ) -> dict[str, Any]:
        """Bind an existing club account to a member record.

        The invitation flow covers people without an account; this covers the
        ones who already have one — above all the founder, who is owner before
        the register is even imported and whom no invitation can ever reach
        (`invite` refuses addresses that already have access, by design).

        Linking hands the account the member's self-service data (dues,
        attendance), so it stays with owner/admin — same bar as inviting.
        """
        member = await self._get_member(tenant_id, member_id)
        if member.user_id is not None:
            raise ConflictError("This member is already linked to an account")

        # The account must already belong to this club: linking must never be
        # a way to smuggle in access — that is what invitations are for.
        await self._get_membership(tenant_id, user_id)

        already_linked = (
            await self.session.execute(
                select(Member.id)
                .where(Member.tenant_id == tenant_id)
                .where(Member.user_id == user_id)
                .where(Member.deleted_at.is_(None))
            )
        ).scalar_one_or_none()
        if already_linked is not None:
            raise ConflictError("This account is already linked to another member")

        member.user_id = user_id
        await self.session.flush()
        logger.info(
            "club_member_linked",
            tenant_id=str(tenant_id),
            member_id=str(member_id),
            user_id=str(user_id),
        )
        return {"member_id": member_id, "user_id": user_id}

    async def unlink_member(self, tenant_id: uuid.UUID, member_id: uuid.UUID) -> None:
        """Undo a link — the escape hatch for binding the wrong person."""
        member = await self._get_member(tenant_id, member_id)
        if member.user_id is None:
            raise ConflictError("This member is not linked to an account")
        unlinked_user = member.user_id
        member.user_id = None
        await self.session.flush()
        logger.info(
            "club_member_unlinked",
            tenant_id=str(tenant_id),
            member_id=str(member_id),
            user_id=str(unlinked_user),
        )

    # --- Invitations ---

    async def invite(
        self,
        *,
        tenant_id: uuid.UUID,
        email: str | None,
        role: str,
        invited_by: uuid.UUID,
        settings: Settings,
        member_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        self._validate_role(role)

        member = None
        if member_id is not None:
            member = await self._get_member(tenant_id, member_id)
            # The address is taken from the member record, never from the
            # request. Accepting a client-supplied address here would let an
            # invitation bind a stranger's account to this member — and with it
            # to their dues and personal data in self-service.
            if not member.email:
                raise ValidationError("This member has no email address")
            normalized = _normalize(member.email)
            if member.user_id is not None:
                raise ConflictError("This member already has an account")
        else:
            if not email:
                raise ValidationError("An email address is required")
            normalized = _normalize(email)

        # Someone who can already sign in does not need an invitation, and
        # sending one would imply their access is in question.
        existing = (
            await self.session.execute(
                select(TenantMembership)
                .join(User, User.id == TenantMembership.user_id)
                .where(TenantMembership.tenant_id == tenant_id)
                .where(User.email == normalized)
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise ConflictError("This address already has access to the club")

        open_invite = (
            await self.session.execute(
                select(Invitation)
                .where(Invitation.tenant_id == tenant_id)
                .where(Invitation.email == normalized)
                .where(Invitation.accepted_at.is_(None))
                .where(Invitation.revoked_at.is_(None))
                .where(Invitation.expires_at > datetime.now(UTC))
            )
        ).scalar_one_or_none()
        if open_invite is not None:
            raise ConflictError("An invitation for this address is already open")

        token = secrets.token_urlsafe(32)
        invitation = Invitation(
            tenant_id=tenant_id,
            email=normalized,
            role=role,
            token_hash=_hash(token),
            invited_by=invited_by,
            member_id=member_id,
            expires_at=datetime.now(UTC) + INVITATION_TTL,
        )
        self.session.add(invitation)
        await self.session.flush()

        tenant = (
            await self.session.execute(select(Tenant).where(Tenant.id == tenant_id))
        ).scalar_one()
        accept_url = f"{settings.BACKEND_URL}/api/v1/auth/invitation/accept?token={token}"
        await self._send_invitation(normalized, accept_url, tenant.name, settings)

        logger.info(
            "club_invitation_created",
            tenant_id=str(tenant_id),
            invitation_id=str(invitation.id),
            role=role,
        )
        return {
            "id": invitation.id,
            "email": invitation.email,
            "role": invitation.role,
            "expires_at": invitation.expires_at,
            "created_at": invitation.created_at,
            "is_expired": False,
            "member_id": invitation.member_id,
            # The one and only time the plaintext link leaves the backend: the
            # inviter may hand it over directly (clubs without working mail).
            # Only the hash is stored, so it cannot be shown again later.
            "accept_url": accept_url,
        }

    async def _send_invitation(
        self, email: str, link: str, club_name: str, settings: Settings
    ) -> None:
        try:
            await send_email(
                # Not `auth`: an invitation arrives unannounced, and while a
                # test system is holding mail back it must be held back too.
                category="member",
                to=email,
                subject=f"Einladung zu {club_name} bei unefy",
                body=(
                    "Hallo,\n\n"
                    f"Sie wurden eingeladen, {club_name} bei unefy beizutreten.\n\n"
                    "Mit diesem Link nehmen Sie die Einladung an:\n\n"
                    f"{link}\n\n"
                    f"Der Link ist {INVITATION_TTL.days} Tage gültig.\n\n"
                    "Wenn Sie damit nichts anfangen können, ignorieren Sie diese "
                    "E-Mail — ohne den Link passiert nichts.\n"
                ),
                settings=settings,
            )
        except EmailError:
            # The invitation row stays: an administrator can revoke and reissue
            # it. Failing the request would leave a token nobody can reach.
            logger.error("invitation_delivery_failed", club=club_name)

    async def revoke_invitation(self, tenant_id: uuid.UUID, invitation_id: uuid.UUID) -> None:
        invitation = (
            await self.session.execute(
                select(Invitation)
                .where(Invitation.id == invitation_id)
                # Scoped by tenant so an id from another club cannot be revoked.
                .where(Invitation.tenant_id == tenant_id)
            )
        ).scalar_one_or_none()
        if invitation is None:
            raise NotFoundError("Invitation not found")
        if invitation.accepted_at is not None:
            raise ConflictError("This invitation has already been accepted")

        invitation.revoked_at = datetime.now(UTC)
        await self.session.flush()
        logger.info(
            "club_invitation_revoked",
            tenant_id=str(tenant_id),
            invitation_id=str(invitation_id),
        )

    async def accept_invitation(self, token: str) -> tuple[User, TenantMembership] | None:
        """Redeem an invitation, creating the account on first use.

        Returns None for anything unusable — unknown, expired, withdrawn or
        already accepted — so the caller cannot distinguish the cases and use
        them to probe for valid tokens.
        """
        invitation = (
            await self.session.execute(
                select(Invitation).where(Invitation.token_hash == _hash(token))
            )
        ).scalar_one_or_none()

        if (
            invitation is None
            or invitation.accepted_at is not None
            or invitation.revoked_at is not None
            or invitation.expires_at < datetime.now(UTC)
        ):
            return None

        user = (
            await self.session.execute(select(User).where(User.email == invitation.email))
        ).scalar_one_or_none()

        if user is None:
            # Opening the link proves control of the mailbox it was sent to.
            user = User(email=invitation.email, name=invitation.email, email_verified=True)
            self.session.add(user)
            await self.session.flush()

        membership = (
            await self.session.execute(
                select(TenantMembership)
                .where(TenantMembership.tenant_id == invitation.tenant_id)
                .where(TenantMembership.user_id == user.id)
            )
        ).scalar_one_or_none()

        if membership is None:
            membership = TenantMembership(
                user_id=user.id,
                tenant_id=invitation.tenant_id,
                role=invitation.role,
                is_active=True,
            )
            self.session.add(membership)
        else:
            # Re-invited after being deactivated: restore access at the role
            # the invitation offers.
            membership.is_active = True
            membership.role = invitation.role

        # Bind the member record to the new account, so self-service shows the
        # person their own data rather than an empty profile.
        if invitation.member_id is not None:
            member = (
                await self.session.execute(
                    select(Member)
                    .where(Member.id == invitation.member_id)
                    .where(Member.tenant_id == invitation.tenant_id)
                )
            ).scalar_one_or_none()
            if member is not None and member.user_id is None:
                member.user_id = user.id

        invitation.accepted_at = datetime.now(UTC)
        await self.session.flush()

        logger.info(
            "club_invitation_accepted",
            tenant_id=str(invitation.tenant_id),
            user_id=str(user.id),
            role=invitation.role,
        )
        return user, membership
