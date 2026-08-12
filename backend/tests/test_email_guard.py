"""The switch that keeps a test system from writing to real members.

An installation holds real addresses long before anybody means to mail them.
One accidental round mail to three hundred people cannot be recalled, so the
default is that nothing goes out except the two mails somebody is actively
waiting for: the login link and the login code.

These tests are the guarantee. If one of them goes red, a club is about to be
mailed by a system that was only supposed to be tested.
"""

from typing import Any

import pytest

from app.config import Settings
from app.integrations.email import may_send, send_email
from app.services.magic_link import send_login_code


def settings_for(mode: str, allowlist: list[str] | None = None, smtp: bool = True) -> Settings:
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        DEBUG=True,
        EMAIL_DELIVERY=mode,
        EMAIL_ALLOWLIST=allowlist or [],
        SMTP_HOST="mail.example.org" if smtp else "",
    )


class Recorder:
    """Stands in for the mail server and remembers whether it was asked."""

    def __init__(self) -> None:
        self.sent: list[str] = []

    async def __call__(self, message: Any, **_: Any) -> None:
        self.sent.append(str(message["Subject"]))


@pytest.fixture
def smtp(monkeypatch: pytest.MonkeyPatch) -> Recorder:
    recorder = Recorder()
    monkeypatch.setattr("app.integrations.email.aiosmtplib.send", recorder)
    return recorder


# --- The rule ---


def test_the_default_holds_member_mail_back() -> None:
    """`auth_only` is the default so that forgetting the setting is the safe
    way round: an unconfigured install writes to nobody."""
    assert Settings(_env_file=None, DEBUG=True).EMAIL_DELIVERY == "auth_only"  # type: ignore[call-arg]


@pytest.mark.parametrize(
    ("mode", "category", "expected"),
    [
        ("auth_only", "auth", True),
        ("auth_only", "member", False),
        ("all", "auth", True),
        ("all", "member", True),
        # `none` is the position for "definitely nothing", so it also stops
        # the login mail — anyone flipping it has accepted that.
        ("none", "auth", False),
        ("none", "member", False),
    ],
)
def test_who_may_be_written_to(mode: str, category: str, expected: bool) -> None:
    assert (
        may_send(to="mitglied@example.org", category=category, settings=settings_for(mode))  # type: ignore[arg-type]
        is expected
    )


def test_an_allowlisted_address_still_receives_member_mail() -> None:
    """The way to test a round mail: against your own inbox and nobody else's."""
    settings = settings_for("auth_only", ["andreas@wdmr.de"])

    assert may_send(to="andreas@wdmr.de", category="member", settings=settings) is True
    assert may_send(to="mitglied@example.org", category="member", settings=settings) is False


def test_the_allowlist_can_name_a_whole_domain() -> None:
    settings = settings_for("auth_only", ["@wdmr.de"])

    assert may_send(to="andreas@wdmr.de", category="member", settings=settings) is True
    assert may_send(to="a@nicht-wdmr.de", category="member", settings=settings) is False


def test_the_allowlist_ignores_case_and_stray_spaces() -> None:
    """It is typed into an .env file by hand."""
    settings = settings_for("auth_only", [" Andreas@WDMR.de "])

    assert may_send(to="andreas@wdmr.de", category="member", settings=settings) is True


def test_the_allowlist_does_not_open_the_none_position() -> None:
    settings = settings_for("none", ["andreas@wdmr.de"])

    assert may_send(to="andreas@wdmr.de", category="member", settings=settings) is False


def test_an_empty_allowlist_entry_matches_nothing() -> None:
    """A trailing comma in the .env must not let everything through."""
    settings = settings_for("auth_only", ["", "  "])

    assert may_send(to="mitglied@example.org", category="member", settings=settings) is False


# --- What actually reaches the mail server ---


async def test_member_mail_never_reaches_the_server_by_default(smtp: Recorder) -> None:
    delivered = await send_email(
        to="mitglied@example.org",
        subject="Einladung zum Sommerfest",
        body="…",
        category="member",
        settings=settings_for("auth_only"),
    )

    assert delivered is False
    assert smtp.sent == [], "a member was mailed from a system that was holding mail back"


async def test_the_login_mail_goes_out_by_default(smtp: Recorder) -> None:
    """Nobody can test a system they cannot sign in to."""
    delivered = await send_email(
        to="andreas@wdmr.de",
        subject="Ihr Anmeldelink für unefy",
        body="…",
        category="auth",
        settings=settings_for("auth_only"),
    )

    assert delivered is True
    assert smtp.sent == ["Ihr Anmeldelink für unefy"]


async def test_the_login_code_path_still_sends(smtp: Recorder) -> None:
    """Through the real caller, not a hand-written one: the guarantee is that
    *this* flow keeps working, whatever the switch does to the rest."""
    await send_login_code("andreas@wdmr.de", "123456", settings_for("auth_only"))

    assert smtp.sent == ["123456 ist Ihr unefy-Anmeldecode"]


async def test_switching_to_all_lets_member_mail_through(smtp: Recorder) -> None:
    delivered = await send_email(
        to="mitglied@example.org",
        subject="Einladung zur Mitgliederversammlung",
        body="…",
        category="member",
        settings=settings_for("all"),
    )

    assert delivered is True
    assert smtp.sent == ["Einladung zur Mitgliederversammlung"]


async def test_none_stops_even_the_login_mail(smtp: Recorder) -> None:
    delivered = await send_email(
        to="andreas@wdmr.de",
        subject="Ihr Anmeldelink für unefy",
        body="…",
        category="auth",
        settings=settings_for("none"),
    )

    assert delivered is False
    assert smtp.sent == []


async def test_an_allowlisted_address_reaches_the_server(smtp: Recorder) -> None:
    delivered = await send_email(
        to="andreas@wdmr.de",
        subject="Testrundmail",
        body="…",
        category="member",
        settings=settings_for("auth_only", ["@wdmr.de"]),
    )

    assert delivered is True
    assert smtp.sent == ["Testrundmail"]


async def test_the_guard_runs_before_the_transport_check(smtp: Recorder) -> None:
    """Without SMTP_HOST the module logs the whole message, body included.

    For held-back mail it must not get that far: on a test system that is a
    log full of member mail nobody asked to keep.
    """
    delivered = await send_email(
        to="mitglied@example.org",
        subject="Einladung zum Sommerfest",
        body="…",
        category="member",
        settings=settings_for("auth_only", smtp=False),
    )

    assert delivered is False
