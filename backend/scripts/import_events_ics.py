"""Idempotent import of a public iCalendar feed into a tenant's event list.

Built for the SVES shooting calendar ("Schießtermine"), whose recurring
"Pistole / Revolver (25m)" entries become plain "Training" events while the
original summary is kept as the description.

Run inside the backend container:
    uv run python scripts/import_events_ics.py <url-or-path> [--tenant sves]
    uv run python scripts/import_events_ics.py <url-or-path> --dry-run

Re-runs update the matching event instead of creating a second one; the match
key is (tenant, starts_at, title), which is stable for this feed because no
two entries share a start time and a title.
"""

import argparse
import asyncio
import re
import sys
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.event import Event
from app.models.tenant import Tenant
from app.models.user import TenantMembership, User

DEFAULT_TENANT_SLUG = "sves"

# Summaries matching this become "Training"; the original text stays as the
# description so the discipline and notes like "Anschlusstermin" survive.
TRAINING_PATTERN = re.compile(r"pistole|revolver|training", re.IGNORECASE)
MEETING_PATTERN = re.compile(r"versammlung", re.IGNORECASE)
TRAINING_TITLE = "Training"


@dataclass
class IcsEvent:
    uid: str
    summary: str
    description: str | None
    location: str | None
    starts_at: datetime
    ends_at: datetime | None
    all_day: bool
    cancelled: bool


def _unfold(text: str) -> list[str]:
    """Join RFC 5545 continuation lines (a line starting with space/tab)."""
    lines: list[str] = []
    for raw in text.replace("\r\n", "\n").split("\n"):
        if raw[:1] in (" ", "\t") and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw)
    return lines


def _unescape(value: str) -> str:
    return (
        value.replace("\\n", "\n")
        .replace("\\N", "\n")
        .replace("\\,", ",")
        .replace("\\;", ";")
        .replace("\\\\", "\\")
    )


def _parse_dt(value: str) -> tuple[datetime, bool]:
    """Parse a DTSTART/DTEND value. Returns (datetime in UTC, all_day)."""
    if len(value) == 8:  # VALUE=DATE
        return datetime.strptime(value, "%Y%m%d").replace(tzinfo=UTC), True
    if value.endswith("Z"):
        return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC), False
    # Floating or TZID-qualified local time. This feed only emits UTC; treat
    # anything else as UTC rather than guessing a zone silently.
    return datetime.strptime(value, "%Y%m%dT%H%M%S").replace(tzinfo=UTC), False


def parse_ics(text: str) -> list[IcsEvent]:
    events: list[IcsEvent] = []
    current: dict[str, tuple[str, str]] | None = None
    for line in _unfold(text):
        if line == "BEGIN:VEVENT":
            current = {}
            continue
        if line == "END:VEVENT":
            if current is not None:
                events.append(_build_event(current))
            current = None
            continue
        if current is None or ":" not in line:
            continue
        head, _, value = line.partition(":")
        name, _, params = head.partition(";")
        current[name.upper()] = (params, value)
    return events


def _build_event(fields: dict[str, tuple[str, str]]) -> IcsEvent:
    _, start_raw = fields["DTSTART"]
    starts_at, all_day = _parse_dt(start_raw)
    ends_at: datetime | None = None
    if "DTEND" in fields:
        ends_at, _ = _parse_dt(fields["DTEND"][1])
    return IcsEvent(
        uid=fields.get("UID", ("", ""))[1],
        summary=_unescape(fields.get("SUMMARY", ("", ""))[1]).strip(),
        description=_unescape(fields.get("DESCRIPTION", ("", ""))[1]).strip() or None,
        location=_unescape(fields.get("LOCATION", ("", ""))[1]).strip() or None,
        starts_at=starts_at,
        ends_at=ends_at,
        all_day=all_day,
        cancelled=fields.get("STATUS", ("", ""))[1].upper() == "CANCELLED",
    )


