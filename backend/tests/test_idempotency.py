"""Phase 3: idempotency and conflicts, all three mechanisms.

Client-assigned check-in ids (a retry is not two guests), the
`Idempotency-Key` header (a retry is not two executions), and
`If-Match`/ETag (a stale write is a 412 with the current state, not a silent
overwrite). Each is additive: without the id, the header or the precondition,
every request behaves exactly as before.
"""

import uuid
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Tenant
from app.models.attendance import AttendanceRecord
from app.models.member import Member

OPENS_AT = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
CLOSES_AT = (datetime.now(UTC) + timedelta(hours=3)).isoformat()


async def _create_session(client: AsyncClient) -> str:
    resp = await client.post(
        "/api/v1/attendance/sessions",
        json={"title": "Übungsabend", "opens_at": OPENS_AT, "closes_at": CLOSES_AT},
    )
    assert resp.status_code == 201, resp.text
    return str(resp.json()["data"]["id"])


async def _record_count(session: AsyncSession) -> int:
    result = await session.execute(select(func.count()).select_from(AttendanceRecord))
    return result.scalar_one()


class TestClientAssignedCheckInIds:
    async def test_a_replayed_guest_check_in_is_one_guest(
        self,
        auth_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """The reason the field exists. Guests are deliberately not deduplicated
        by content — nothing identifies them well enough — so a drained queue
        that retries after a dropped response used to book the guest twice."""
        session_id = await _create_session(auth_client)
        body = {"id": str(uuid.uuid4()), "guest_name": "Gast Gundula"}

        first = await auth_client.post(
            f"/api/v1/attendance/sessions/{session_id}/check-in", json=body
        )
        second = await auth_client.post(
            f"/api/v1/attendance/sessions/{session_id}/check-in", json=body
        )

        assert first.status_code == 201, first.text
        assert second.status_code == 201, second.text
        assert first.json()["data"]["id"] == second.json()["data"]["id"]
        assert await _record_count(db_session) == 1

    async def test_two_guests_of_the_same_name_stay_two(
        self,
        auth_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """The key distinguishes a retry from two real guests — it must never
        start identifying people by name."""
        session_id = await _create_session(auth_client)

        for _ in range(2):
            resp = await auth_client.post(
                f"/api/v1/attendance/sessions/{session_id}/check-in",
                json={"id": str(uuid.uuid4()), "guest_name": "Gast Gundula"},
            )
            assert resp.status_code == 201, resp.text

        assert await _record_count(db_session) == 2

    async def test_a_replayed_member_check_in_is_a_retry_not_a_conflict(
        self,
        auth_client: AsyncClient,
        db_session: AsyncSession,
        test_tenant: Tenant,
    ) -> None:
        """`ALREADY_CHECKED_IN` means somebody tried to check a member in twice.
        A replay of the *same* request is the queue succeeding — dressing that
        up as a conflict would make every flaky connection look like an error."""
        member = Member(
            id=uuid.uuid4(),
            tenant_id=test_tenant.id,
            member_number="777",
            first_name="Retry",
            last_name="Fall",
            joined_at=datetime.now(UTC).date(),
            status="active",
        )
        db_session.add(member)
        await db_session.flush()

        session_id = await _create_session(auth_client)
        body = {"id": str(uuid.uuid4()), "member_id": str(member.id)}

        first = await auth_client.post(
            f"/api/v1/attendance/sessions/{session_id}/check-in", json=body
        )
        replay = await auth_client.post(
            f"/api/v1/attendance/sessions/{session_id}/check-in", json=body
        )
        fresh = await auth_client.post(
            f"/api/v1/attendance/sessions/{session_id}/check-in",
            json={"member_id": str(member.id)},
        )

        assert first.status_code == 201, first.text
        assert replay.status_code == 201, replay.text
        assert fresh.status_code == 409
        assert fresh.json()["error"]["code"] == "ALREADY_CHECKED_IN"
        assert await _record_count(db_session) == 1


class TestIdempotencyKeyHeader:
    async def test_a_replay_returns_the_stored_response_without_executing(
        self,
        auth_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        session_id = await _create_session(auth_client)
        headers = {"Idempotency-Key": "drain-42"}
        body = {"guest_name": "Kein Client-Key"}

        first = await auth_client.post(
            f"/api/v1/attendance/sessions/{session_id}/check-in", json=body, headers=headers
        )
        replay = await auth_client.post(
            f"/api/v1/attendance/sessions/{session_id}/check-in", json=body, headers=headers
        )

        assert first.status_code == 201, first.text
        assert replay.status_code == 201
        assert replay.headers.get("idempotency-replayed") == "true"
        assert replay.json() == first.json()
        assert await _record_count(db_session) == 1

    async def test_the_same_key_with_a_different_body_is_refused(
        self,
        auth_client: AsyncClient,
    ) -> None:
        """A key is one intent. Answering a different body with somebody's
        stored response would be worse than any duplicate."""
        session_id = await _create_session(auth_client)
        headers = {"Idempotency-Key": "drain-43"}

        first = await auth_client.post(
            f"/api/v1/attendance/sessions/{session_id}/check-in",
            json={"guest_name": "Erste"},
            headers=headers,
        )
        other = await auth_client.post(
            f"/api/v1/attendance/sessions/{session_id}/check-in",
            json={"guest_name": "Zweite"},
            headers=headers,
        )

        assert first.status_code == 201
        assert other.status_code == 422
        assert other.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"

    async def test_without_the_header_nothing_changes(
        self,
        auth_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        session_id = await _create_session(auth_client)
        body = {"guest_name": "Ohne Netz"}

        for _ in range(2):
            resp = await auth_client.post(
                f"/api/v1/attendance/sessions/{session_id}/check-in", json=body
            )
            assert resp.status_code == 201

        assert await _record_count(db_session) == 2


class TestIfMatch:
    async def _create_member(self, client: AsyncClient) -> dict:
        resp = await client.post(
            "/api/v1/members",
            json={"first_name": "Etag", "last_name": "Probe", "joined_at": "2024-01-01"},
        )
        assert resp.status_code == 201, resp.text
        return dict(resp.json()["data"])

    async def test_the_detail_read_carries_an_etag(self, auth_client: AsyncClient) -> None:
        member = await self._create_member(auth_client)

        resp = await auth_client.get(f"/api/v1/members/{member['id']}")

        assert resp.status_code == 200
        assert resp.headers.get("etag", "").startswith('"')

    async def test_a_stale_write_answers_412_with_the_current_state(
        self,
        auth_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """The 412 carries the server's current representation, so the client
        can offer a merge in one round trip instead of two.

        The intervening edit is written with an explicit `updated_at`:
        `func.now()` is the *transaction* timestamp, so inside one test
        transaction a real PATCH would not move the ETag and the staleness this
        test exists for could never occur (see tests/test_sync.py for the same
        device).
        """
        member = await self._create_member(auth_client)
        detail = await auth_client.get(f"/api/v1/members/{member['id']}")
        etag = detail.headers["etag"]

        await db_session.execute(
            update(Member)
            .where(Member.id == uuid.UUID(member["id"]))
            .values(
                last_name="Zwischenzeitlich",
                updated_at=datetime.now(UTC) + timedelta(seconds=1),
            )
        )
        await db_session.flush()

        stale = await auth_client.patch(
            f"/api/v1/members/{member['id']}",
            json={"last_name": "Verspätet"},
            headers={"If-Match": etag},
        )

        assert stale.status_code == 412, stale.text
        body = stale.json()
        assert body["error"]["code"] == "PRECONDITION_FAILED"
        assert body["details"][0]["current"]["last_name"] == "Zwischenzeitlich"

    async def test_a_fresh_etag_writes_normally(self, auth_client: AsyncClient) -> None:
        member = await self._create_member(auth_client)
        detail = await auth_client.get(f"/api/v1/members/{member['id']}")

        resp = await auth_client.patch(
            f"/api/v1/members/{member['id']}",
            json={"last_name": "Aktuell"},
            headers={"If-Match": detail.headers["etag"]},
        )

        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["last_name"] == "Aktuell"

    async def test_without_if_match_last_write_wins_as_before(
        self,
        auth_client: AsyncClient,
    ) -> None:
        member = await self._create_member(auth_client)

        resp = await auth_client.patch(
            f"/api/v1/members/{member['id']}", json={"last_name": "Einfach so"}
        )

        assert resp.status_code == 200
