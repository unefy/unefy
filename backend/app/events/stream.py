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

#: Where a client with no `Last-Event-ID` starts: "only what happens from now on".
#: Not `0`, which would replay the whole retained window to a client that has just
#: finished a delta sync and needs none of it.
STREAM_NOW = "$"


async def event_stream(
    redis: Redis,
    tenant_id: Any,
    *,
    last_event_id: str | None = None,
    allowed: frozenset[str] | None = None,
    on_heartbeat: Callable[[], Awaitable[None]] | None = None,
) -> AsyncGenerator[str]:
    """Yield SSE frames for one tenant until the client goes away.

    Touches Redis only. **No database session may be held here** — see
    `app/api/v1/stream.py` for why that would take the whole backend down.

    @param allowed collection names this connection may be told about. A stream is
        per tenant but its readers hold different roles, so the filter happens on
        the way out. None means no filtering.
    @param on_heartbeat called each time the stream goes quiet. The route uses it
        to re-assert that this connection is still alive, which is what lets a
        dead one age out of the connection cap instead of holding a slot forever.
    """
    key = stream_key(tenant_id)
    cursor = last_event_id or STREAM_NOW

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
                if allowed is not None and fields.get("entity") not in allowed:
                    continue
                yield encode_sse(event_id, fields)
