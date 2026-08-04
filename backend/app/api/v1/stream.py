"""`GET /api/v1/stream` — the doorbell.

Says "something changed, come and get it" and nothing more. Every frame carries a
collection name, an id and an op; the client coalesces a burst and issues one
delta sync against `/api/v1/sync/*`. A dropped frame therefore costs a few seconds
of freshness, never data — which is the whole reason the design puts correctness
in the pull and only latency in the push.

## The constraint that shapes this file

**No `Depends(get_db_session)`.** `app/database.py` configures
`pool_size=10, max_overflow=20` — thirty connections — and a dependency-injected
session is held open for the entire response. An SSE response lasts minutes, so
thirty-one phones with the app open would consume the pool and take down every
other request, the web UI included. That is not a load-test scenario; it is a
mid-sized club on a Tuesday evening.

So this route opens its own session, resolves auth, closes it, and from then on
talks only to Redis.

## No token in the query string

It would land in `RequestLoggingMiddleware`'s output and in every proxy access log
along the way. It is also unnecessary: the web app reaches this through its own
Next.js route handler, which forwards the session cookie server-side, and the
mobile clients use real HTTP clients that can set `Authorization` on a GET.
"""

import asyncio
import time
import uuid
from collections.abc import AsyncGenerator

import structlog
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.core.exceptions import AppError, ForbiddenError
from app.database import async_session_factory
from app.dependencies import resolve_auth
from app.events.stream import event_stream
from app.redis import get_redis
from app.sync.registry import collections_for

logger = structlog.get_logger()

router = APIRouter()

#: Concurrent streams allowed per club, and per user. A backstop against a
#: reconnect storm from a buggy client, not an accounting system.
MAX_STREAMS_PER_TENANT = 200
MAX_STREAMS_PER_USER = 3

#: How long a connection stays counted without saying it is still there. Every
#: heartbeat re-registers it, so a stream that dies simply stops refreshing and
#: ages out.
SLOT_TTL_SECONDS = 90


class TooManyStreamsError(AppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=429,
            code="TOO_MANY_STREAMS",
            message="Too many open event streams; close one or fall back to polling",
        )


def _slot_keys(tenant_id: uuid.UUID, user_id: uuid.UUID) -> tuple[str, str]:
    return f"sse:conns:{tenant_id}", f"sse:conns:{tenant_id}:{user_id}"


async def _claim_slot(tenant_id: uuid.UUID, user_id: uuid.UUID, connection_id: str) -> None:
    """Register this connection, or refuse it.

    ## Why a set of live connections and not a counter

    An INCR/DECR counter only stays honest if the decrement always runs, and here
    it cannot be relied on: the release happens in a `finally` during task
    cancellation, and awaiting Redis at that point is itself cancellable, so the
    decrement is frequently dropped. The counter then ratchets upward and the cap
    locks the user out of live updates permanently, with no error anywhere and
    nothing to restart. That is exactly what happened the first time this ran.

    So membership is *asserted*, not accumulated. Each connection adds itself to a
    sorted set scored by the last time it said hello, and the count is the number
    of members that said so recently. A connection that dies stops refreshing and
    disappears on its own; the release below is an optimisation, not a
    requirement.
    """
    redis = get_redis()
    tenant_key, user_key = _slot_keys(tenant_id, user_id)
    now = time.time()
    cutoff = now - SLOT_TTL_SECONDS

    pipe = redis.pipeline()
    for key in (tenant_key, user_key):
        pipe.zremrangebyscore(key, "-inf", cutoff)
        pipe.zadd(key, {connection_id: now})
        pipe.zcard(key)
        pipe.expire(key, SLOT_TTL_SECONDS * 2)
    results = await pipe.execute()

    # zcard is the third command of each group of four.
    tenant_count, user_count = results[2], results[6]

    if tenant_count > MAX_STREAMS_PER_TENANT or user_count > MAX_STREAMS_PER_USER:
        await _release_slot(tenant_id, user_id, connection_id)
        raise TooManyStreamsError()


