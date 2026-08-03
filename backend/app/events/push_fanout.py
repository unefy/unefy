"""Turning committed change hints into FCM wake-ups.

## Why a background task and not the request path

A bulk import that touches 500 rows queues 500 hints; a club has tens of
devices, and FCM's HTTP v1 has no multicast — sending from the request path
would put thousands of sequential HTTPS calls between a board member and
their response. So the request path keeps doing what it already does (XADD to
the tenant's stream, `app/events/outbox.py`), and this task turns the stream
into wake-ups at its own pace.

## Why a consumer group

The backend runs several Uvicorn workers, each with this task. A consumer
group distributes entries among them without a leader election: whoever reads
an entry owns it. The SSE readers are unaffected — they read the same streams
outside any group.

## Coalescing

One wake-up per club per [COALESCE_TTL_SECONDS], via `SET NX EX`. The window
costs nothing: the woken device waits out the server's safety lag before its
drain anyway, and a second wake-up inside the window would find a device that
is already syncing. The price is named in the plan: a burst whose first hint
is board-only (members) swallows a member-visible hint (events) arriving in
the same window — the members' devices catch up on the next change or app
open, which is the doorbell contract.
"""

import asyncio
import uuid
from typing import Any

import structlog
from redis.asyncio import Redis
from redis.exceptions import ResponseError

from app.database import async_session_factory
from app.integrations.push import FcmSender
from app.repositories.push_device import PushDeviceRepository
from app.sync.registry import COLLECTIONS

logger = structlog.get_logger()

GROUP = "push"

#: One wake-up per club per window. See the module docstring.
COALESCE_TTL_SECONDS = 10

#: How often to look for streams of tenants that were quiet until now.
DISCOVER_INTERVAL_SECONDS = 5.0

#: How long one XREADGROUP blocks before the loop discovers new streams again.
READ_BLOCK_MS = 5_000

_STREAM_PREFIX = "unefy:events:"


async def run_push_fanout(
    redis: Redis,
    sender: FcmSender,
    consumer: str,
    session_factory: Any = async_session_factory,
) -> None:
    """Runs until cancelled. One instance per worker process; the group makes
    that cooperation instead of duplication.

    `session_factory` is injectable for the same reason the sender is: the
    fan-out opens its own short-lived sessions, and a test has to hand it the
    transaction it can see.
    """
    known: set[str] = set()
    try:
        while True:
            await _discover(redis, known)
            if not known:
                await asyncio.sleep(DISCOVER_INTERVAL_SECONDS)
                continue

            try:
                batches = await redis.xreadgroup(
                    GROUP,
                    consumer,
                    {key: ">" for key in known},
                    count=100,
                    block=READ_BLOCK_MS,
                )
            except ResponseError:
                # A stream expired (idle tenants' streams carry a TTL) and took
                # its group with it. Forget everything and rediscover — cheaper
                # and more honest than guessing which key died.
                known.clear()
                continue
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.warning("push_fanout_read_failed", exc_info=True)
                await asyncio.sleep(DISCOVER_INTERVAL_SECONDS)
                continue

            for stream_key, entries in batches or []:
                tenant = str(stream_key).removeprefix(_STREAM_PREFIX)
                for entry_id, fields in entries:
                    try:
                        await _handle(redis, sender, tenant, fields, session_factory)
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        # One bad entry must not stall the stream behind it.
                        logger.warning("push_fanout_entry_failed", exc_info=True)
                    await redis.xack(stream_key, GROUP, entry_id)
    finally:
        await sender.aclose()


async def _discover(redis: Redis, known: set[str]) -> None:
    """Find tenant streams and make sure the group exists on each.

    The group starts at `$`: entries older than the group's creation were
    handled by the SSE path while the fan-out was down, and a wake-up is only
    worth sending for what happens from now on.
    """
    try:
        async for key in redis.scan_iter(match=f"{_STREAM_PREFIX}*"):
            name = str(key)
            if name in known:
                continue
            try:
                await redis.xgroup_create(name, GROUP, id="$")
            except ResponseError as exc:
                if "BUSYGROUP" not in str(exc):
                    raise
            known.add(name)
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.warning("push_fanout_discover_failed", exc_info=True)


async def _handle(
    redis: Redis,
    sender: FcmSender,
    tenant: str,
    fields: dict[str, str],
    session_factory: Any = async_session_factory,
) -> None:
    entity = fields.get("entity")
    if entity is None or entity not in COLLECTIONS:
        return

    # The coalescing window — see the module docstring.
    if not await redis.set(f"push:sent:{tenant}", "1", nx=True, ex=COALESCE_TTL_SECONDS):
        return

    tenant_id = uuid.UUID(tenant)
    roles = COLLECTIONS[entity].roles

    async with session_factory() as session:
        tokens = await PushDeviceRepository(session).tokens_for_roles(tenant_id, roles)

    dead: list[str] = []
    for token in tokens:
        if not await sender.send_wakeup(token, tenant_id=tenant, entity=entity):
            dead.append(token)

    if dead:
        # FCM said these installs are gone. Dropping them keeps every future
        # fan-out from paying for devices that no longer exist.
        async with session_factory() as session:
            repo = PushDeviceRepository(session)
            for token in dead:
                await repo.delete_by_token(token)
            await session.commit()
        logger.info("push_dead_tokens_dropped", count=len(dead))

    if tokens:
        logger.info("push_wakeups_sent", entity=entity, devices=len(tokens) - len(dead))
