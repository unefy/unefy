"""Push registration, the FCM sender, and the fan-out.

The properties worth pinning are the quiet failure modes: a register endpoint
that answers 500 instead of a named 503 on an unconfigured server, a dead
token that keeps getting paid for, a burst that sends thirty wake-ups where
one would do, and a wake-up sent to a role the sync endpoint would refuse.
"""

import uuid
from contextlib import asynccontextmanager
from typing import Any

import httpx
import pytest
import respx
from httpx import AsyncClient, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.events.push_fanout import GROUP, _handle
from app.integrations.push import FcmSender
from app.models import PushDevice, Tenant
from app.repositories.push_device import PushDeviceRepository

DEVICES = "/api/v1/push/devices"
UNREGISTER = "/api/v1/push/devices/unregister"
TOKEN = "fcm-token-0123456789abcdef-0123456789abcdef"


@pytest.fixture
def push_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Flips the cached settings to 'configured'. The file path only has to be
    truthy for the endpoints — nothing in these tests constructs credentials
    from it."""
    settings = get_settings()
    monkeypatch.setattr(settings, "PUSH_ENABLED", True)
    monkeypatch.setattr(settings, "FCM_CREDENTIALS_FILE", "configured-in-test")


async def _count(session: AsyncSession) -> int:
    return (await session.execute(select(func.count()).select_from(PushDevice))).scalar_one()


class TestRegistration:
    async def test_registering_stores_the_callers_tenant_and_role(
        self,
        auth_client: AsyncClient,
        db_session: AsyncSession,
        test_tenant: Tenant,
        push_enabled: None,
    ) -> None:
        response = await auth_client.post(DEVICES, json={"token": TOKEN, "platform": "android"})

        assert response.status_code == 200, response.text
        row = (await db_session.execute(select(PushDevice))).scalar_one()
        assert row.tenant_id == test_tenant.id
        assert row.role == "owner"
        assert row.platform == "android"

    async def test_reregistering_refreshes_instead_of_duplicating(
        self,
        auth_client: AsyncClient,
        db_session: AsyncSession,
        push_enabled: None,
    ) -> None:
        """`onNewToken` and every app open land here — the row must move, not
        multiply, or every wake-up fans out to ghosts."""
        assert (await auth_client.post(DEVICES, json={"token": TOKEN})).status_code == 200
        assert (await auth_client.post(DEVICES, json={"token": TOKEN})).status_code == 200

        assert await _count(db_session) == 1

    async def test_a_device_moving_to_another_account_moves_its_row(
        self,
        auth_client: AsyncClient,
        db_session: AsyncSession,
        test_tenant: Tenant,
        push_enabled: None,
    ) -> None:
        """Same token, new owner: the old club must not keep waking a phone
        that signed into a different account."""
        assert (await auth_client.post(DEVICES, json={"token": TOKEN})).status_code == 200

        other_user = uuid.uuid4()
        await PushDeviceRepository(db_session).upsert(
            tenant_id=test_tenant.id,
            user_id=other_user,
            token=TOKEN,
            platform="android",
            role="member",
        )

        row = (await db_session.execute(select(PushDevice))).scalar_one()
        assert row.user_id == other_user
        assert row.role == "member"

    async def test_unregistering_removes_the_row_and_is_idempotent(
        self,
        auth_client: AsyncClient,
        db_session: AsyncSession,
        push_enabled: None,
    ) -> None:
        assert (await auth_client.post(DEVICES, json={"token": TOKEN})).status_code == 200

        assert (await auth_client.post(UNREGISTER, json={"token": TOKEN})).status_code == 204
        assert await _count(db_session) == 0
        # Absence is the goal, so asking twice is not an error.
        assert (await auth_client.post(UNREGISTER, json={"token": TOKEN})).status_code == 204

    async def test_an_unconfigured_server_answers_a_named_503(
        self,
        auth_client: AsyncClient,
    ) -> None:
        """Self-hosted without a Firebase project is healthy, not broken. The
        client reads the code and stops asking for the session."""
        for path in (DEVICES, UNREGISTER):
            response = await auth_client.post(path, json={"token": TOKEN})
            assert response.status_code == 503, response.text
            assert response.json()["error"]["code"] == "PUSH_DISABLED"

    async def test_an_anonymous_caller_may_not_register(
        self,
        anon_client: AsyncClient,
        push_enabled: None,
    ) -> None:
        assert (await anon_client.post(DEVICES, json={"token": TOKEN})).status_code == 403

    async def test_a_short_token_is_rejected(
        self,
        auth_client: AsyncClient,
        push_enabled: None,
    ) -> None:
        assert (await auth_client.post(DEVICES, json={"token": "short"})).status_code == 422


class _FakeCredentials:
    """google-auth's surface, minus the RSA key a test has no business owning."""

    valid = True
    token = "an-oauth2-token"
    project_id = "unefy-test"

    def refresh(self, _request: object) -> None:  # pragma: no cover - valid stays True
        raise AssertionError("refresh must not run while the token is valid")


