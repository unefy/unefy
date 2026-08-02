"""Guests in the attendance list.

A club has to know who was on the range, and not everyone there is a member —
supervision duty and insurance do not care about membership. What must stay
true is that a guest never counts towards anyone's §14 proof.
"""

import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.member import Member
from app.models.tenant import Tenant
from app.models.user import User

OPENS_AT = "2026-07-07T17:00:00+00:00"
CLOSES_AT = "2026-07-07T21:00:00+00:00"


async def _add_member(session: AsyncSession, tenant_id: uuid.UUID, **overrides: object) -> Member:
    member = Member(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        member_number=str(overrides.pop("member_number", "001")),
        first_name=str(overrides.pop("first_name", "Alice")),
        last_name="Example",
        joined_at=date(2024, 1, 1),
        status="active",
        **overrides,
    )
    session.add(member)
    await session.flush()
    return member


async def _create_session(client: AsyncClient) -> dict:
    resp = await client.post(
        "/api/v1/attendance/sessions",
        json={"title": "Übungsabend", "opens_at": OPENS_AT, "closes_at": CLOSES_AT},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


async def test_a_guest_can_be_checked_in_by_name(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    created = await _create_session(auth_client)

    resp = await auth_client.post(
        f"/api/v1/attendance/sessions/{created['id']}/check-in",
        json={"guest_name": "Jonas Gast"},
    )

    assert resp.status_code == 201, resp.text
    record = resp.json()["data"]
    assert record["member_id"] is None
    assert record["guest_name"] == "Jonas Gast"
    # Named for the supervisor's list, without inventing a member number.
    assert record["member_name"] == "Jonas Gast"
    assert record["member_number"] is None
    # A name on a list is the weakest proof there is, and the column says so.
    assert record["method"] == "manual"
    assert record["assurance"] == "low"


async def test_guests_appear_in_the_session_list_beside_members(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    """The join to members is an outer one, or guests vanish from the list.

    That is the failure worth guarding: an inner join drops them silently, and
    the list is exactly what a supervisor uses to know who is on the range.
    """
    member = await _add_member(db_session, test_tenant.id)
    created = await _create_session(auth_client)

    await auth_client.post(
        f"/api/v1/attendance/sessions/{created['id']}/check-in",
        json={"member_id": str(member.id)},
    )
    await auth_client.post(
        f"/api/v1/attendance/sessions/{created['id']}/check-in",
        json={"guest_name": "Jonas Gast"},
    )

    resp = await auth_client.get(f"/api/v1/attendance/sessions/{created['id']}/records")

    assert resp.status_code == 200
    names = [r["member_name"] for r in resp.json()["data"]]
    assert sorted(names) == ["Alice Example", "Jonas Gast"]
    # "None None" is what formatting an outer join's nulls produces.
    assert all(name and "None" not in name for name in names)


async def test_a_guest_never_reaches_a_member_history(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    """The §14 proof counts a member's own appointments and nobody else's."""
    member = await _add_member(db_session, test_tenant.id, user_id=test_user.id)
    created = await _create_session(auth_client)

    await auth_client.post(
        f"/api/v1/attendance/sessions/{created['id']}/check-in",
        json={"guest_name": "Jonas Gast"},
    )

    resp = await auth_client.get("/api/v1/attendance/me/records")

    assert resp.status_code == 200
    assert resp.json()["meta"]["total"] == 0, "a guest leaked into a member's history"
    assert member.id is not None


@pytest.mark.parametrize(
    ("payload", "reason"),
    [
        ({}, "neither a member nor a guest"),
        ({"guest_name": ""}, "an empty guest name"),
    ],
)
async def test_a_record_needs_exactly_one_subject(
    auth_client: AsyncClient, payload: dict, reason: str
) -> None:
    created = await _create_session(auth_client)

    resp = await auth_client.post(
        f"/api/v1/attendance/sessions/{created['id']}/check-in", json=payload
    )

    assert resp.status_code == 422, f"{reason}: {resp.text}"


async def test_both_a_member_and_a_guest_is_refused(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    # A contradiction about who was there, not a merge of two facts.
    member = await _add_member(db_session, test_tenant.id)
    created = await _create_session(auth_client)

    resp = await auth_client.post(
        f"/api/v1/attendance/sessions/{created['id']}/check-in",
        json={"member_id": str(member.id), "guest_name": "Jonas Gast"},
    )

    assert resp.status_code == 422, resp.text


async def test_two_guests_of_the_same_name_are_both_recorded(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    """Nothing about a guest identifies them well enough to refuse the second.

    Refusing would lose a real attendance to guard against a bookkeeping
    annoyance — the opposite of the trade the evidence layer wants.
    """
    created = await _create_session(auth_client)

    first = await auth_client.post(
        f"/api/v1/attendance/sessions/{created['id']}/check-in",
        json={"guest_name": "Jonas Gast"},
    )
    second = await auth_client.post(
        f"/api/v1/attendance/sessions/{created['id']}/check-in",
        json={"guest_name": "Jonas Gast"},
    )

    assert first.status_code == 201
    assert second.status_code == 201, second.text


async def test_a_member_still_cannot_be_checked_in_twice(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    # Guests being exempt from the duplicate rule must not have loosened it.
    member = await _add_member(db_session, test_tenant.id)
    created = await _create_session(auth_client)

    await auth_client.post(
        f"/api/v1/attendance/sessions/{created['id']}/check-in",
        json={"member_id": str(member.id)},
    )
    resp = await auth_client.post(
        f"/api/v1/attendance/sessions/{created['id']}/check-in",
        json={"member_id": str(member.id)},
    )

    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "ALREADY_CHECKED_IN"
