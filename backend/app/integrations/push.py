"""Sending FCM data messages, without `firebase-admin`.

The official SDK is synchronous; inside an `async def` it would block the
event loop — the one thing the backend CLAUDE.md forbids outright. What FCM
actually needs is small: an OAuth2 access token (google-auth, blocking, but
refreshed roughly once an hour and therefore pushed into a thread) and one
HTTPS POST per device token, which the `httpx` that is already here does
natively.

A message is a silent data payload: tenant id and collection name, nothing
else. No name, no amount, no text — a wake-up carries no information beyond
"come and sync", for the same three reasons the SSE hint carries none (see
`app/events/outbox.py`).
"""

import asyncio
from typing import Any

import httpx
import structlog
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import service_account

from app.config import Settings, get_settings

logger = structlog.get_logger()

_FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"


class FcmSender:
    """Sends wake-ups, and reports which tokens are dead.

    Never raises toward its caller: the write that triggered the wake-up has
    already committed, so a Google outage must cost freshness, not correctness.
    """

    def __init__(self, settings: Settings | None = None, credentials: Any | None = None) -> None:
        settings = settings or get_settings()
        # Loading the file also yields the project id — no second setting to
        # keep in step with the key. Injectable because constructing real
        # credentials requires a real RSA key, which a test has no business
        # owning.
        # The ignore below: google-auth ships this constructor unannotated.
        self._credentials = credentials or service_account.Credentials.from_service_account_file(  # type: ignore[no-untyped-call]
            settings.FCM_CREDENTIALS_FILE, scopes=[_FCM_SCOPE]
        )
        project_id = self._credentials.project_id
        self._endpoint = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
        self._client = httpx.AsyncClient(timeout=10.0)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _bearer(self) -> str:
        """A valid OAuth2 token. google-auth refreshes lazily and blocking —
        roughly once an hour, so the thread hop is cheap where it happens."""
        if not self._credentials.valid:
            await asyncio.to_thread(self._credentials.refresh, GoogleAuthRequest())
        token: str = self._credentials.token
        return token

    async def send_wakeup(self, token: str, *, tenant_id: str, entity: str) -> bool:
        """One silent data message to one device.

        Returns False when FCM says the token is gone (`UNREGISTERED` / 404),
        so the caller can drop the row — otherwise every future fan-out pays
        for a device that no longer exists. Transport errors only log: the
        next wake-up will try again.
        """
        message: dict[str, Any] = {
            "message": {
                "token": token,
                "data": {"tenant_id": tenant_id, "entity": entity},
                "android": {"priority": "high"},
            }
        }
        try:
            response = await self._client.post(
                self._endpoint,
                json=message,
                headers={"Authorization": f"Bearer {await self._bearer()}"},
            )
        except httpx.HTTPError as exc:
            logger.warning("push_send_failed", error=str(exc))
            return True

        if response.status_code == 404 or (
            response.status_code == 400 and "UNREGISTERED" in response.text
        ):
            # FCM's word for "this install is gone" — uninstalled, or the token
            # rotated and the device re-registered under the new one.
            return False
        if response.status_code >= 400:
            logger.warning(
                "push_send_rejected", status=response.status_code, body=response.text[:200]
            )
        return True