def _sender() -> FcmSender:
    return FcmSender(settings=get_settings(), credentials=_FakeCredentials())


FCM_URL = "https://fcm.googleapis.com/v1/projects/unefy-test/messages:send"


class TestFcmSender:
    @respx.mock
    async def test_a_wakeup_carries_only_tenant_and_entity(self) -> None:
        """The payload is the whole privacy story: ids, never content."""
        route = respx.post(FCM_URL).mock(return_value=Response(200, json={"name": "m/1"}))
        sender = _sender()

        alive = await sender.send_wakeup(TOKEN, tenant_id="t-1", entity="members")
        await sender.aclose()

        assert alive is True
        body = route.calls.last.request.read().replace(b" ", b"")
        assert b'"data":{"tenant_id":"t-1","entity":"members"}' in body
        assert b'"priority":"high"' in body

    @respx.mock
    async def test_a_gone_install_is_reported_dead(self) -> None:
        respx.post(FCM_URL).mock(
            return_value=Response(404, json={"error": {"status": "NOT_FOUND"}})
        )
        sender = _sender()

        assert await sender.send_wakeup(TOKEN, tenant_id="t", entity="events") is False
        await sender.aclose()

    @respx.mock
    async def test_an_unregistered_token_is_reported_dead(self) -> None:
        respx.post(FCM_URL).mock(
            return_value=Response(400, json={"error": {"details": [{"errorCode": "UNREGISTERED"}]}})
        )
        sender = _sender()

        assert await sender.send_wakeup(TOKEN, tenant_id="t", entity="events") is False
        await sender.aclose()

    @respx.mock
    async def test_a_network_failure_neither_raises_nor_kills_the_token(self) -> None:
        """The write already committed; Google being down costs freshness only —
        and a token must never be dropped for a transport error."""
        respx.post(FCM_URL).mock(side_effect=httpx.ConnectError("down"))
        sender = _sender()

        assert await sender.send_wakeup(TOKEN, tenant_id="t", entity="events") is True
        await sender.aclose()


class _RecordingSender:
    """Stands in for [FcmSender]: wake-ups become a list, dead tokens a set."""

    def __init__(self, dead: set[str] | None = None) -> None:
        self.dead = dead or set()
        self.sent: list[tuple[str, str]] = []

    async def send_wakeup(self, token: str, *, tenant_id: str, entity: str) -> bool:
        self.sent.append((token, entity))
        return token not in self.dead

    async def aclose(self) -> None:  # pragma: no cover - nothing to close
        pass


