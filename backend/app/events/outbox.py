"""Change hints, published after the transaction they describe has committed.

## Why an outbox and not just a publish call

`get_db_session` yields to the handler and commits *afterwards*
(`app/database.py`). Anything published from inside a service therefore fires
before the transaction is visible to any other connection: the client is told
"something changed", syncs immediately, reads the pre-change state, and then never
hears about it again. Silent, intermittent, and close to undebuggable — the
symptom is "sometimes the app is one edit behind" with no failing request.

So writes queue their hints on `session.info` and the session teardown drains
them once the commit has actually succeeded. On the exception path the queue is
discarded with the transaction, which is the correct pairing: no commit, no
notification.

The two halves are deliberately built differently, and the split is the design:

- **Collection is implicit**, via a `before_flush` listener, because it has to be
  *complete*. Nine entity types are written by hand-rolled service code that never
  goes near `BaseRepository`, and a forgotten call site is invisible — that entity
  merely stops being live, which nobody notices for months. See [_collect_flush].
- **Publishing is explicit**, one call in `app/database.py` right after the commit
  returns, because what has to be *obvious* there is the ordering. An
  `after_commit` listener would hide the very thing a reader needs to see.

## Why Redis Streams and not pub/sub

Pub/sub is fire-and-forget: a client whose connection flaps for three seconds
silently misses whatever happened in the gap, and has no way to know it did. A
stream keeps a bounded history, so `Last-Event-ID` on reconnect resumes exactly
where the connection dropped. The stream id *is* the SSE event id — no parallel
bookkeeping.

## Why hints and not rows

Three reasons, in order of weight.

1. **Authorization.** There is one stream per tenant, but its readers hold
   different roles. `MemberResponse` carries `iban`, `bic` and
   `sepa_mandate_reference`; `MemberDirectoryEntry` exists precisely because that
   narrowing is a separate schema. Broadcasting rows would move the authorization
   decision out of the request handler and into the fan-out layer, where it will
   eventually be got wrong for one role and nobody will notice.
2. **One place decides the shape.** `/api/v1/sync/*` already applies role gating
   and field selection. A second serialisation path would drift from it.
3. **A hint is idempotent and order-insensitive.** "Member 3f2a changed" is true
   however many times and in whatever order it arrives. A row payload has to be
   reasoned about against what the client already holds.

The cost is one extra round trip per burst, which is wanted anyway: the client
should coalesce a burst of hints into a single delta sync.
"""

import json
import uuid
from dataclasses import dataclass
from typing import Any

import structlog
from redis.asyncio import Redis
from redis.typing import EncodableT, FieldT
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import get_history

logger = structlog.get_logger()

#: What `xadd` accepts. Taken from redis's own aliases rather than spelled out:
#: `dict` is invariant in its parameters, so a `dict[str, str]` is not assignable
#: to it however obviously compatible the values are.
type StreamFields = dict[FieldT, EncodableT]

#: Key under which pending hints live on `session.info`.
OUTBOX_KEY = "unefy_change_events"

#: Roughly how many events a tenant's stream keeps. Sized for reconnects, not for
#: history: a client that falls further behind than this re-syncs from its cursor,
#: which is durable on the device and always correct.
STREAM_MAX_LEN = 500

#: An idle tenant's stream should not linger forever.
STREAM_TTL_SECONDS = 3600


def stream_key(tenant_id: uuid.UUID) -> str:
    """One stream per tenant.

    Not per entity type: a club has tens of concurrent devices, not thousands, and
    per-entity channels would mean N subscriptions per phone plus a subscription
    protocol to manage them. Filtering by role happens on the way out.
    """
    return f"unefy:events:{tenant_id}"


@dataclass(frozen=True)
class ChangeEvent:
    tenant_id: uuid.UUID
    entity: str
    entity_id: uuid.UUID

    #: `upsert` or `delete`. Deliberately coarse — the client re-reads either way,
    #: and a finer verb would imply the hint carries information it does not.
    op: str

    def fields(self) -> "StreamFields":
        return {
            "entity": self.entity,
            "id": str(self.entity_id),
            "op": self.op,
        }


def queue_change(
    session: AsyncSession | Session,
    *,
    tenant_id: uuid.UUID,
    entity: str,
    entity_id: uuid.UUID,
    op: str,
) -> None:
    """Record that something changed. Published only if the commit succeeds."""
    pending: list[ChangeEvent] = session.info.setdefault(OUTBOX_KEY, [])
    pending.append(ChangeEvent(tenant_id=tenant_id, entity=entity, entity_id=entity_id, op=op))


