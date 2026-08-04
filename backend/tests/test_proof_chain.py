"""Assurance level 1: the chain over proof events, and its external anchor."""

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.tsa import TsaClient, build_timestamp_query
from app.models import Tenant
from app.models.attendance import AttendanceSession
from app.models.member import Member
from app.models.proof_chain import ProofChainAnchor, ProofChainEntry
from app.models.sport import Sport
from app.models.tenant_sport import TenantSport
from app.services.proof_chain import GENESIS_HASH, append_entry, verify_chain
from app.tasks.proof_anchor import anchor_once


async def _add_member(db_session: AsyncSession, tenant_id: uuid.UUID) -> Member:
    member = Member(
        tenant_id=tenant_id,
        member_number=f"M-{uuid.uuid4().hex[:8]}",
        first_name="Erika",
        last_name="Musterfrau",
    )
    db_session.add(member)
    await db_session.flush()
    return member


async def _create_closed_session(
    client: AsyncClient, db_session: AsyncSession, tenant_id: uuid.UUID
) -> tuple[dict[str, Any], dict[str, Any]]:
    """One session with one member checked in, closed via the API."""
    member = await _add_member(db_session, tenant_id)
    now = datetime.now(UTC)
    created = await client.post(
        "/api/v1/attendance/sessions",
        json={
            "title": "Training",
            "opens_at": (now - timedelta(hours=1)).isoformat(),
            "closes_at": (now + timedelta(hours=2)).isoformat(),
        },
    )
    assert created.status_code == 201, created.text
    session_data = created.json()["data"]

    checked_in = await client.post(
        f"/api/v1/attendance/sessions/{session_data['id']}/check-in",
        json={"member_id": str(member.id), "method": "manual"},
    )
    assert checked_in.status_code == 201, checked_in.text

    closed = await client.post(f"/api/v1/attendance/sessions/{session_data['id']}/close")
    assert closed.status_code == 200, closed.text
    return closed.json()["data"], checked_in.json()["data"]


async def _entries(db_session: AsyncSession, tenant_id: uuid.UUID) -> list[ProofChainEntry]:
    return list(
        (
            await db_session.execute(
                select(ProofChainEntry)
                .where(ProofChainEntry.tenant_id == tenant_id)
                .order_by(ProofChainEntry.seq.asc())
            )
        )
        .scalars()
        .all()
    )