def map_event(ics: IcsEvent) -> tuple[str, str, str | None]:
    """Map an ICS entry to (title, event_type, description)."""
    if TRAINING_PATTERN.search(ics.summary):
        return TRAINING_TITLE, "training", ics.description or ics.summary
    if MEETING_PATTERN.search(ics.summary):
        return ics.summary, "meeting", ics.description
    return ics.summary, "other", ics.description


def read_source(source: str) -> str:
    if source.startswith(("http://", "https://")):
        with urllib.request.urlopen(source, timeout=30) as response:
            return str(response.read().decode("utf-8"))
    return Path(source).read_text(encoding="utf-8")


async def _load_tenant(session: AsyncSession, slug: str) -> Tenant:
    tenant = (await session.execute(select(Tenant).where(Tenant.slug == slug))).scalar_one_or_none()
    if tenant is None:
        print(f"Tenant '{slug}' not found.", file=sys.stderr)
        raise SystemExit(1)
    return tenant


async def _audit_user_id(session: AsyncSession, tenant: Tenant) -> uuid.UUID | None:
    """Pick the tenant's owner as the author of the imported events."""
    stmt = (
        select(User.id)
        .join(TenantMembership, TenantMembership.user_id == User.id)
        .where(TenantMembership.tenant_id == tenant.id)
        .order_by(TenantMembership.created_at)
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def import_events(
    session: AsyncSession, tenant: Tenant, entries: list[IcsEvent], *, dry_run: bool
) -> tuple[int, int]:
    author_id = await _audit_user_id(session, tenant)
    existing = (
        (await session.execute(select(Event).where(Event.tenant_id == tenant.id))).scalars().all()
    )
    by_key = {(e.starts_at, e.title): e for e in existing}

    created = updated = 0
    for ics in sorted(entries, key=lambda e: e.starts_at):
        title, event_type, description = map_event(ics)
        status = "cancelled" if ics.cancelled else "scheduled"
        event = by_key.get((ics.starts_at, title))
        if event is None:
            if not dry_run:
                session.add(
                    Event(
                        tenant_id=tenant.id,
                        title=title,
                        description=description,
                        event_type=event_type,
                        location=ics.location,
                        starts_at=ics.starts_at,
                        ends_at=ics.ends_at,
                        all_day=ics.all_day,
                        status=status,
                        created_by=author_id,
                        updated_by=author_id,
                    )
                )
            created += 1
            print(f"  + {ics.starts_at:%Y-%m-%d %H:%M} {title} ({event_type})")
            continue

        changes = {
            "description": description,
            "event_type": event_type,
            "location": ics.location,
            "ends_at": ics.ends_at,
            "all_day": ics.all_day,
            "status": status,
        }
        touched = [k for k, v in changes.items() if getattr(event, k) != v]
        if touched:
            if not dry_run:
                for key in touched:
                    setattr(event, key, changes[key])
                event.updated_by = author_id
            updated += 1
            print(f"  ~ {ics.starts_at:%Y-%m-%d %H:%M} {title} ({', '.join(touched)})")
    return created, updated


async def run(source: str, slug: str, *, dry_run: bool) -> None:
    entries = parse_ics(read_source(source))
    if not entries:
        print("No VEVENT entries found in the feed.", file=sys.stderr)
        raise SystemExit(1)
    async with async_session_factory() as session:
        tenant = await _load_tenant(session, slug)
        print(f"Importing {len(entries)} calendar entries into '{tenant.slug}':")
        created, updated = await import_events(session, tenant, entries, dry_run=dry_run)
        if dry_run:
            await session.rollback()
            print(f"Dry run: {created} would be created, {updated} would be updated.")
            return
        await session.commit()
        print(f"Done: {created} created, {updated} updated.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="URL or file path of the .ics feed")
    parser.add_argument("--tenant", default=DEFAULT_TENANT_SLUG, help="Tenant slug")
    parser.add_argument("--dry-run", action="store_true", help="Report without writing")
    args = parser.parse_args()
    asyncio.run(run(args.source, args.tenant, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
