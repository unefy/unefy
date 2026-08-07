"""What `get_db_session` writes to the log when a request fails.

The session wrapper is the outermost thing around a request, so every exception
passes through it — including the ones that are not errors at all. A request
without a session raises `ForbiddenError` and is answered with a 403; that is
the system working. It used to be logged as `database_session_error`, at ERROR,
with a full traceback, which made the log unusable for finding actual database
failures.

The fake session keeps this off a real connection: the only thing under test is
which branch runs, and that is decided before any I/O.
"""

from typing import Any
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import ForbiddenError, NotFoundError
from app.database import get_db_session


class FakeSession:
    """Records commit/rollback. Enough surface for `get_db_session`."""

    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False
        # Where the outbox parks change hints; empty means nothing to publish,
        # so the success path stops before it reaches Redis.
        self.info: dict[str, Any] = {}

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


class FakeSessionFactory:
    def __init__(self, session: FakeSession) -> None:
        self._session = session

    def __call__(self) -> "FakeSessionFactory":
        return self

    async def __aenter__(self) -> FakeSession:
        return self._session

    async def __aexit__(self, *args: Any) -> bool:
        return False


@pytest.fixture
def fake_session(monkeypatch: pytest.MonkeyPatch) -> FakeSession:
    session = FakeSession()
    monkeypatch.setattr("app.database.async_session_factory", FakeSessionFactory(session))
    return session


@pytest.fixture
def spy_logger(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    logger = MagicMock()
    monkeypatch.setattr("app.database.logger", logger)
    return logger


@pytest.mark.parametrize(
    "error",
    [
        ForbiddenError("No valid authentication provided"),
        NotFoundError("Member not found"),
    ],
    ids=["forbidden", "not_found"],
)
async def test_expected_app_errors_are_not_logged_as_database_errors(
    fake_session: FakeSession,
    spy_logger: MagicMock,
    error: Exception,
) -> None:
    gen = get_db_session()
    await gen.asend(None)

    with pytest.raises(type(error)):
        await gen.athrow(error)

    spy_logger.exception.assert_not_called()
    # The rollback is not optional just because the error was expected.
    assert fake_session.rolled_back is True
    assert fake_session.committed is False


async def test_unexpected_errors_are_still_logged(
    fake_session: FakeSession,
    spy_logger: MagicMock,
) -> None:
    gen = get_db_session()
    await gen.asend(None)

    with pytest.raises(RuntimeError):
        await gen.athrow(RuntimeError("connection reset"))

    spy_logger.exception.assert_called_once_with("database_session_error")
    assert fake_session.rolled_back is True


async def test_successful_request_commits_and_logs_nothing(
    fake_session: FakeSession,
    spy_logger: MagicMock,
) -> None:
    gen = get_db_session()
    await gen.asend(None)

    with pytest.raises(StopAsyncIteration):
        await gen.asend(None)

    assert fake_session.committed is True
    assert fake_session.rolled_back is False
    spy_logger.exception.assert_not_called()
