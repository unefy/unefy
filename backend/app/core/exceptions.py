from typing import Any

import structlog
from fastapi import Request
from fastapi.responses import JSONResponse

logger = structlog.get_logger()


class AppError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(status_code=404, code="NOT_FOUND", message=message)


class ForbiddenError(AppError):
    def __init__(self, message: str = "Forbidden") -> None:
        super().__init__(status_code=403, code="FORBIDDEN", message=message)


class ConflictError(AppError):
    def __init__(self, message: str = "Conflict") -> None:
        super().__init__(status_code=409, code="CONFLICT", message=message)


class ValidationError(AppError):
    def __init__(
        self,
        message: str = "Validation error",
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(status_code=422, code="VALIDATION_ERROR", message=message, details=details)


async def app_exception_handler(_request: Request, exc: AppError) -> JSONResponse:
    body: dict[str, Any] = {
        "error": {
            "code": exc.code,
            "message": exc.message,
        }
    }
    if exc.details:
        body["details"] = exc.details
    return JSONResponse(status_code=exc.status_code, content=body)


async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    logger.error("unhandled_exception", error=str(exc), exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
            }
        },
    )