@pytest.mark.asyncio
async def test_closing_a_session_chains_its_state(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    session_data, _ = await _create_closed_session(auth_client, db_session, test_tenant.id)

    row = await db_session.get(AttendanceSession, uuid.UUID(session_data["id"]))
    assert row is not None
    assert row.close_hash is not None

    entries = await _entries(db_session, test_tenant.id)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.entry_type == "session_close"
    assert entry.seq == 1
    assert entry.subject_id == row.id
    assert entry.content_hash == row.close_hash
    assert entry.prev_hash == GENESIS_HASH
    assert (
        entry.chain_hash == hashlib.sha256((GENESIS_HASH + entry.content_hash).encode()).hexdigest()
    )


@pytest.mark.asyncio
async def test_an_amendment_after_closing_chains_against_the_close_hash(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    _, record_data = await _create_closed_session(auth_client, db_session, test_tenant.id)

    amended = await auth_client.patch(
        f"/api/v1/attendance/records/{record_data['id']}",
        json={"note": "Nachtrag vom Folgetag", "reason": "Notiz vergessen"},
    )
    assert amended.status_code == 200, amended.text

    entries = await _entries(db_session, test_tenant.id)
    assert [e.entry_type for e in entries] == ["session_close", "record_amendment"]
    close, amendment = entries
    assert amendment.seq == 2
    # The chain reads: closed at X, amended against X.
    assert amendment.prev_hash == close.chain_hash
    assert amendment.subject_id == uuid.UUID(record_data["id"])

    status = await verify_chain(db_session, test_tenant.id)
    assert status.valid is True
    assert status.length == 2


@pytest.mark.asyncio
async def test_a_correction_during_the_open_session_chains_nothing(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    member = await _add_member(db_session, test_tenant.id)
    now = datetime.now(UTC)
    created = await auth_client.post(
        "/api/v1/attendance/sessions",
        json={
            "title": "Training",
            "opens_at": (now - timedelta(hours=1)).isoformat(),
            "closes_at": (now + timedelta(hours=2)).isoformat(),
        },
    )
    record = await auth_client.post(
        f"/api/v1/attendance/sessions/{created.json()['data']['id']}/check-in",
        json={"member_id": str(member.id), "method": "manual"},
    )
    amended = await auth_client.patch(
        f"/api/v1/attendance/records/{record.json()['data']['id']}",
        json={"note": "sofort korrigiert", "reason": "Tippfehler"},
    )
    assert amended.status_code == 200

    # Level 0 audits it; the chain is for what happens after the freeze.
    assert await _entries(db_session, test_tenant.id) == []


@pytest.mark.asyncio
async def test_certificates_and_revocations_extend_the_chain(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    sport = Sport(key=f"shooting-{uuid.uuid4().hex[:6]}", name="Schießsport", modules=["shooting"])
    db_session.add(sport)
    await db_session.flush()
    db_session.add(TenantSport(tenant_id=test_tenant.id, sport_id=sport.id, is_primary=True))
    member = await _add_member(db_session, test_tenant.id)
    await db_session.flush()

    rule = await auth_client.post(
        "/api/v1/modules/shooting/rules",
        json={"rule_key": "dsb", "label": "Regel", "min_total_days": 1},
    )
    assert rule.status_code == 201

    issued = await auth_client.post(
        "/api/v1/modules/shooting/certificates",
        json={"member_id": str(member.id), "rule_key": "dsb", "as_of": "2026-08-04"},
    )
    assert issued.status_code == 201, issued.text
    certificate = issued.json()["data"]

    revoked = await auth_client.post(
        f"/api/v1/modules/shooting/certificates/{certificate['id']}/revoke",
        json={"reason": "Testlauf"},
    )
    assert revoked.status_code == 200

    entries = await _entries(db_session, test_tenant.id)
    assert [e.entry_type for e in entries] == ["certificate", "certificate_revoked"]
    assert entries[0].content_hash == certificate["content_hash"]
    assert entries[1].prev_hash == entries[0].chain_hash

    status = await verify_chain(db_session, test_tenant.id)
    assert status.valid is True


@pytest.mark.asyncio
async def test_tampering_breaks_the_chain_at_the_rewritten_link(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    await _create_closed_session(auth_client, db_session, test_tenant.id)
    await _create_closed_session(auth_client, db_session, test_tenant.id)
    await _create_closed_session(auth_client, db_session, test_tenant.id)

    entries = await _entries(db_session, test_tenant.id)
    assert len(entries) == 3
    # Rewrite history: link 2's content changes without its chain hash moving.
    entries[1].content_hash = "f" * 64
    await db_session.flush()

    status = await verify_chain(db_session, test_tenant.id)
    assert status.valid is False
    assert status.broken_at_seq == 2


@pytest.mark.asyncio
async def test_chain_status_endpoint(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    await _create_closed_session(auth_client, db_session, test_tenant.id)

    response = await auth_client.get("/api/v1/attendance/proof-chain/status")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["length"] == 1
    assert data["valid"] is True
    assert data["anchored_to_seq"] is None


@pytest.mark.asyncio
async def test_each_tenant_has_its_own_chain(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    other = Tenant(id=uuid.uuid4(), name="Other Club", slug="other-club")
    db_session.add(other)
    await db_session.flush()

    await _create_closed_session(auth_client, db_session, test_tenant.id)
    await append_entry(
        db_session,
        other.id,
        entry_type="session_close",
        subject_id=uuid.uuid4(),
        content_hash="a" * 64,
    )

    ours = await _entries(db_session, test_tenant.id)
    theirs = await _entries(db_session, other.id)
    assert [e.seq for e in ours] == [1]
    assert [e.seq for e in theirs] == [1]
    assert theirs[0].prev_hash == GENESIS_HASH


# --- TSA / anchoring ---


def test_timestamp_query_is_well_formed_der() -> None:
    chain_hash = "ab" * 32
    tsq = build_timestamp_query(chain_hash)
    assert len(tsq) == 59
    # SEQUENCE(57) / version 1 / messageImprint with the sha256 OID.
    assert tsq[:5] == bytes.fromhex("3039020101")
    assert bytes.fromhex("0609608648016503040201") in tsq
    assert tsq[-3:] == bytes.fromhex("0101ff")  # certReq TRUE
    assert hashlib.sha256(chain_hash.encode()).digest() in tsq


class _FakeTsa(TsaClient):
    def __init__(self, *, fail: bool = False) -> None:
        super().__init__("https://tsa.example/tsr")
        self.fail = fail
        self.calls: list[str] = []

    async def timestamp(self, chain_hash_hex: str) -> bytes:
        self.calls.append(chain_hash_hex)
        if self.fail:
            raise ValueError("TSA down")
        return b"token:" + chain_hash_hex.encode()


@pytest.mark.asyncio
async def test_anchoring_covers_the_head_and_then_rests(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    await _create_closed_session(auth_client, db_session, test_tenant.id)
    await _create_closed_session(auth_client, db_session, test_tenant.id)

    tsa = _FakeTsa()
    assert await anchor_once(db_session, tsa) == 1

    anchor = (
        await db_session.execute(
            select(ProofChainAnchor).where(ProofChainAnchor.tenant_id == test_tenant.id)
        )
    ).scalar_one()
    assert anchor.seq_to == 2
    assert anchor.tsa_token.startswith(b"token:")
    assert anchor.tsa_url == "https://tsa.example/tsr"

    # Nothing new happened — the head is covered, no second token is bought.
    assert await anchor_once(db_session, tsa) == 0
    assert len(tsa.calls) == 1

    # The chain grows, the next sweep anchors again.
    await _create_closed_session(auth_client, db_session, test_tenant.id)
    assert await anchor_once(db_session, tsa) == 1


@pytest.mark.asyncio
async def test_a_failing_tsa_leaves_the_chain_unanchored_not_broken(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    await _create_closed_session(auth_client, db_session, test_tenant.id)

    assert await anchor_once(db_session, _FakeTsa(fail=True)) == 0
    anchors = (
        (
            await db_session.execute(
                select(ProofChainAnchor).where(ProofChainAnchor.tenant_id == test_tenant.id)
            )
        )
        .scalars()
        .all()
    )
    assert anchors == []
