import uuid
from typing import Any

import structlog
from fastapi import Request
from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.dependencies import AuthContext
from app.models.audit import AdminAuditLog
from app.models.member import Member
from app.models.tenant import Tenant
from app.models.user import TenantMembership, User
from app.schemas.admin import ImpersonateRequest
from app.services.audit import record_admin_action

logger = structlog.get_logger()


class AdminService:
    """Platform-admin operations that deliberately span all tenants.

    Every method here runs outside tenant isolation, so the guard on the route
    (`require_platform_admin`) is the only thing standing between these queries
    and every club's data. Nothing in this class may be reachable from a
    tenant-scoped router.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- Clubs ---

    async def list_tenants(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        search: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        member_count = (
            select(func.count(Member.id))
            .where(Member.tenant_id == Tenant.id)
            .where(Member.deleted_at.is_(None))
            .correlate(Tenant)
            .scalar_subquery()
        )
        user_count = (
            select(func.count(TenantMembership.id))
            .where(TenantMembership.tenant_id == Tenant.id)
            .where(TenantMembership.is_active.is_(True))
            .correlate(Tenant)
            .scalar_subquery()
        )

        stmt = select(
            Tenant,
            member_count.label("member_count"),
            user_count.label("user_count"),
        )
        count_stmt = select(func.count(Tenant.id))

        if search:
            stmt, count_stmt = self._apply_search(
                stmt,
                count_stmt,
                search,
                (Tenant.name, Tenant.short_name, Tenant.slug, Tenant.city),
            )

        total = (await self.session.execute(count_stmt)).scalar_one()
        rows = await self.session.execute(
            stmt.order_by(Tenant.name.asc()).offset(offset).limit(limit)
        )

        return [
            {
                **{
                    field: getattr(tenant, field)
                    for field in (
                        "id",
                        "name",
                        "short_name",
                        "slug",
                        "city",
                        "is_active",
                        "created_at",
                    )
                },
                "member_count": members,
                "user_count": users,
            }
            for tenant, members, users in rows.all()
        ], total

    async def get_tenant(self, tenant_id: uuid.UUID) -> dict[str, Any]:
        """Fetch a single club with the same counts the list shows."""
        tenant = (
            await self.session.execute(select(Tenant).where(Tenant.id == tenant_id))
        ).scalar_one_or_none()
        if tenant is None:
            raise NotFoundError("Tenant not found")

        member_count = (
            await self.session.execute(
                select(func.count(Member.id))
                .where(Member.tenant_id == tenant_id)
                .where(Member.deleted_at.is_(None))
            )
        ).scalar_one()
        user_count = (
            await self.session.execute(
                select(func.count(TenantMembership.id))
                .where(TenantMembership.tenant_id == tenant_id)
                .where(TenantMembership.is_active.is_(True))
            )
        ).scalar_one()

        return {
            **{
                field: getattr(tenant, field)
                for field in (
                    "id",
                    "name",
                    "short_name",
                    "slug",
                    "city",
                    "zip_code",
                    "street",
                    "country",
                    "email",
                    "phone",
                    "website",
                    "founded_at",
                    "is_active",
                    "created_at",
                )
            },
            "member_count": member_count,
            "user_count": user_count,
        }

    async def list_tenant_users(self, tenant_id: uuid.UUID) -> list[dict[str, Any]]:
        """Login accounts attached to a club, with their role."""
        result = await self.session.execute(
            select(TenantMembership, User)
            .join(User, User.id == TenantMembership.user_id)
            .where(TenantMembership.tenant_id == tenant_id)
            .order_by(User.name.asc())
        )
        return [
            {
                "user_id": user.id,
                "name": user.name,
                "email": user.email,
                "role": membership.role,
                "is_active": membership.is_active,
            }
            for membership, user in result.all()
        ]

    async def list_tenant_members(self, tenant_id: uuid.UUID) -> list[dict[str, Any]]:
        """Club members as seen by a platform admin.

        Deliberately narrow: banking details (IBAN, BIC, SEPA mandate), address,
        birthday and notes stay out. Platform support needs to see that members
        exist and in what state — not a club's personal and financial records.
        """
        result = await self.session.execute(
            select(Member)
            .where(Member.tenant_id == tenant_id)
            .where(Member.deleted_at.is_(None))
            .order_by(Member.last_name.asc(), Member.first_name.asc())
        )
        return [
            {
                "id": member.id,
                "member_number": member.member_number,
                "first_name": member.first_name,
                "last_name": member.last_name,
                "status": member.status,
                "category": member.category,
                "joined_at": member.joined_at,
                "left_at": member.left_at,
                "has_account": member.user_id is not None,
            }
            for member in result.scalars().all()
        ]

    # --- Users ---

    async def list_users(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        search: str | None = None,
    ) -> tuple[list[User], int]:
        stmt = select(User)
        count_stmt = select(func.count(User.id))

        if search:
            stmt, count_stmt = self._apply_search(stmt, count_stmt, search, (User.name, User.email))

        total = (await self.session.execute(count_stmt)).scalar_one()
        result = await self.session.execute(
            stmt.order_by(User.name.asc()).offset(offset).limit(limit)
        )
        return list(result.scalars().all()), total

    async def get_user(self, user_id: uuid.UUID) -> User:
        user = (
            await self.session.execute(select(User).where(User.id == user_id))
        ).scalar_one_or_none()
        if user is None:
            raise NotFoundError("User not found")
        return user

    async def list_user_memberships(self, user_id: uuid.UUID) -> list[dict[str, Any]]:
        result = await self.session.execute(
            select(TenantMembership, Tenant.name)
            .join(Tenant, Tenant.id == TenantMembership.tenant_id)
            .where(TenantMembership.user_id == user_id)
            .order_by(Tenant.name.asc())
        )
        return [
            {
                "tenant_id": membership.tenant_id,
                "tenant_name": tenant_name,
                "role": membership.role,
                "is_active": membership.is_active,
            }
            for membership, tenant_name in result.all()
        ]

    # --- Impersonation ---

    async def start_impersonation(
        self,
        auth: AuthContext,
        payload: ImpersonateRequest,
        current_session_token: str,
        request: Request,
    ) -> tuple[str, dict[str, Any], int]:
        """Open an impersonation session for `payload.user_id`.

        Returns `(session_token, response_body, ttl)`. The admin's own session
        is left intact in Redis so that ending impersonation can restore it.
        """
        from app.api.v1.auth import IMPERSONATION_TTL, create_session

        target = (
            await self.session.execute(select(User).where(User.id == payload.user_id))
        ).scalar_one_or_none()
        if target is None:
            raise NotFoundError("User not found")

        if target.id == auth.user_id:
            raise ValidationError("Cannot impersonate yourself")

        # A platform admin must not be able to borrow another admin's identity:
        # it would launder one admin's actions into another's name and defeat
        # the audit trail this whole feature depends on.
        if target.is_superuser:
            logger.warning(
                "impersonation_denied_superuser_target",
                actor=str(auth.user_id),
                target=str(target.id),
            )
            raise ForbiddenError("Cannot impersonate another platform administrator")

        tenant: Tenant | None = None
        role: str | None = None

        memberships = (
            (
                await self.session.execute(
                    select(TenantMembership)
                    .where(TenantMembership.user_id == target.id)
                    .where(TenantMembership.is_active.is_(True))
                )
            )
            .scalars()
            .all()
        )

        if payload.tenant_id is not None:
            membership = next((m for m in memberships if m.tenant_id == payload.tenant_id), None)
            if membership is None:
                raise NotFoundError("User has no active membership in that club")
            tenant = (
                await self.session.execute(select(Tenant).where(Tenant.id == membership.tenant_id))
            ).scalar_one_or_none()
            if tenant is None or not tenant.is_active:
                raise ConflictError("Club is not active")
            role = membership.role
        elif memberships:
            # Ambiguous on purpose: entering "some" club silently would make the
            # audit entry misleading about what the admin actually saw.
            raise ValidationError("tenant_id is required — user belongs to a club")

        token = await create_session(
            user_id=target.id,
            tenant_id=tenant.id if tenant else None,
            role=role,
            impersonator_id=auth.user_id,
            impersonator_session=current_session_token,
            ttl=IMPERSONATION_TTL,
        )

        await record_admin_action(
            self.session,
            auth,
            "impersonation.start",
            request=request,
            target_type="user",
            target_id=target.id,
            tenant_id=tenant.id if tenant else None,
            payload={
                "reason": payload.reason,
                "target_email": target.email,
                "role": role,
            },
        )
        logger.info(
            "impersonation_started",
            actor=str(auth.user_id),
            target=str(target.id),
            tenant=str(tenant.id) if tenant else None,
        )

        return (
            token,
            {
                "user_id": target.id,
                "user_email": target.email,
                "tenant_id": tenant.id if tenant else None,
                "tenant_name": tenant.name if tenant else None,
                "role": role,
                "expires_in": IMPERSONATION_TTL,
            },
            IMPERSONATION_TTL,
        )

    async def stop_impersonation(
        self,
        auth: AuthContext,
        current_session_token: str,
        request: Request,
    ) -> str | None:
        """End impersonation and return the admin's original session token.

        Returns None when the original session has expired in the meantime —
        the caller then clears the cookie and the admin signs in again. The
        impersonation session is destroyed either way.
        """
        from app.api.v1.auth import get_session_data
        from app.redis import get_redis

        data = await get_session_data(current_session_token)
        if data is None or data.impersonator_id is None:
            raise ValidationError("Not an impersonation session")

        await record_admin_action(
            self.session,
            auth,
            "impersonation.stop",
            request=request,
            target_type="user",
            target_id=auth.user_id,
            tenant_id=auth.tenant_id,
        )

        redis = get_redis()
        await redis.delete(f"session:{current_session_token}")

        original = data.impersonator_session
        if original is None or not await redis.exists(f"session:{original}"):
            logger.info("impersonation_stopped_original_expired", actor=str(data.impersonator_id))
            return None

        logger.info(
            "impersonation_stopped",
            actor=str(data.impersonator_id),
            target=str(auth.user_id),
        )
        return original

    # --- Audit log ---

    async def list_audit_log(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        action: str | None = None,
        tenant_id: uuid.UUID | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        actor = select(User).subquery()
        impersonator = select(User).subquery()

        stmt = (
            select(AdminAuditLog, actor.c.email, impersonator.c.email)
            .outerjoin(actor, actor.c.id == AdminAuditLog.actor_user_id)
            .outerjoin(impersonator, impersonator.c.id == AdminAuditLog.impersonator_id)
        )
        count_stmt = select(func.count(AdminAuditLog.id))

        if action:
            stmt = stmt.where(AdminAuditLog.action == action)
            count_stmt = count_stmt.where(AdminAuditLog.action == action)
        if tenant_id:
            stmt = stmt.where(AdminAuditLog.tenant_id == tenant_id)
            count_stmt = count_stmt.where(AdminAuditLog.tenant_id == tenant_id)

        total = (await self.session.execute(count_stmt)).scalar_one()
        rows = await self.session.execute(
            stmt.order_by(AdminAuditLog.created_at.desc()).offset(offset).limit(limit)
        )

        return [
            {
                **{
                    field: getattr(entry, field)
                    for field in (
                        "id",
                        "actor_user_id",
                        "impersonator_id",
                        "action",
                        "target_type",
                        "target_id",
                        "tenant_id",
                        "payload",
                        "ip_address",
                        "created_at",
                    )
                },
                "actor_email": actor_email,
                "impersonator_email": impersonator_email,
            }
            for entry, actor_email, impersonator_email in rows.all()
        ], total

    # --- Helpers ---

    @staticmethod
    def _apply_search(
        stmt: Select[Any],
        count_stmt: Select[Any],
        search: str,
        columns: tuple[Any, ...],
    ) -> tuple[Select[Any], Select[Any]]:
        pattern = f"%{search}%"
        clause = or_(*(column.ilike(pattern) for column in columns))
        return stmt.where(clause), count_stmt.where(clause)
