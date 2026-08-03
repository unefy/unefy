"""`Idempotency-Key` — the safety net for writes without a client-assigned id.

Some endpoints get idempotency from a client key in the row itself (entries,
buffered check-ins). The rest — bulk-delete, close, check-out, scan — have
nothing in the payload that could tell a retry from a repeat, so the key moves
into a header and the answer into Redis: the first response under a key is
stored, and a replay gets that stored response back instead of a second
execution.

Three properties carry the security story:

- **Bound to the credential, not just the key.** The Redis key hashes the
  caller's session cookie or bearer token in, so one user's key can never
  replay — or observe — another's response.
- **Bound to the body.** The stored entry remembers a hash of the request
  body; the same key with a different body is a bug on the client (or an
  attack) and answers a named 422 rather than someone else's stale response.
- **Replay is replay, not re-execution.** A replayed scan returns the stored
  201 without running anything — the rotating code burned exactly once, and
  `CODE_ALREADY_USED` keeps meaning what it means: the same code from a
  *different* request, which is precisely the screenshot-pass-around the burn
  key exists to catch.

Opt-in per request via the header; without it nothing changes. 5xx responses
are never stored — a retry after a server error must actually retry.
"""

import hashlib
import json

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.redis import get_redis

logger = structlog.get_logger()

#: How long a stored response answers replays. A day covers every realistic
#: retry (an offline queue draining on the drive home); past that a repeat is
#: more likely a new intent than a retry.
TTL_SECONDS = 86_400

#: Responses above this size pass through unstored — the header is meant for
#: writes, whose responses are one row, not for accidentally caching a report.
MAX_STORED_BODY = 256 * 1024

#: While a first execution is in flight, a concurrent duplicate waits nowhere —
#: it answers 409 and retries later. Short, so a crashed worker does not hold
#: the key hostage.
LOCK_SECONDS = 30

_METHODS = frozenset({"POST", "PATCH", "DELETE"})


class IdempotencyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        key = request.headers.get("idempotency-key")
        if key is None or request.method not in _METHODS or len(key) > 200:
            return await call_next(request)

        body = await request.body()
        body_hash = hashlib.sha256(body).hexdigest()
        redis_key = self._redis_key(request, key)
        redis = get_redis()

        stored = await redis.get(redis_key)
        if stored is not None:
            entry = json.loads(stored)
            if entry == "in-flight":
                return _conflict("The same request is still being processed; retry shortly")
            if entry["body_hash"] != body_hash:
                # A key is one intent. The same key carrying a different body is
                # a client bug worth surfacing, never worth answering with the
                # other body's stored response.
                return _key_reuse_error()
            return Response(
                content=entry["body"],
                status_code=entry["status"],
                media_type=entry["media_type"],
                headers={"Idempotency-Replayed": "true"},
            )

        # NX: of two concurrent first attempts, exactly one executes.
        if not await redis.set(redis_key, json.dumps("in-flight"), nx=True, ex=LOCK_SECONDS):
            return _conflict("The same request is already being processed; retry shortly")

        response = await call_next(request)

        if response.status_code >= 500:
            # A retry after a server error must actually retry.
            await redis.delete(redis_key)
            return response

        response_body = b""
        async for chunk in response.body_iterator:  # type: ignore[attr-defined]
            response_body += chunk if isinstance(chunk, bytes) else chunk.encode()

        if len(response_body) <= MAX_STORED_BODY:
            await redis.set(
                redis_key,
                json.dumps(
                    {
                        "body_hash": body_hash,
                        "status": response.status_code,
                        "body": response_body.decode("utf-8", errors="replace"),
                        "media_type": response.headers.get("content-type"),
                    }
                ),
                ex=TTL_SECONDS,
            )
        else:
            await redis.delete(redis_key)

        return Response(
            content=response_body,
            status_code=response.status_code,
            headers=dict(response.headers),
        )

    def _redis_key(self, request: Request, key: str) -> str:
        """Scoped to the credential — see the module docstring.

        The session cookie or bearer token stands in for the user without a
        database round trip; hashing it keeps credentials out of Redis keys.
        """
        credential = request.headers.get("authorization") or request.cookies.get(
            "unefy_session", ""
        )
        scope = hashlib.sha256(credential.encode()).hexdigest()[:32]
        return f"idem:{scope}:{hashlib.sha256(key.encode()).hexdigest()[:32]}"


def _conflict(message: str) -> Response:
    return _error(409, "IDEMPOTENT_REQUEST_IN_FLIGHT", message)


def _key_reuse_error() -> Response:
    return _error(
        422,
        "IDEMPOTENCY_KEY_REUSED",
        "This Idempotency-Key was already used with a different request body",
    )


def _error(status: int, code: str, message: str) -> Response:
    return Response(
        content=json.dumps({"error": {"code": code, "message": message}}),
        status_code=status,
        media_type="application/json",
    )
