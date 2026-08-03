"""Change hints: ordering, filtering, and the failure modes that must stay quiet.

The ones that matter most are `test_the_hint_is_published_only_after_the_commit`
and `test_a_rejected_write_announces_nothing`. Get that ordering wrong and the bug
is a client that syncs on the hint, reads the pre-change state, and never hears
about the row again — no error, no failing request, just an app that is
occasionally one edit stale.
"""

import asyncio
import uuid
from datetime import date
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.events.outbox import (
    ChangeEvent,
    encode_sse,
    publish,
    queue_change,
    stream_key,
    take_pending,
)
from app.events.stream import event_stream
from app.models import Tenant
from app.models.member import Member
from app.repositories.member import MemberRepository
from app.schemas.member import MemberUpdate


async def _read_stream(redis: Any, tenant_id: uuid.UUID) -> list[dict[str, str]]:
    entries = await redis.xrange(stream_key(tenant_id))
    return [fields for _id, fields in entries]


async def _make_member(session: AsyncSession, tenant_id: uuid.UUID, number: str) -> Member:
    """Built through the ORM, not `BaseRepository.create`.

    `MemberCreate` carries no `member_number` — the service assigns it from the
    tenant's format — so the generic create path cannot make a valid member on its
    own. The create *announcement* is covered end to end through the HTTP endpoint
    below instead.
    """
    member = Member(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        member_number=number,
        first_name="Alice",
        last_name="Example",
        joined_at=date(2024, 1, 1),
        status="active",
    )
    session.add(member)
    await session.flush()
    return member


class TestOutboxOrdering:
    async def test_queuing_a_hint_does_not_publish_it(
        self,
        db_session: AsyncSession,
        test_tenant: Tenant,
        fake_redis: Any,
    ) -> None:
        """Queuing is not publishing — that separation is the whole point."""
        queue_change(
            db_session,
            tenant_id=test_tenant.id,
            entity="members",
            entity_id=uuid.uuid4(),
            op="upsert",
        )
        assert await _read_stream(fake_redis, test_tenant.id) == []

    async def test_taking_the_queue_empties_it(
        self,
        db_session: AsyncSession,
        test_tenant: Tenant,
    ) -> None:
        """Or a later request on a pooled session would republish this one's."""
        queue_change(
            db_session,
            tenant_id=test_tenant.id,
            entity="members",
            entity_id=uuid.uuid4(),
            op="upsert",
        )
        assert len(take_pending(db_session)) == 1
        assert take_pending(db_session) == []

    async def test_publish_writes_one_entry_per_event_in_order(
        self,
        test_tenant: Tenant,
        fake_redis: Any,
    ) -> None:
        first, second = uuid.uuid4(), uuid.uuid4()
        await publish(
            fake_redis,
            [
                ChangeEvent(test_tenant.id, "members", first, "upsert"),
                ChangeEvent(test_tenant.id, "members", second, "delete"),
            ],
        )

        entries = await _read_stream(fake_redis, test_tenant.id)
        assert [e["id"] for e in entries] == [str(first), str(second)]
        assert [e["op"] for e in entries] == ["upsert", "delete"]

    async def test_identical_hints_from_one_transaction_collapse_to_one_entry(
        self,
        test_tenant: Tenant,
        fake_redis: Any,
    ) -> None:
        """A row flushed several times in one transaction queues the same hint
        several times. One entry says everything the duplicates would; the extras
        only burn the stream's bounded history and fan out frames every client
        coalesces away anyway.
        """
        member_id = uuid.uuid4()
        duplicate = ChangeEvent(test_tenant.id, "members", member_id, "upsert")
        distinct = ChangeEvent(test_tenant.id, "members", member_id, "delete")

        await publish(fake_redis, [duplicate, duplicate, distinct, duplicate])

        entries = await _read_stream(fake_redis, test_tenant.id)
        assert [e["op"] for e in entries] == ["upsert", "delete"]

    async def test_a_redis_failure_never_reaches_the_caller(
        self,
        test_tenant: Tenant,
    ) -> None:
        """The write has already committed.

        There is nothing to undo and nothing the caller could do about it, so a
        Redis outage has to cost freshness rather than turn a successful write into
        an error response.
        """

        class BrokenRedis:
            def pipeline(self) -> "BrokenRedis":
                return self

            def xadd(self, *_a: object, **_k: object) -> None:
                raise ConnectionError("redis is gone")

            def expire(self, *_a: object, **_k: object) -> None:
                pass

            async def execute(self) -> None:
                pass

        await publish(
            BrokenRedis(),  # type: ignore[arg-type]
            [ChangeEvent(test_tenant.id, "members", uuid.uuid4(), "upsert")],
        )

    async def test_publishing_nothing_touches_nothing(
        self,
        test_tenant: Tenant,
        fake_redis: Any,
    ) -> None:
        await publish(fake_redis, [])
        assert await fake_redis.exists(stream_key(test_tenant.id)) == 0


