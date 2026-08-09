"""The production stack must be able to start.

Two settings were forwarded nowhere — `ATTENDANCE_SECRET`, which the validator
requires outside DEBUG, and the whole `SMTP_*` block. The first stopped the
backend from booting at all, the second silently turned every login code into
a log line. Both were invisible until someone deployed.

So this reads the deployment files as an operator would use them and asserts
the result is a configuration that actually validates. No database, no
containers — just the files.
"""

import os
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from app.config import Settings

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = REPO_ROOT / "docker-compose.prod.yml"
ENV_EXAMPLE = REPO_ROOT / ".env.prod.example"

#: `${VAR}` or `${VAR:-default}`.
_INTERPOLATION = re.compile(r"\$\{([A-Z0-9_]+)(?::-(.*?))?\}")

#: Long enough for MIN_SECRET_LENGTH, recognisable in a failure message.
_DUMMY_SECRET = "dummy-secret-for-the-config-test-0123456789"


def _backend_environment() -> dict[str, str]:
    compose: dict[str, Any] = yaml.safe_load(COMPOSE_FILE.read_text())
    environment = compose["services"]["backend"]["environment"]
    return {str(k): "" if v is None else str(v) for k, v in environment.items()}


def _example_keys() -> set[str]:
    keys = set()
    for line in ENV_EXAMPLE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        keys.add(line.split("=", 1)[0].strip())
    return keys


def _render(value: str) -> str:
    """Resolve compose interpolation the way `docker compose` would.

    A variable with a default takes the default (nothing in the operator's
    .env). One without gets a dummy, because the operator is required to
    supply it — whether the example file says so is a separate test.
    """

    def substitute(match: re.Match[str]) -> str:
        name, default = match.group(1), match.group(2)
        if default is not None:
            return default
        if name.endswith("SECRET") or name.endswith("PASSWORD"):
            return _DUMMY_SECRET
        return f"dummy-{name.lower()}"

    return _INTERPOLATION.sub(substitute, value)


