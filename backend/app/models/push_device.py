"""Devices that asked to be woken when something in their club changes.

One row per FCM token, which *is* the device identity — no separate device id.
The stored role decides which changes are worth a wake-up: `collections_for`
already knows what a role may sync, and waking a plain member for a member-list
edit would be a push for a sync the server then refuses.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class PushDevice(BaseModel):
    """A registered push target. The token is unique across tenants — a device
    re-registering under a new account simply moves its row."""

    __tablename__ = "push_devices"
    __table_args__ = (
        # The fan-out asks "which tokens in this club may hear about entity X" —
        # tenant first, role second answers it from the index.
        Index("ix_push_devices_tenant_role", "tenant_id", "role"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)

    #: "android" today; "ios" the day APNs arrives.
    platform: Mapped[str] = mapped_column(String(20), nullable=False)

    #: The FCM registration token. Unique: it identifies exactly one app install.
    token: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)

    #: The role at registration time, refreshed on every re-register. Used to
    #: filter wake-ups, never to authorise reads — the sync endpoints keep
    #: checking the live role themselves.
    role: Mapped[str] = mapped_column(String(20), nullable=False)

    #: Refreshed on every re-register, so stale rows are visible and a cleanup
    #: job has something to reap by.
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