class TestRepositoryAnnouncements:
    """The generic write path labels its own changes."""

    async def test_create_update_and_delete_each_queue_a_hint(
        self,
        db_session: AsyncSession,
        test_tenant: Tenant,
    ) -> None:
        """The create is caught too, though nothing asked for it.

        `_make_member` writes through the ORM directly, exactly as
        `MemberService.create` does. The flush listener sees it anyway, which is
        the property that makes collection complete rather than careful.
        """
        member = await _make_member(db_session, test_tenant.id, "001")
        repo = MemberRepository(db_session, test_tenant.id)

        await repo.update(member.id, MemberUpdate(last_name="Changed"))
        await repo.soft_delete(member.id)

        pending = take_pending(db_session)
        assert [(e.entity, e.op) for e in pending] == [
            ("members", "upsert"),
            ("members", "upsert"),
            ("members", "delete"),
        ]
        assert {e.entity_id for e in pending} == {member.id}

    async def test_a_bulk_delete_announces_every_id_it_was_given(
        self,
        db_session: AsyncSession,
        test_tenant: Tenant,
    ) -> None:
        """Announced per requested id, not per row actually hit.

        The UPDATE does not report which ids matched. A spurious hint costs a
        client one wasted delta sync; a missing one leaves a deleted member on
        screen indefinitely.
        """
        members = [await _make_member(db_session, test_tenant.id, f"{i:03d}") for i in range(2)]
        take_pending(db_session)  # discard the creates
        repo = MemberRepository(db_session, test_tenant.id)

        await repo.soft_delete_many([m.id for m in members])
        pending = take_pending(db_session)
        assert {e.entity_id for e in pending} == {m.id for m in members}
        assert all(e.op == "delete" for e in pending)

    async def test_a_model_outside_the_registry_announces_nothing(
        self,
        db_session: AsyncSession,
        test_tenant: Tenant,
    ) -> None:
        """Writing an unsynced model stays an ordinary write, not an error.

        Tenants, users, invitations and the discipline catalog are all outside the
        sync registry, and a base-class hook that raised on them would break every
        one of those write paths.
        """
        from app.repositories.catalog import MeasurementUnitRepository

        repo = MeasurementUnitRepository(db_session, test_tenant.id)
        repo._announce(uuid.uuid4(), "upsert")
        assert take_pending(db_session) == []


