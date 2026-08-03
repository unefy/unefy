"""The sync cursor: an opaque keyset position in a tenant's change history.

## Why a (timestamp, id) pair and not a bare timestamp

Rows share an `updated_at`. `func.now()` is constant for a whole transaction, so
a bulk operation stamps dozens of rows identically. A bare-timestamp cursor then
forces a choice between two broken options: `> ts` skips the siblings, which is
silent data loss, and `>= ts` re-delivers the whole batch forever and never
terminates once a batch exceeds one page. Adding the id makes the ordering total,
so `(updated_at, id) > (ts, id)` has exactly one meaning.

## Why opaque

Because the timestamp inside is always a value *the server produced*. The device
never invents it, never adjusts it for its own clock, never does arithmetic on
it — it stores a blob and echoes it back. Clock skew is excluded structurally
rather than tolerated numerically, which is a stronger guarantee than the one
`AttendanceRecord.checked_in_at` needs (see `_resolve_occurred_at` in
`app/services/attendance.py`: there the device clock is the only available source
for the fact, so it is accepted and bounded; here there is a better source, so it
is not accepted at all).

Opacity also means the shape can gain fields without an API version bump. Base64
of plain JSON, not encrypted: `base64 -d` should stay a debugging tool.

## The visibility gap, and why the watermark exists

`TimestampMixin.updated_at` defaults to `func.now()`, which Postgres maps to
`transaction_timestamp()` — **transaction start, not commit**. A transaction that
begins at T, runs 800ms and commits at T+800ms writes `updated_at = T`. A sync
request served at T+400ms therefore hands out a cursor at or after T, and when
that row finally becomes visible at T+800ms it already sorts *behind* the cursor.
It would never be delivered. Not late — never.

[CURSOR_SAFETY_LAG] closes that: the query never reads rows newer than
`now() - lag`, so any cursor it issues is at least that old and a slow
transaction has time to land in front of it. The cost is that a cold poll is up
to five seconds behind, which does not matter because the push channel carries
the low-latency path and also tells the client when to poll again.

**The invariant, which every choice here bends toward:** the delivered set is
always a superset of the changed set, never a subset. Duplicates are free — every
client-side apply is an upsert by primary key. A missing row is unrecoverable.

Residual risk, stated rather than hidden: a transaction longer than the lag can
still slip through. Real interactive transactions do not, but a bulk import
might. If that ever bites, the fix is a commit-ordered change log (an outbox
whose sequence is assigned after commit, or logical decoding) — and the cursor
being opaque is exactly what keeps that a server-only change.
"""

import base64
import binascii
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.core.exceptions import AppError

CURSOR_VERSION = 1

# How far behind "now" the newest readable row must be. See the module docstring:
# this is the guard against `updated_at` being transaction-start time.
CURSOR_SAFETY_LAG = timedelta(seconds=5)

# Past this age a cursor is refused and the client bootstraps instead. Two jobs:
# it bounds how long tombstones must be kept, and it is the only recovery path
# for *hard*-deleted rows, which sync cannot see at all.
CURSOR_MAX_AGE = timedelta(days=14)

# Where a client with no cursor starts. Not `datetime.min` — Postgres accepts it
# but it is a value nobody can eyeball, and the epoch reads as "the beginning".
EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
ZERO_UUID = uuid.UUID(int=0)


class CursorInvalidError(AppError):
    """Malformed, truncated, or hand-crafted cursor."""

    def __init__(self, message: str = "Sync cursor is not valid") -> None:
        super().__init__(status_code=400, code="INVALID_CURSOR", message=message)


class CursorTooOldError(AppError):
    """Older than [CURSOR_MAX_AGE] — tombstones that old may already be gone."""

    def __init__(self) -> None:
        super().__init__(
            status_code=409,
            code="CURSOR_TOO_OLD",
            message="Sync cursor is too old to resume from; start a fresh sync without one",
        )


@dataclass(frozen=True)
class Cursor:
    """A position in one collection's change history."""

    updated_at: datetime
    entity_id: uuid.UUID

    #: False until the first page of a cold start has been drained. The only
    #: thing it changes is whether tombstones are included — see `is_bootstrap`.
    bootstrap: bool = False

    @property
    def is_start(self) -> bool:
        return self.updated_at == EPOCH and self.entity_id == ZERO_UUID


def start_cursor(*, bootstrap: bool) -> Cursor:
    """The position a client with no cursor begins at."""
    return Cursor(updated_at=EPOCH, entity_id=ZERO_UUID, bootstrap=bootstrap)


def watermark(now: datetime) -> datetime:
    """The newest `updated_at` a sync page may read."""
    return now - CURSOR_SAFETY_LAG


def encode_cursor(cursor: Cursor) -> str:
    payload = {
        "v": CURSOR_VERSION,
        "ts": cursor.updated_at.isoformat(),
        "id": str(cursor.entity_id),
        "phase": "bootstrap" if cursor.bootstrap else "live",
    }
    raw = json.dumps(payload, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(token: str, *, now: datetime) -> Cursor:
    """Parse a cursor, or refuse it.

    Every failure mode answers 400, never 500 and never a stack trace: a cursor
    arrives from a device that may have truncated it, stored it through an app
    upgrade, or had it mangled by a proxy.
    """
    try:
        padded = token + "=" * (-len(token) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode()))
    except (ValueError, binascii.Error) as exc:
        raise CursorInvalidError() from exc

    if not isinstance(payload, dict) or payload.get("v") != CURSOR_VERSION:
        raise CursorInvalidError("Sync cursor version is not supported")

    raw_ts = payload.get("ts")
    raw_id = payload.get("id")
    if not isinstance(raw_ts, str) or not isinstance(raw_id, str):
        raise CursorInvalidError()

    try:
        updated_at = datetime.fromisoformat(raw_ts)
        entity_id = uuid.UUID(raw_id)
    except ValueError as exc:
        raise CursorInvalidError() from exc

    if updated_at.tzinfo is None:
        # A naive timestamp cannot be compared against `now`, and guessing a
        # zone here is how a client in UTC+2 would silently skip two hours.
        raise CursorInvalidError("Sync cursor timestamp must carry a timezone")

    # The start cursor is exempt: it is older than any age limit by construction
    # and means "I have nothing", which is precisely what a bootstrap is.
    if updated_at > EPOCH and now - updated_at > CURSOR_MAX_AGE:
        raise CursorTooOldError()

    return Cursor(
        updated_at=updated_at,
        entity_id=entity_id,
        bootstrap=payload.get("phase") == "bootstrap",
    )
