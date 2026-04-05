"""Lightweight Redis-backed rate limiter.

Fixed-window counter per client IP + endpoint path. Use as a FastAPI
dependency:

    @router.post("/login", dependencies=[Depends(RateLimit(limit=5, window=60))])
    async def login(...): ...

For authenticated endpoints, pass `by="user"` to key on the user_id
resolved from the request cookie/session. Falls back to IP if unresolvable.
"""

from typing import Literal

from fastapi import HTTPException, Request

from app.redis import get_redis


def _client_ip(request: Request) -> str:
    # Behind a proxy the real client IP is in X-Forwarded-For; trust the
    # left-most entry (set by our own reverse proxy, not arbitrary callers).
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


class RateLimit:
    """Limit requests per fixed time window.

    Args:
        limit: Max allowed requests per window.
        window: Window length in seconds.
        by: Key strategy. "ip" (default) or "user" (falls back to ip).
        scope: Optional scope tag so multiple limiters on one path don't
            share a counter (e.g. "auth-login").
    """

    def __init__(
        self,
        *,
        limit: int,
        window: int,
        by: Literal["ip", "user"] = "ip",
        scope: str | None = None,
    ) -> None:
        self.limit = limit
        self.window = window
        self.by = by
        self.scope = scope

    async def __call__(self, request: Request) -> None:
        identifier = _client_ip(request)
        if self.by == "user":
            # Read user id from the session cookie body if present.
            # This avoids a DB/Redis roundtrip — we only need *some* key.
            from app.api.v1.auth import COOKIE_NAME, get_session_data

            token = request.cookies.get(COOKIE_NAME)
            if token:
                data = await get_session_data(token)
                if data is not None:
                    identifier = f"user:{data[0]}"

        tag = self.scope or request.url.path
        key = f"rl:{tag}:{identifier}"

        redis = get_redis()
        # Atomic INCR + set TTL on first hit within the window.
        current = await redis.incr(key)
        if current == 1:
            await redis.expire(key, self.window)

        if current > self.limit:
            ttl = await redis.ttl(key)
            raise HTTPException(
                status_code=429,
                detail="Too many requests",
                headers={"Retry-After": str(max(ttl, 1))},
            )
