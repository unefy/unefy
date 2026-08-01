import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from app.schemas.base import BaseSchema


class AdminTenantResponse(BaseSchema):
    """A club as seen from the platform admin area."""

    id: uuid.UUID
    name: str
    short_name: str | None = None
    slug: str
    city: str | None = None
    is_active: bool
    created_at: datetime

    member_count: int = 0
    user_count: int = 0


class AdminUserResponse(BaseSchema):
    id: uuid.UUID
    email: str
    name: str
    image: str | None = None
    email_verified: bool
    locale: str | None = None
    is_superuser: bool
    created_at: datetime


class AdminMembershipResponse(BaseSchema):
    """A user's membership, used to pick a target club for impersonation."""

    tenant_id: uuid.UUID
    tenant_name: str
    role: str
    is_active: bool


class ImpersonateRequest(BaseSchema):
    user_id: uuid.UUID

    # Which club to enter. Optional only for users without any membership —
    # otherwise the admin must state which context they are stepping into,
    # rather than silently landing in an arbitrary one.
    tenant_id: uuid.UUID | None = None

    # Free-text justification, stored in the audit log. Required, because
    # "why" is the part of an impersonation record that matters months later.
    reason: str = Field(min_length=3, max_length=500)


class ImpersonateResponse(BaseSchema):
    user_id: uuid.UUID
    user_email: str
    tenant_id: uuid.UUID | None
    tenant_name: str | None
    role: str | None
    expires_in: int


class AuditLogResponse(BaseSchema):
    id: uuid.UUID
    actor_user_id: uuid.UUID
    actor_email: str | None = None
    impersonator_id: uuid.UUID | None = None
    impersonator_email: str | None = None
    action: str
    target_type: str | None = None
    target_id: uuid.UUID | None = None
    tenant_id: uuid.UUID | None = None
    payload: dict[str, Any] | None = None
    ip_address: str | None = None
    created_at: datetime
