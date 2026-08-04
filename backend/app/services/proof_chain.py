"""Appending to and verifying the proof chain (assurance level 1).

One writer path: [append_entry]. Callers hash their own content — the chain
does not interpret it, it only commits to it. Appends happen inside the same
transaction as the event they describe, for the same reason audit entries do:
a session close whose chain link failed must not exist half-way.

## Concurrency

The predecessor is read `FOR UPDATE`, so two concurrent appends for one
tenant serialize on the last link; the unique `(tenant_id, seq)` index backs
that up for the empty-chain race, where there is no row to lock. Proof events
are rare (a handful per club per evening), so contention is theoretical —
correctness of the order is not.
"""

import hashlib
import json
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attendance import AttendanceRecord
from app.models.proof_chain import ProofChainAnchor, ProofChainEntry

GENESIS_HASH = "0" * 64


def _sha256(payload: str) -> str:
    return hashlib.sha256(payload.encode()).hexdigest()


def canonical_hash(content: dict[str, Any]) -> str:
    """Hash of a canonical JSON rendering — sorted keys, compact, str fallback
    for dates and UUIDs. Anyone holding the same content can recompute it."""
    return _sha256(json.dumps(content, sort_keys=True, separators=(",", ":"), default=str))


def session_close_hash(session_id: uuid.UUID, records: list[AttendanceRecord]) -> str:
    """What "the state at closing" means, pinned to bytes.

    The live records at the moment of closing, sorted by id so the hash does
    not depend on query order. Soft-deleted rows are already out of `records`:
    they were corrected away *during* the evening, and what the close attests
    is the final list, not its drafts.
    """
    return canonical_hash(
        {
            "session_id": str(session_id),
            "records": [
                {
                    "id": str(record.id),
                    "member_id": str(record.member_id) if record.member_id else None,
                    "guest_name": record.guest_name,
                    "occurred_on": record.occurred_on.isoformat(),
                    "checked_in_at": record.checked_in_at.isoformat(),
                    "checked_out_at": (
                        record.checked_out_at.isoformat() if record.checked_out_at else None
                    ),
                    "method": record.method,
                    "assurance": record.assurance,
                    "verified_by_user_id": (
                        str(record.verified_by_user_id) if record.verified_by_user_id else None
                    ),
                }
                for record in sorted(records, key=lambda r: str(r.id))
            ],
        }
    )


async def append_entry(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    entry_type: str,
    subject_id: uuid.UUID,
    content_hash: str,
) -> ProofChainEntry:
    """Append one link. Flushes, does not commit — the caller's event does."""
    last = (
        await session.execute(
            select(ProofChainEntry)
            .where(ProofChainEntry.tenant_id == tenant_id)
            .order_by(ProofChainEntry.seq.desc())
            .limit(1)
            .with_for_update()
        )
    ).scalar_one_or_none()

    prev_hash = last.chain_hash if last else GENESIS_HASH
    entry = ProofChainEntry(
        tenant_id=tenant_id,
        seq=(last.seq + 1) if last else 1,
        entry_type=entry_type,
        subject_id=subject_id,
        content_hash=content_hash,
        prev_hash=prev_hash,
        chain_hash=_sha256(prev_hash + content_hash),
    )
    session.add(entry)
    await session.flush()
    return entry


@dataclass
class ChainStatus:
    length: int
    valid: bool
    broken_at_seq: int | None
    head_hash: str | None
    anchored_to_seq: int | None
    anchored_at: str | None


async def verify_chain(session: AsyncSession, tenant_id: uuid.UUID) -> ChainStatus:
    """Walk the whole chain and recompute every link.

    O(n) over all entries, which is fine for its audience: this is a button a
    board member or auditor presses, not a request path. A break names the
    first bad seq — everything before it is still intact evidence.
    """
    entries = (
        (
            await session.execute(
                select(ProofChainEntry)
                .where(ProofChainEntry.tenant_id == tenant_id)
                .order_by(ProofChainEntry.seq.asc())
            )
        )
        .scalars()
        .all()
    )

    expected_prev = GENESIS_HASH
    broken_at: int | None = None
    for position, entry in enumerate(entries, start=1):
        if (
            entry.seq != position
            or entry.prev_hash != expected_prev
            or entry.chain_hash != _sha256(entry.prev_hash + entry.content_hash)
        ):
            broken_at = entry.seq
            break
        expected_prev = entry.chain_hash

    anchor = (
        await session.execute(
            select(ProofChainAnchor)
            .where(ProofChainAnchor.tenant_id == tenant_id)
            .order_by(ProofChainAnchor.seq_to.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    return ChainStatus(
        length=len(entries),
        valid=broken_at is None,
        broken_at_seq=broken_at,
        head_hash=entries[-1].chain_hash if entries else None,
        anchored_to_seq=anchor.seq_to if anchor else None,
        anchored_at=anchor.anchored_at.isoformat() if anchor else None,
    )
