"""Tests for the dues API: fee types, assignments, assessment runs, payments.

Dues are financial records — tenant isolation and idempotency of the
assessment run are the critical invariants.
"""

import json
import uuid
from collections.abc import AsyncGenerator
from datetime import date

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.models.member import Member
from app.models.tenant import Tenant


async def _add_member(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    member_number: str = "M-001",
    joined_at: date = date(2024, 1, 1),
) -> Member:
    member = Member(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        member_number=member_number,
        first_name="Alice",
        last_name="Example",
        joined_at=joined_at,
        status="active",
    )
    session.add(member)
    await session.flush()
    return member


async def _create_fee_type(
    client: AsyncClient,
    *,
    name: str = "Erwachsene",
    amount: str = "120.00",
    interval: str = "yearly",
) -> dict:
    resp = await client.post(
        "/api/v1/dues/fee-types",
        json={"name": name, "amount": amount, "interval": interval},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


async def _assign_fee(
    client: AsyncClient,
    member_id: str,
    fee_type_id: str,
    *,
    valid_from: str = "2026-01-01",
    valid_to: str | None = None,
) -> dict:
    resp = await client.post(
        "/api/v1/dues/assignments",
        json={
            "member_id": member_id,
            "fee_type_id": fee_type_id,
            "valid_from": valid_from,
            "valid_to": valid_to,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


# --- Fee types ---


async def test_create_and_list_fee_types(auth_client: AsyncClient) -> None:
    created = await _create_fee_type(auth_client, name="Jugend", amount="60.00")
    assert created["name"] == "Jugend"
    assert created["amount"] == "60.00"
    assert created["interval"] == "yearly"

    resp = await auth_client.get("/api/v1/dues/fee-types")
    assert resp.status_code == 200
    names = [f["name"] for f in resp.json()["data"]]
    assert "Jugend" in names


async def test_create_fee_type_duplicate_name_conflict(auth_client: AsyncClient) -> None:
    await _create_fee_type(auth_client, name="Erwachsene")
    resp = await auth_client.post(
        "/api/v1/dues/fee-types",
        json={"name": "Erwachsene", "amount": "100.00", "interval": "yearly"},
    )
    assert resp.status_code == 409


async def test_create_fee_type_invalid_interval(auth_client: AsyncClient) -> None:
    resp = await auth_client.post(
        "/api/v1/dues/fee-types",
        json={"name": "X", "amount": "10.00", "interval": "weekly"},
    )
    assert resp.status_code == 422


async def test_update_fee_type(auth_client: AsyncClient) -> None:
    created = await _create_fee_type(auth_client)
    resp = await auth_client.patch(
        f"/api/v1/dues/fee-types/{created['id']}",
        json={"amount": "150.00", "is_active": False},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["amount"] == "150.00"
    assert resp.json()["data"]["is_active"] is False


async def test_delete_fee_type(auth_client: AsyncClient) -> None:
    created = await _create_fee_type(auth_client)
    resp = await auth_client.delete(f"/api/v1/dues/fee-types/{created['id']}")
    assert resp.status_code == 204

    resp = await auth_client.get("/api/v1/dues/fee-types?include_inactive=true")
    assert created["id"] not in [f["id"] for f in resp.json()["data"]]


async def test_fee_types_require_auth(anon_client: AsyncClient) -> None:
    resp = await anon_client.get("/api/v1/dues/fee-types")
    assert resp.status_code == 403


# --- Assignments ---


async def test_assign_fee_to_member(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    member = await _add_member(db_session, test_tenant.id)
    fee_type = await _create_fee_type(auth_client)
    assignment = await _assign_fee(auth_client, str(member.id), fee_type["id"])
    assert assignment["member_id"] == str(member.id)

    resp = await auth_client.get(f"/api/v1/dues/assignments?member_id={member.id}")
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 1


async def test_assign_fee_unknown_member(auth_client: AsyncClient) -> None:
    fee_type = await _create_fee_type(auth_client)
    resp = await auth_client.post(
        "/api/v1/dues/assignments",
        json={
            "member_id": str(uuid.uuid4()),
            "fee_type_id": fee_type["id"],
            "valid_from": "2026-01-01",
        },
    )
    assert resp.status_code == 404


async def test_assign_fee_invalid_validity_range(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    member = await _add_member(db_session, test_tenant.id)
    fee_type = await _create_fee_type(auth_client)
    resp = await auth_client.post(
        "/api/v1/dues/assignments",
        json={
            "member_id": str(member.id),
            "fee_type_id": fee_type["id"],
            "valid_from": "2026-06-01",
            "valid_to": "2026-01-01",
        },
    )
    assert resp.status_code == 422


# --- Assessment run ---


async def test_generate_dues_yearly(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    member = await _add_member(db_session, test_tenant.id)
    fee_type = await _create_fee_type(auth_client, amount="120.00", interval="yearly")
    await _assign_fee(auth_client, str(member.id), fee_type["id"])

    resp = await auth_client.post("/api/v1/dues/generate", json={"year": 2026})
    assert resp.status_code == 200
    assert resp.json()["data"]["created"] == 1

    resp = await auth_client.get("/api/v1/dues?year=2026")
    dues = resp.json()["data"]
    assert len(dues) == 1
    assert dues[0]["amount"] == "120.00"
    assert dues[0]["status"] == "open"
    assert dues[0]["fee_name"] == "Erwachsene"
    assert dues[0]["period_start"] == "2026-01-01"
    assert dues[0]["period_end"] == "2026-12-31"


async def test_generate_dues_is_idempotent(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    member = await _add_member(db_session, test_tenant.id)
    fee_type = await _create_fee_type(auth_client)
    await _assign_fee(auth_client, str(member.id), fee_type["id"])

    resp = await auth_client.post("/api/v1/dues/generate", json={"year": 2026})
    assert resp.json()["data"]["created"] == 1
    resp = await auth_client.post("/api/v1/dues/generate", json={"year": 2026})
    assert resp.json()["data"]["created"] == 0


async def test_generate_dues_quarterly_respects_validity(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    member = await _add_member(db_session, test_tenant.id)
    fee_type = await _create_fee_type(auth_client, interval="quarterly", amount="30.00")
    # Member joins mid-year: only Q3 + Q4 are assessed
    await _assign_fee(auth_client, str(member.id), fee_type["id"], valid_from="2026-07-15")

    resp = await auth_client.post("/api/v1/dues/generate", json={"year": 2026})
    assert resp.json()["data"]["created"] == 2

    resp = await auth_client.get("/api/v1/dues?year=2026")
    starts = sorted(d["period_start"] for d in resp.json()["data"])
    assert starts == ["2026-07-01", "2026-10-01"]


async def test_generate_dues_one_time_only_in_join_year(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    member = await _add_member(db_session, test_tenant.id)
    fee_type = await _create_fee_type(auth_client, name="Aufnahme", interval="one_time")
    await _assign_fee(auth_client, str(member.id), fee_type["id"], valid_from="2026-03-01")

    resp = await auth_client.post("/api/v1/dues/generate", json={"year": 2026})
    assert resp.json()["data"]["created"] == 1
    resp = await auth_client.post("/api/v1/dues/generate", json={"year": 2027})
    assert resp.json()["data"]["created"] == 0


async def test_generate_skips_inactive_fee_types(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    member = await _add_member(db_session, test_tenant.id)
    fee_type = await _create_fee_type(auth_client)
    await _assign_fee(auth_client, str(member.id), fee_type["id"])
    await auth_client.patch(f"/api/v1/dues/fee-types/{fee_type['id']}", json={"is_active": False})

    resp = await auth_client.post("/api/v1/dues/generate", json={"year": 2026})
    assert resp.json()["data"]["created"] == 0


# --- Payments / status ---


async def _generate_single_due(
    auth_client: AsyncClient, db_session: AsyncSession, tenant: Tenant
) -> dict:
    member = await _add_member(db_session, tenant.id)
    fee_type = await _create_fee_type(auth_client)
    await _assign_fee(auth_client, str(member.id), fee_type["id"])
    await auth_client.post("/api/v1/dues/generate", json={"year": 2026})
    resp = await auth_client.get("/api/v1/dues")
    return resp.json()["data"][0]


async def test_pay_due(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    due = await _generate_single_due(auth_client, db_session, test_tenant)
    resp = await auth_client.post(
        f"/api/v1/dues/{due['id']}/pay",
        json={"paid_at": "2026-02-01", "payment_method": "cash"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "paid"
    assert data["paid_at"] == "2026-02-01"
    assert data["payment_method"] == "cash"


async def test_pay_due_twice_conflict(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    due = await _generate_single_due(auth_client, db_session, test_tenant)
    await auth_client.post(f"/api/v1/dues/{due['id']}/pay", json={})
    resp = await auth_client.post(f"/api/v1/dues/{due['id']}/pay", json={})
    assert resp.status_code == 409


async def test_cancel_paid_due_conflict(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    due = await _generate_single_due(auth_client, db_session, test_tenant)
    await auth_client.post(f"/api/v1/dues/{due['id']}/pay", json={})
    resp = await auth_client.post(f"/api/v1/dues/{due['id']}/cancel")
    assert resp.status_code == 409


async def test_cancel_and_reopen_due(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    due = await _generate_single_due(auth_client, db_session, test_tenant)
    resp = await auth_client.post(f"/api/v1/dues/{due['id']}/cancel")
    assert resp.json()["data"]["status"] == "cancelled"
    resp = await auth_client.post(f"/api/v1/dues/{due['id']}/reopen")
    assert resp.json()["data"]["status"] == "open"
    assert resp.json()["data"]["paid_at"] is None


async def test_pay_unknown_due_not_found(auth_client: AsyncClient) -> None:
    resp = await auth_client.post(f"/api/v1/dues/{uuid.uuid4()}/pay", json={})
    assert resp.status_code == 404


async def test_summary(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    due = await _generate_single_due(auth_client, db_session, test_tenant)
    resp = await auth_client.get("/api/v1/dues/summary")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["open_count"] == 1
    assert data["open_amount"] == "120.00"

    await auth_client.post(f"/api/v1/dues/{due['id']}/pay", json={})
    resp = await auth_client.get("/api/v1/dues/summary")
    data = resp.json()["data"]
    assert data["open_count"] == 0
    assert data["paid_count"] == 1
    assert data["paid_amount"] == "120.00"


# --- SEPA export ---


async def _setup_sepa_creditor(db_session: AsyncSession, tenant: Tenant) -> None:
    tenant.iban = "DE02120300000000202051"
    tenant.bic = "BYLADEM1001"
    tenant.sepa_creditor_id = "DE98ZZZ09999999999"
    await db_session.flush()


async def _add_sepa_member(
    db_session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    member_number: str = "M-100",
) -> Member:
    member = await _add_member(db_session, tenant_id, member_number=member_number)
    member.iban = "DE02500105170137075030"
    member.bic = "INGDDEFF"
    member.sepa_mandate_reference = f"MNDT-{member_number}"
    member.sepa_mandate_date = date(2025, 1, 15)
    await db_session.flush()
    return member


async def test_sepa_export_requires_creditor_data(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    member = await _add_sepa_member(db_session, test_tenant.id)
    fee_type = await _create_fee_type(auth_client)
    await _assign_fee(auth_client, str(member.id), fee_type["id"])
    await auth_client.post("/api/v1/dues/generate", json={"year": 2026})

    resp = await auth_client.get("/api/v1/dues/sepa-export?year=2026")
    assert resp.status_code == 422


async def test_sepa_export_generates_xml(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    await _setup_sepa_creditor(db_session, test_tenant)
    member = await _add_sepa_member(db_session, test_tenant.id)
    fee_type = await _create_fee_type(auth_client, amount="120.00")
    await _assign_fee(auth_client, str(member.id), fee_type["id"])
    await auth_client.post("/api/v1/dues/generate", json={"year": 2026})

    resp = await auth_client.get("/api/v1/dues/sepa-export?year=2026")
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("application/xml")
    assert resp.headers["x-transaction-count"] == "1"
    xml = resp.text
    assert "pain.008.001.02" in xml
    assert "DE02500105170137075030" in xml
    assert "DE98ZZZ09999999999" in xml
    assert "MNDT-M-100" in xml
    assert '<InstdAmt Ccy="EUR">120.00</InstdAmt>' in xml


async def test_sepa_export_excludes_members_without_mandate(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    await _setup_sepa_creditor(db_session, test_tenant)
    # Member without bank data — their due must not be exported
    member = await _add_member(db_session, test_tenant.id, member_number="M-200")
    fee_type = await _create_fee_type(auth_client)
    await _assign_fee(auth_client, str(member.id), fee_type["id"])
    await auth_client.post("/api/v1/dues/generate", json={"year": 2026})

    resp = await auth_client.get("/api/v1/dues/sepa-export?year=2026")
    assert resp.status_code == 422


async def test_sepa_text_sanitization() -> None:
    from app.services.sepa import sanitize_sepa_text

    assert sanitize_sepa_text("Schützenverein Grün-Weiß") == "Schuetzenverein Gruen-Weiss"
    assert sanitize_sepa_text("A<B>&C") == "A B C"


# --- Tenant isolation ---


async def _build_client_for(
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> AsyncClient:
    import app.redis as redis_module
    from app.main import app

    async def override_db() -> AsyncGenerator[AsyncSession]:  # type: ignore[type-arg]
        yield db_session

    app.dependency_overrides[get_db_session] = override_db
    redis_module._redis_client = fake_redis

    token = uuid.uuid4().hex
    await fake_redis.set(
        f"session:{token}",
        json.dumps(
            {
                "user_id": str(user_id),
                "tenant_id": str(tenant_id),
                "role": "owner",
            }
        ),
        ex=604800,
    )
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={"unefy_session": token},
    )


async def test_dues_are_tenant_scoped(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    fake_redis,  # type: ignore[no-untyped-def]
) -> None:
    due = await _generate_single_due(auth_client, db_session, test_tenant)

    other_tenant = Tenant(id=uuid.uuid4(), name="Other Club", slug="other-club")
    db_session.add(other_tenant)
    await db_session.flush()

    other_client = await _build_client_for(db_session, fake_redis, uuid.uuid4(), other_tenant.id)
    try:
        resp = await other_client.get("/api/v1/dues")
        assert resp.json()["data"] == []

        resp = await other_client.post(f"/api/v1/dues/{due['id']}/pay", json={})
        assert resp.status_code == 404

        resp = await other_client.get("/api/v1/dues/fee-types")
        assert resp.json()["data"] == []
    finally:
        await other_client.aclose()
