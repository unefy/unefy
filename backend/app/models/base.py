import uuid
from datetime import datetime
from typing import Any, ClassVar

from sqlalchemy import DateTime, ForeignKey, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    type_annotation_map: ClassVar[dict[Any, Any]] = {
        uuid.UUID: Uuid,
        datetime: DateTime(timezone=True),
    }


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        index=True,
    )


class TenantMixin:
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )


class AuditMixin(TimestampMixin):
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)


class TenantModel(Base, TenantMixin):
    """Abstract base for tenant-scoped models with a UUID primary key.

    The repository layer is generic over this class, and that is the point:
    it makes `model_class.tenant_id` an attribute the type checker verifies
    rather than one the code hopes for. Tenant scoping is the invariant that
    must never rest on hope, so it is the one the types pin down.

    Timestamps are deliberately not included — a model picks `TimestampMixin`
    or `AuditMixin` depending on whether it needs to record who acted.
    """

    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )


class BaseModel(TenantModel, TimestampMixin):
    """Tenant-scoped model with timestamps — the common default."""

    __abstract__ = True
