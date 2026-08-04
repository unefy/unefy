"""Reading a tenant's change stream as Server-Sent Events.

## Why SSE and not WebSocket

The deciding argument is self-hosting. `docker-compose.prod.yml` binds the backend
to `127.0.0.1`, so every real deployment has somebody else's reverse proxy in
front of it — nginx, Caddy, Traefik, a Synology, a Cloudflare tunnel. WebSocket
needs `Upgrade`/`Connection` passthrough, which is opt-in in nginx and quietly
missing from a lot of copied configs; the failure is a 400 with no diagnosis, and
it lands in *this project's* issue tracker. SSE is a plain GET returning
`text/event-stream` and traverses all of them. Its one gotcha, response buffering,
is fixable from the server with `X-Accel-Buffering: no`. A missing `Upgrade` is
not fixable from the server at all.

WebSocket's real advantage is client-to-server push, and this design does not want
it: writes go over ordinary POST/PATCH so they keep idempotency, retries and HTTP
status codes. A second stateful write path would mean two sets of write semantics
to keep in step.

## Why no library

`sse-starlette` would add disconnect detection and a ping loop. Both fall out of
the generator below: the heartbeat write is what discovers a dead socket, and
when it raises the generator ends. Under `mypy --strict` and "prefer simple,
readable code over clever abstractions", forty lines that are read once beat a
dependency whose typing has to be audited.
"""

import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import Any

import structlog
from redis.asyncio import Redis

from app.events.outbox import encode_sse, stream_key

logger = structlog.get_logger()

#: How long to wait on the stream before emitting a comment frame. Short enough
#: that idle proxies and phone radios keep the connection alive, long enough that
#: an idle club costs almost nothing.
HEARTBEAT_SECONDS = 25


async def event_stream(
    redis: Redis,
    tenant_id: Any,
    *,
    last_event_id: str | None = None,
    allowed: frozenset[str] | None = None,
    user_id: Any = None,
    on_heartbeat: Callable[[], Awaitable[None]] | None = None,
) -> AsyncGenerator[str]:
    """Yield SSE frames for one tenant until the client goes away.

    Touches Redis only. **No database session may be held here** — see
    `app/api/v1/stream.py` for why that would take the whole backend down.

    @param allowed collection names this connection may be told about. A stream is
        per tenant but its readers hold different roles, so the filter happens on
        the way out. None means no filtering.
    @param user_id who is reading, needed only for addressed frames — see
        `ChangeEvent.audience_user_id`. Without it, an addressed frame reaches
        nobody, which is the right way round: a connection that cannot prove it is
        the addressee is not one.
    @param on_heartbeat called each time the stream goes quiet. The route uses it
        to re-assert that this connection is still alive, which is what lets a
        dead one age out of the connection cap instead of holding a slot forever.
    """
    key = stream_key(tenant_id)
    cursor = last_event_id
    if cursor is None:
        # No `Last-Event-ID` means "only what happens from now on" — not `0`,
        # which would replay the whole retained window to a client that has just
        # finished a delta sync and needs none of it. "Now" is pinned to the
        # newest entry that currently exists, once, right here. Redis's `$` would
        # say the same thing more cheaply but re-resolves to "the newest id right
        # now" on *every* xread call, so an event landing in the gap between one
        # read returning empty and the next being issued would be skipped
        # forever. An absent or empty stream pins to `0-0`: nothing is retained,
        # so everything that arrives later is genuinely new.
        try:
            newest = await redis.xrevrange(key, count=1)
        except Exception:
            logger.warning("event_stream_resolve_failed", exc_info=True)
            return
        cursor = newest[0][0] if newest else "0-0"

    # An immediate frame, before anything has changed. Two jobs: it flushes the
    # response headers through any buffering proxy so the client's connection
    # actually opens, and it gives the client a positive "the stream is live"
    # signal rather than silence it cannot distinguish from a hang.
    yield ": open\n\n"

    while True:
        try:
            batches = await redis.xread(
                {key: cursor},
                block=HEARTBEAT_SECONDS * 1000,
                count=100,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning("event_stream_read_failed", exc_info=True)
            return

        if not batches:
            # Timed out with nothing to say. The write is also the liveness check:
            # if the client has gone, this raises and the generator unwinds.
            if on_heartbeat is not None:
                await on_heartbeat()
            yield ": heartbeat\n\n"
            continue

        for _stream, entries in batches:
            for event_id, fields in entries:
                cursor = event_id
                if not _may_hear(fields, allowed=allowed, user_id=user_id):
                    continue
                yield encode_sse(event_id, fields)


def _may_hear(
    fields: dict[str, str],
    *,
    allowed: frozenset[str] | None,
    user_id: Any,
) -> bool:
    """Whether this connection is told about one frame.

    Two filters, and an addressed frame answers to the second only. Its `entity`
    is deliberately not a syncable collection — nothing in `allowed` would ever
    match it — and it does not need to be: the publisher already decided that this
    one person may know, which is a narrower decision than the role gate makes and
    supersedes it. Letting `allowed` veto here would mean a member never hearing
    about their own check-in.
    """
    addressee = fields.get("to")
    if addressee is not None:
        return user_id is not None and addressee == str(user_id)
    return allowed is None or fields.get("entity") in allowed