def _collect_flush(session: Session, _ctx: object) -> None:
    """Queue a hint for every synced row this flush just wrote.

    ## Why a listener and not a call in each write path

    Collection has to be *complete*, and explicit calls are not. Members, events,
    registrations, fee types, member fees, dues, competitions, sessions and entries
    are all created by hand-rolled code that never touches
    `BaseRepository.create` — `MemberService.create` builds the row itself so it
    can allocate a member number under a row lock, and it is right to. Eight call
    sites today is eight places to forget, and the next feature adds more. A
    forgotten one is invisible: the row syncs correctly on the next poll, so the
    only symptom is that *one* entity type is not live, which nobody notices for
    months.

    So completeness is automatic here, and only the *publish* step stays explicit
    (see `app/database.py`) — that is the step whose ordering has to be visible.

    Bulk `UPDATE`s bypass the ORM entirely and so bypass this too;
    `BaseRepository.soft_delete_many` announces itself for that reason.

    ## Why `after_flush` and not `before_flush`

    Primary keys. `Member.id` defaults to `uuid.uuid4` as a *column* default, which
    SQLAlchemy applies during the flush, and `MemberService.create` does not supply
    one. In `before_flush` a newly added row therefore still has `id = None`, and a
    hint without an id is not a hint. `after_flush` runs late enough for the keys to
    exist while `session.new` / `dirty` / `deleted` still hold their pre-flush
    contents — the one hook where both are true.
    """
    from app.sync.registry import collection_for_model

    def note(obj: object, op: str) -> None:
        collection = collection_for_model(type(obj))
        if collection is None:
            return
        tenant_id = getattr(obj, "tenant_id", None)
        entity_id = getattr(obj, "id", None)
        if tenant_id is None or entity_id is None:
            # Should be unreachable after a flush. Logged rather than ignored
            # because silence here is precisely the failure this design is meant
            # to avoid: one entity type quietly stops being live.
            logger.warning(
                "change_hint_incomplete", model=type(obj).__name__, collection=collection
            )
            return
        queue_change(session, tenant_id=tenant_id, entity=collection, entity_id=entity_id, op=op)

    for obj in session.new:
        note(obj, "upsert")

    for obj in session.dirty:
        if not session.is_modified(obj, include_collections=False):
            continue
        # A soft delete is an UPDATE, so it has to be recognised by what changed
        # rather than by which statement ran.
        history = get_history(obj, "deleted_at") if hasattr(obj, "deleted_at") else None
        became_deleted = bool(history and history.added and history.added[0] is not None)
        note(obj, "delete" if became_deleted else "upsert")

    for obj in session.deleted:
        note(obj, "delete")


def register_change_listener() -> None:
    """Install [_collect_flush]. Idempotent, so importing twice is harmless."""
    if not event.contains(Session, "after_flush", _collect_flush):
        event.listen(Session, "after_flush", _collect_flush)


def take_pending(session: AsyncSession | Session) -> list[ChangeEvent]:
    """Hand over the queued hints and clear the queue."""
    pending: list[ChangeEvent] = session.info.pop(OUTBOX_KEY, [])
    return pending


async def publish(redis: Redis, events: list[ChangeEvent]) -> None:
    """Push hints onto their tenants' streams.

    Never raises. A Redis hiccup must cost latency — clients fall back to their
    next poll — and must never turn a committed write into an error response. The
    write already happened; there is nothing to undo and nothing the caller could
    do about it.
    """
    if not events:
        return
    # A transaction that flushes the same row several times queues the same hint
    # several times. One entry says everything the duplicates would; the extras
    # only burn the stream's bounded history and fan out frames every client
    # coalesces away. Order is preserved, first occurrence wins.
    events = list(dict.fromkeys(events))
    try:
        pipe = redis.pipeline()
        for event in events:
            key = stream_key(event.tenant_id)
            # `~` makes trimming amortised: Redis is allowed to overshoot the
            # limit slightly rather than trim on every single write.
            pipe.xadd(key, event.fields(), maxlen=STREAM_MAX_LEN, approximate=True)
            pipe.expire(key, STREAM_TTL_SECONDS)
        await pipe.execute()
    except Exception:
        logger.warning("change_publish_failed", events=len(events), exc_info=True)


def encode_sse(event_id: str, fields: dict[str, Any]) -> str:
    """One SSE frame.

    The `id:` line is the Redis stream id, which is what makes `Last-Event-ID`
    resumption exact rather than approximate.
    """
    data = json.dumps({"v": 1, **fields}, separators=(",", ":"))
    return f"id: {event_id}\nevent: change\ndata: {data}\n\n"