async def _touch_slot(tenant_id: uuid.UUID, user_id: uuid.UUID, connection_id: str) -> None:
    """Say this connection is still alive. Called on every heartbeat."""
    redis = get_redis()
    tenant_key, user_key = _slot_keys(tenant_id, user_id)
    now = time.time()
    try:
        pipe = redis.pipeline()
        for key in (tenant_key, user_key):
            pipe.zadd(key, {connection_id: now})
            pipe.expire(key, SLOT_TTL_SECONDS * 2)
        await pipe.execute()
    except Exception:
        logger.warning("sse_slot_touch_failed", exc_info=True)


async def _release_slot(tenant_id: uuid.UUID, user_id: uuid.UUID, connection_id: str) -> None:
    """Give the slot back immediately rather than waiting for it to age out.

    Best-effort by design — see [_claim_slot]. If this is lost, the entry
    expires within [SLOT_TTL_SECONDS] anyway.
    """
    redis = get_redis()
    tenant_key, user_key = _slot_keys(tenant_id, user_id)
    try:
        pipe = redis.pipeline()
        pipe.zrem(tenant_key, connection_id)
        pipe.zrem(user_key, connection_id)
        await pipe.execute()
    except Exception:
        logger.warning("sse_slot_release_failed", exc_info=True)


#: Keeps in-flight release tasks alive — a bare `create_task` result that nothing
#: references may be garbage-collected before it runs.
_release_tasks: set[asyncio.Task[None]] = set()


def _release_slot_soon(tenant_id: uuid.UUID, user_id: uuid.UUID, connection_id: str) -> None:
    """Schedule the release as its own task, immune to this request's teardown.

    The natural `await _release_slot(...)` in the generator's `finally` runs
    during task cancellation, where the await itself is cancellable — so three
    quick reloads dropped three releases, filled the per-user cap, and locked
    the user out of live updates for [SLOT_TTL_SECONDS]. A detached task is not
    cancelled with the request and gets the decrement through.
    """
    task = asyncio.create_task(_release_slot(tenant_id, user_id, connection_id))
    _release_tasks.add(task)
    task.add_done_callback(_release_tasks.discard)


@router.get("")
async def stream(request: Request) -> StreamingResponse:
    """Open a change stream for the caller's club."""
    # Auth in a session that is opened and closed right here. See the module
    # docstring: this is the difference between one connection borrowed for
    # milliseconds and one pinned for the life of the stream.
    async with async_session_factory() as session:
        auth = await resolve_auth(request, session)

    if auth is None or auth.tenant_id is None:
        raise ForbiddenError("No valid authentication provided")

    tenant_id = auth.tenant_id
    user_id = auth.user_id
    # A stream is per tenant, but its readers hold different roles, so what a
    # connection may be *told about* is narrowed here rather than at publish time.
    allowed = frozenset(c.name for c in collections_for(auth.role))
    last_event_id = request.headers.get("last-event-id")

    # Identifies this connection in the live-connection set. Random rather than
    # derived from the request: two tabs of the same user must count as two.
    connection_id = uuid.uuid4().hex
    await _claim_slot(tenant_id, user_id, connection_id)

    async def frames() -> AsyncGenerator[str]:
        async def still_here() -> None:
            await _touch_slot(tenant_id, user_id, connection_id)

        try:
            async for frame in event_stream(
                get_redis(),
                tenant_id,
                last_event_id=last_event_id,
                allowed=allowed,
                user_id=user_id,
                on_heartbeat=still_here,
            ):
                yield frame
        finally:
            # An optimisation, not a requirement: if the detached task is lost
            # with the event loop, the entry ages out of the set on its own.
            _release_slot_soon(tenant_id, user_id, connection_id)

    return StreamingResponse(
        frames(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-store",
            # nginx buffers proxied responses by default, which would hold frames
            # until the buffer filled and make the stream look broken. This is the
            # server-side fix that needs no cooperation from whoever runs the proxy.
            "X-Accel-Buffering": "no",
        },
    )