class TestFanout:
    @pytest.fixture
    def factory(self, db_session: AsyncSession) -> Any:
        """Hands the fan-out the test's transaction. `commit` flushes instead —
        the tests share one database, and a real commit would leak rows past
        this test's rollback."""
        session = db_session

        class NonCommitting:
            def __getattr__(self, name: str) -> Any:
                return getattr(session, name)

            async def commit(self) -> None:
                await session.flush()

        @asynccontextmanager
        async def open_session() -> Any:
            yield NonCommitting()

        return open_session

    async def _register(
        self, session: AsyncSession, tenant_id: uuid.UUID, token: str, role: str
    ) -> None:
        await PushDeviceRepository(session).upsert(
            tenant_id=tenant_id,
            user_id=uuid.uuid4(),
            token=token,
            platform="android",
            role=role,
        )

    async def test_a_burst_wakes_each_club_once(
        self,
        db_session: AsyncSession,
        test_tenant: Tenant,
        fake_redis: Any,
        factory: Any,
    ) -> None:
        await self._register(db_session, test_tenant.id, TOKEN, "owner")
        sender = _RecordingSender()
        hint = {"entity": "events", "id": "x", "op": "upsert"}

        for _ in range(5):
            await _handle(fake_redis, sender, str(test_tenant.id), hint, factory)

        assert len(sender.sent) == 1

    async def test_only_roles_that_may_sync_the_entity_are_woken(
        self,
        db_session: AsyncSession,
        test_tenant: Tenant,
        fake_redis: Any,
        factory: Any,
    ) -> None:
        """Waking a plain member for a member-list edit is a push for a sync
        the server then refuses."""
        await self._register(db_session, test_tenant.id, "board-" + TOKEN, "board")
        await self._register(db_session, test_tenant.id, "member-" + TOKEN, "member")
        sender = _RecordingSender()

        await _handle(fake_redis, sender, str(test_tenant.id), {"entity": "members"}, factory)
        tokens_for_members = {token for token, _ in sender.sent}

        await fake_redis.delete(f"push:sent:{test_tenant.id}")
        await _handle(fake_redis, sender, str(test_tenant.id), {"entity": "events"}, factory)
        tokens_for_events = {token for token, _ in sender.sent} - tokens_for_members

        assert tokens_for_members == {"board-" + TOKEN}
        assert "member-" + TOKEN in tokens_for_events

    async def test_a_dead_token_is_dropped(
        self,
        db_session: AsyncSession,
        test_tenant: Tenant,
        fake_redis: Any,
        factory: Any,
    ) -> None:
        await self._register(db_session, test_tenant.id, TOKEN, "owner")
        sender = _RecordingSender(dead={TOKEN})

        await _handle(fake_redis, sender, str(test_tenant.id), {"entity": "events"}, factory)

        assert await _count(db_session) == 0

    async def test_an_unknown_entity_wakes_nobody(
        self,
        db_session: AsyncSession,
        test_tenant: Tenant,
        fake_redis: Any,
        factory: Any,
    ) -> None:
        """The stream carries hints for whatever the server knows; the fan-out
        must not guess roles for a collection it cannot look up."""
        await self._register(db_session, test_tenant.id, TOKEN, "owner")
        sender = _RecordingSender()

        await _handle(fake_redis, sender, str(test_tenant.id), {"entity": "audit-log"}, factory)

        assert sender.sent == []

    async def test_two_consumers_split_the_stream_instead_of_doubling_it(
        self,
        test_tenant: Tenant,
        fake_redis: Any,
    ) -> None:
        """The property the consumer group buys: several workers, each entry
        owned by exactly one of them."""
        key = f"unefy:events:{test_tenant.id}"
        for i in range(4):
            await fake_redis.xadd(key, {"entity": "events", "id": str(i)})
        await fake_redis.xgroup_create(key, GROUP, id="0")

        first = await fake_redis.xreadgroup(GROUP, "worker-1", {key: ">"}, count=2)
        second = await fake_redis.xreadgroup(GROUP, "worker-2", {key: ">"}, count=10)

        ids_first = {entry_id for _, entries in first for entry_id, _ in entries}
        ids_second = {entry_id for _, entries in second for entry_id, _ in entries}
        assert len(ids_first) == 2
        assert len(ids_second) == 2
        assert ids_first.isdisjoint(ids_second)
