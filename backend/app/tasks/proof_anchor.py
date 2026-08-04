"""Anchoring proof-chain heads at an external TSA, on schedule.

Runs only when `TSA_URL` is configured — an anchor row without a real token
would be a claim with nothing behind it, so an unconfigured install simply
has no anchors (and the chain still holds against outsiders).

Same shape as the retention sweep: in-process loop, Redis `SET NX` so one
worker anchors per interval. Anchoring is idempotent in effect — a second
token over the same head is redundant, not wrong — so the lock is an economy.
Per tenant, one anchor per interval *only if the chain grew*: a quiet club's
head is already covered by its last anchor, and re-stamping it daily would
spend the TSA's goodwill on proving nothing new.
"""

import asyncio
from datetime import UTC, datetime
from typing import Any

import structlog
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.integrations.tsa import TsaClient
from app.models.proof_chain import ProofChainAnchor, ProofChainEntry

logger = structlog.get_logger()

#: Daily. The plan allows "täglich oder monatlich" — daily bounds the window
#: in which a self-hosted operator could rewrite history to under a day.
ANCHOR_INTERVAL_SECONDS = 86_400

LOCK_TTL_SECONDS = ANCHOR_INTERVAL_SECONDS - 300

_LOCK_KEY = "proof-anchor:sweep"


async def run_anchor_loop(
    redis: Redis,
    client: TsaClient,
    session_factory: Any = async_session_factory,
    interval_seconds: float = ANCHOR_INTERVAL_SECONDS,
) -> None:
    """Runs until cancelled."""
    while True:
        try:
            if await _acquire(redis):
                async with session_factory() as session:
                    anchored = await anchor_once(session, client)
                if anchored:
                    logger.info("proof_chains_anchored", tenants=anchored)
        except asyncio.CancelledError:
            raise
        except Exception:
            # The next interval retries; an anchor a day late still bounds the
            # rewrite window, just a little wider.
            logger.warning("proof_anchor_sweep_failed", exc_info=True)
        await asyncio.sleep(interval_seconds)


async def _acquire(redis: Redis) -> bool:
    try:
        return bool(await redis.set(_LOCK_KEY, "1", nx=True, ex=LOCK_TTL_SECONDS))
    except Exception:
        logger.warning("proof_anchor_lock_unavailable", exc_info=True)
        return True


async def anchor_once(session: AsyncSession, client: TsaClient) -> int:
    """Anchor every tenant whose chain grew past its last anchor. Commits.

    One tenant's TSA failure does not stop the others: each anchor commits on
    its own, and the failed one is simply still unanchored next interval.
    """
    heads = (
        await session.execute(
            select(
                ProofChainEntry.tenant_id,
                func.max(ProofChainEntry.seq).label("head_seq"),
            ).group_by(ProofChainEntry.tenant_id)
        )
    ).all()

    anchored = 0
    for tenant_id, head_seq in heads:
        last_anchored = await session.scalar(
            select(func.max(ProofChainAnchor.seq_to)).where(ProofChainAnchor.tenant_id == tenant_id)
        )
        if last_anchored is not None and last_anchored >= head_seq:
            continue

        head = (
            await session.execute(
                select(ProofChainEntry)
                .where(ProofChainEntry.tenant_id == tenant_id)
                .where(ProofChainEntry.seq == head_seq)
            )
        ).scalar_one()

        try:
            token = await client.timestamp(head.chain_hash)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning("proof_anchor_tsa_failed", tenant_id=str(tenant_id), exc_info=True)
            continue

        session.add(
            ProofChainAnchor(
                tenant_id=tenant_id,
                seq_to=head.seq,
                chain_hash=head.chain_hash,
                tsa_token=token,
                tsa_url=client.url,
                anchored_at=datetime.now(UTC),
            )
        )
        await session.commit()
        anchored += 1
    return anchored