class TestCollectionThroughTheApi:
    """Collection, exercised through a real request and a real service."""

    async def test_a_create_through_the_api_queues_a_hint(
        self,
        auth_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """`MemberService.create` never touches `BaseRepository`.

        It builds the row itself so it can allocate a member number under a row
        lock. The flush listener catches it anyway — which is the whole reason
        collection is a listener and not a call per write path.
        """
        response = await auth_client.post(
            "/api/v1/members",
            json={
                "first_name": "Alice",
                "last_name": "Example",
                "joined_at": "2024-01-01",
            },
        )
        assert response.status_code in (200, 201), response.text
        created = response.json()["data"]["id"]

        pending = take_pending(db_session)
        assert [(e.entity, str(e.entity_id)) for e in pending] == [("members", created)]

    async def test_a_rejected_write_queues_nothing(
        self,
        auth_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Validation fails before any flush, so there is nothing to announce."""
        response = await auth_client.post("/api/v1/members", json={"first_name": "Alice"})
        assert response.status_code == 422
        assert take_pending(db_session) == []


class TestPublishOrdering:
    """The half of the design that must be published *after* the commit.

    Tested against `get_db_session` directly rather than through the HTTP client.
    The shared test fixture overrides that dependency with one that neither commits
    nor rolls back — by design, since every test runs inside a transaction that is
    always discarded — so a request-level test could not observe this ordering at
    all. Queuing a hint by hand needs no database write, which keeps this honest
    without touching the fixture everything else depends on.
    """

    async def test_a_successful_request_publishes_its_hints(
        self,
        test_tenant: Tenant,
        fake_redis: Any,
    ) -> None:
        import app.redis as redis_module
        from app.database import get_db_session

        original = redis_module._redis_client
        redis_module._redis_client = fake_redis
        try:
            gen = get_db_session()
            session = await anext(gen)
            queue_change(
                session,
                tenant_id=test_tenant.id,
                entity="members",
                entity_id=uuid.uuid4(),
                op="upsert",
            )
            with pytest.raises(StopAsyncIteration):
                await anext(gen)  # runs the commit, then the drain
        finally:
            redis_module._redis_client = original

        assert len(await _read_stream(fake_redis, test_tenant.id)) == 1

    async def test_a_failed_request_publishes_nothing(
        self,
        test_tenant: Tenant,
        fake_redis: Any,
    ) -> None:
        """No commit, no notification.

        Published anyway, every device in the club would sync in response to a
        change that was rolled back — and then never hear the truth, because
        nothing else is going to touch that row.
        """
        import app.redis as redis_module
        from app.database import get_db_session

        original = redis_module._redis_client
        redis_module._redis_client = fake_redis
        try:
            gen = get_db_session()
            session = await anext(gen)
            queue_change(
                session,
                tenant_id=test_tenant.id,
                entity="members",
                entity_id=uuid.uuid4(),
                op="upsert",
            )
            with pytest.raises(RuntimeError, match="handler blew up"):
                await gen.athrow(RuntimeError("handler blew up"))
        finally:
            redis_module._redis_client = original

        assert await _read_stream(fake_redis, test_tenant.id) == []


class TestSseFrames:
    def test_a_frame_carries_the_stream_id_as_its_event_id(self) -> None:
        """That identity is what makes Last-Event-ID resumption exact."""
        frame = encode_sse("1735900000000-0", {"entity": "members", "id": "abc", "op": "upsert"})
        assert frame.startswith("id: 1735900000000-0\n")
        assert "event: change\n" in frame
        assert frame.endswith("\n\n")

    def test_a_frame_carries_no_row_data(self) -> None:
        """A hint, not a delivery. See app/events/outbox.py for why."""
        frame = encode_sse("1-0", {"entity": "members", "id": "abc", "op": "upsert"})
        assert "iban" not in frame
        assert "last_name" not in frame


class TestEventStream:
    async def test_it_opens_immediately_and_then_delivers(
        self,
        test_tenant: Tenant,
        fake_redis: Any,
    ) -> None:
        """The first frame arrives before anything has changed.

        It flushes the response headers through any buffering proxy, and gives the
        client a positive "live" signal rather than a silence it cannot tell apart
        from a hang.
        """
        member_id = uuid.uuid4()
        await publish(fake_redis, [ChangeEvent(test_tenant.id, "members", member_id, "upsert")])

        gen = event_stream(fake_redis, test_tenant.id, last_event_id="0")
        try:
            opening = await anext(gen)
            change = await anext(gen)
        finally:
            await gen.aclose()

        assert opening.startswith(":")
        assert str(member_id) in change

    async def test_a_role_only_hears_about_what_it_may_sync(
        self,
        test_tenant: Tenant,
        fake_redis: Any,
    ) -> None:
        """One stream per tenant, several roles reading it.

        A plain member may sync events but not the member list, so the narrowing
        happens on the way out. Filtering at publish time instead would need one
        stream per role.
        """
        await publish(
            fake_redis,
            [
                ChangeEvent(test_tenant.id, "members", uuid.uuid4(), "upsert"),
                ChangeEvent(test_tenant.id, "events", uuid.uuid4(), "upsert"),
            ],
        )

        gen = event_stream(
            fake_redis, test_tenant.id, last_event_id="0", allowed=frozenset({"events"})
        )
        try:
            assert (await anext(gen)).startswith(":")
            frame = await anext(gen)
        finally:
            await gen.aclose()

        assert '"entity":"events"' in frame
        assert "members" not in frame

    async def test_an_event_published_between_two_reads_is_not_skipped(
        self,
        test_tenant: Tenant,
        fake_redis: Any,
    ) -> None:
        """The regression test for resuming from `$`.

        `$` re-resolves to "the newest id right now" on every `xread` call, so an
        event published in the gap between one read returning and the next being
        issued would land *behind* the freshly-resolved position and never be
        delivered. The generator is parked on its opening frame — after the start
        position was fixed, before any read — and the publish lands exactly in
        that gap.
        """
        await publish(fake_redis, [ChangeEvent(test_tenant.id, "members", uuid.uuid4(), "upsert")])

        gen = event_stream(fake_redis, test_tenant.id)
        try:
            assert (await anext(gen)).startswith(":")

            member_id = uuid.uuid4()
            await publish(fake_redis, [ChangeEvent(test_tenant.id, "members", member_id, "upsert")])
            # Bounded, so the failure mode is a red test and not a 25s heartbeat
            # wait: with `$` the frame never arrives.
            frame = await asyncio.wait_for(anext(gen), timeout=2)
        finally:
            await gen.aclose()

        assert str(member_id) in frame

    async def test_a_dead_redis_ends_the_stream_instead_of_raising(
        self,
        test_tenant: Tenant,
    ) -> None:
        """A 500 mid-stream is unhelpful — the client should reconnect instead."""

        class BrokenRedis:
            async def xread(self, *_a: object, **_k: object) -> None:
                raise ConnectionError("redis is gone")

        # A resumption cursor, so the failure is the mid-stream read — a redis
        # that is already dead at connection time ends before the opening frame.
        gen = event_stream(BrokenRedis(), test_tenant.id, last_event_id="0")  # type: ignore[arg-type]
        assert (await anext(gen)).startswith(":")
        with pytest.raises(StopAsyncIteration):
            await anext(gen)


class TestStreamRoute:
    """`GET /api/v1/stream` itself — auth and the connection cap.

    The generator's behaviour is covered above; these pin the two branches only
    the route owns: who may open a stream at all, and what a reconnect storm is
    told.
    """

    async def test_an_anonymous_caller_may_not_open_a_stream(
        self, anon_client: AsyncClient
    ) -> None:
        response = await anon_client.get("/api/v1/stream")
        assert response.status_code == 403

    async def test_an_authenticated_caller_gets_an_event_stream(
        self, auth_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Auth, headers and the glue — the generator itself is pinned above.

        The real stream never ends and the test transport buffers the whole
        body before handing it over, so a bounded stand-in stream is
        substituted; what this pins is the route, not the generator.
        """
        import app.api.v1.stream as stream_route

        async def one_frame(*_a: object, **_k: object):
            yield ": open\n\n"

        monkeypatch.setattr(stream_route, "event_stream", one_frame)

        response = await auth_client.get("/api/v1/stream")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert response.text.startswith(": open")

    async def test_the_per_user_cap_answers_429(
        self,
        auth_client: AsyncClient,
        test_tenant: Tenant,
        fake_redis: Any,
    ) -> None:
        """The backstop against a reconnect storm from a buggy client."""
        from app.api.v1.auth import get_session_data
        from app.api.v1.stream import MAX_STREAMS_PER_USER, _claim_slot

        session_token = auth_client.cookies["unefy_session"]
        data = await get_session_data(session_token)
        assert data is not None
        for _ in range(MAX_STREAMS_PER_USER):
            await _claim_slot(test_tenant.id, data.user_id, uuid.uuid4().hex)

        response = await auth_client.get("/api/v1/stream")
        assert response.status_code == 429
        assert response.json()["error"]["code"] == "TOO_MANY_STREAMS"
