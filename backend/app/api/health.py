import structlog
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.database import async_session_factory
from app.redis import get_redis
from app.schemas.base import HealthResponse

logger = structlog.get_logger()
router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/health/live", response_model=HealthResponse)
async def liveness() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/health/ready", response_model=HealthResponse)
async def readiness() -> HealthResponse:
    checks: dict[str, str] = {}

    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        logger.error("readiness_check_failed", component="database")
        checks["database"] = "error"

    try:
        redis = get_redis()
        await redis.ping()
        checks["redis"] = "ok"
    except Exception:
        logger.error("readiness_check_failed", component="redis")
        checks["redis"] = "error"

    all_ok = all(v == "ok" for v in checks.values())

    if not all_ok:
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "checks": checks},
        )

    return HealthResponse(
        status="ok",
        checks=checks,
    )