def test_backend_settings_validate_with_what_compose_forwards(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The container's environment must produce a valid Settings object.

    This is the test that would have caught the missing ATTENDANCE_SECRET:
    DEBUG is "false" in the compose file, and the validator rejects any of the
    four secrets left at its placeholder.
    """
    for key in list(os.environ):
        if key.isupper():
            monkeypatch.delenv(key, raising=False)
    for key, raw in _backend_environment().items():
        monkeypatch.setenv(key, _render(raw))

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.DEBUG is False, "the production stack must not run in DEBUG"
    # Parsed, not merely present: GOOGLE_MOBILE_CLIENT_IDS is a list, and its
    # compose default has to be valid JSON or the container dies on startup.
    assert settings.GOOGLE_MOBILE_CLIENT_IDS == []


def test_every_required_variable_is_in_the_example_file() -> None:
    """`cp .env.prod.example .env` must yield a complete file.

    A variable the compose file interpolates without a default has to be
    supplied by the operator — so it needs a line in the example, or they can
    only discover it from a crash.
    """
    required = {
        name
        for raw in _backend_environment().values()
        for name, default in _INTERPOLATION.findall(raw)
        if not default
    }
    missing = sorted(required - _example_keys())
    assert not missing, f"required but absent from .env.prod.example: {missing}"


#: Variables in the example that configure the stack around the backend rather
#: than the backend itself, so their absence from its environment is correct.
_INFRASTRUCTURE_ONLY = {
    "IMAGE_TAG",
    "WEB_PORT",
    "API_PORT",
    # Reaches the backend inside DATABASE_URL, not as a key of its own.
    "POSTGRES_PASSWORD",
}


def test_every_documented_variable_reaches_the_backend() -> None:
    """The example file is a promise; a setting listed there must have effect.

    This is the inverse of the test above and the one that catches the sort of
    gap SMTP and COOKIE_DOMAIN both were: documented, filled in by the
    operator, and then quietly dropped because no line forwarded it.
    """
    forwarded = "\n".join(_backend_environment().values())
    documented = _example_keys() - _INFRASTRUCTURE_ONLY
    ignored = sorted(name for name in documented if f"${{{name}" not in forwarded)
    assert not ignored, f"documented in .env.prod.example but never forwarded: {ignored}"


def test_mail_is_configurable_in_production() -> None:
    """Every SMTP setting reaches the container.

    Not derivable from the validator — mail is optional as far as Settings is
    concerned. It is not optional for a club: login codes, magic links and
    invitations all go out this way, and a stack that cannot be pointed at a
    mail server locks everyone out.
    """
    forwarded = _backend_environment().keys()
    smtp_fields = {name for name in Settings.model_fields if name.startswith("SMTP_")}
    missing = sorted(smtp_fields - forwarded)
    assert not missing, f"SMTP settings not forwarded by docker-compose.prod.yml: {missing}"


def test_the_migration_step_shares_the_backend_environment() -> None:
    """Alembic runs with the same settings, or it fails the same validation."""
    compose: dict[str, Any] = yaml.safe_load(COMPOSE_FILE.read_text())
    assert compose["services"]["migrate"]["environment"] == _backend_environment()


# --- The cookie domain, which no CI run can check for a given server ---


def _production(**overrides: str) -> dict[str, str]:
    """A minimal environment that satisfies every other production rule."""
    base = {
        "DEBUG": "false",
        "INTERNAL_API_SECRET": _DUMMY_SECRET,
        "SESSION_SECRET": _DUMMY_SECRET,
        "JWT_SECRET": _DUMMY_SECRET,
        "ATTENDANCE_SECRET": _DUMMY_SECRET,
    }
    base.update(overrides)
    return base


def test_split_hosts_without_a_cookie_domain_are_refused() -> None:
    """The exact shape of the outage: api and app on different hosts, no domain.

    Every request would answer 200 and the health checks would pass; only a
    human trying to sign in would ever find out.
    """
    with pytest.raises(ValueError, match="COOKIE_DOMAIN"):
        Settings(
            _env_file=None,  # type: ignore[call-arg]
            **_production(
                BACKEND_URL="https://api.unefy.app",
                WEB_APP_URL="https://test.unefy.app",
            ),
        )


def test_a_cookie_domain_that_spans_both_hosts_is_accepted() -> None:
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        **_production(
            BACKEND_URL="https://api.unefy.app",
            WEB_APP_URL="https://test.unefy.app",
            COOKIE_DOMAIN=".unefy.app",
        ),
    )
    assert settings.COOKIE_DOMAIN == ".unefy.app"


def test_a_cookie_domain_missing_the_leading_dot_is_still_accepted() -> None:
    """RFC 6265 ignores it, so refusing over it would be pedantry."""
    Settings(
        _env_file=None,  # type: ignore[call-arg]
        **_production(
            BACKEND_URL="https://api.unefy.app",
            WEB_APP_URL="https://test.unefy.app",
            COOKIE_DOMAIN="unefy.app",
        ),
    )


def test_a_cookie_domain_that_covers_only_one_host_is_refused() -> None:
    with pytest.raises(ValueError, match="does not cover"):
        Settings(
            _env_file=None,  # type: ignore[call-arg]
            **_production(
                BACKEND_URL="https://api.unefy.app",
                WEB_APP_URL="https://app.example.com",
                COOKIE_DOMAIN=".unefy.app",
            ),
        )


def test_a_neighbouring_domain_does_not_count_as_covered() -> None:
    """Suffix matching without a boundary dot would let `not-unefy.app` pass."""
    with pytest.raises(ValueError, match="does not cover"):
        Settings(
            _env_file=None,  # type: ignore[call-arg]
            **_production(
                BACKEND_URL="https://api.unefy.app",
                WEB_APP_URL="https://app.not-unefy.app",
                COOKIE_DOMAIN=".unefy.app",
            ),
        )


def test_one_host_for_both_needs_no_cookie_domain() -> None:
    """Same host, so the cookie is readable where it was set."""
    Settings(
        _env_file=None,  # type: ignore[call-arg]
        **_production(
            BACKEND_URL="https://unefy.app/api",
            WEB_APP_URL="https://unefy.app",
        ),
    )


def test_a_mobile_only_deployment_still_boots() -> None:
    """`WEB_APP_URL` left at its default serves no web app to lock anyone out of."""
    Settings(
        _env_file=None,  # type: ignore[call-arg]
        **_production(BACKEND_URL="https://api.unefy.app"),
    )


def test_development_is_left_alone() -> None:
    """DEBUG skips it, like every other production rule in this file."""
    Settings(
        _env_file=None,  # type: ignore[call-arg]
        DEBUG="true",
        BACKEND_URL="https://api.unefy.app",
        WEB_APP_URL="https://test.unefy.app",
    )


def test_the_error_names_the_domain_to_set() -> None:
    """A message that makes the operator guess is only half a check."""
    with pytest.raises(ValueError, match=r"\.unefy\.app"):
        Settings(
            _env_file=None,  # type: ignore[call-arg]
            **_production(
                BACKEND_URL="https://api.unefy.app",
                WEB_APP_URL="https://test.unefy.app",
            ),
        )
