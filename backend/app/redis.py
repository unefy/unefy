from redis.asyncio import Redis, from_url

from app.config import get_settings

_redis_client: Redis | None = None


async def init_redis() -> Redis:
    global _redis_client
    settings = get_settings()
    _redis_client = from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


async def close_redis() -> None:
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None


def get_redis() -> Redis:
    if _redis_client is None:
        msg = "Redis client not initialized. Call init_redis() first."
        raise RuntimeError(msg)
    return _redis_client
