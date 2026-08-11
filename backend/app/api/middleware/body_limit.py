"""Refuse an oversized body before it is read, not after.

Starlette spools a multipart upload to a temporary file *before* the endpoint
runs, so a limit checked inside the handler is a limit checked after the disk
has already been used. A 5 GB "upload" to a 25 MB library would be accepted,
written to `/tmp`, and only then declined.

So the declared length is checked here, where the body has not been touched
yet. Two honest limitations, written down rather than implied:

- A request without `Content-Length` (chunked transfer encoding) passes
  through. `LocalStorage` still stops at `max_bytes` mid-stream, so nothing is
  *stored* over the limit — the temporary file is what goes unguarded, and
  browsers do not send uploads that way.
- A lie in the header is not caught here either. It does not have to be: the
  writer counts the bytes it actually receives.
"""

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = structlog.get_logger()

#: Room on top of the largest accepted file for the rest of a multipart body:
#: boundaries, headers and the form fields that travel with it.
MULTIPART_OVERHEAD = 1024 * 1024

_METHODS_WITH_BODIES = {"POST", "PUT", "PATCH"}


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: object, max_bytes: int) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self.max_bytes = max_bytes + MULTIPART_OVERHEAD

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method in _METHODS_WITH_BODIES:
            declared = request.headers.get("content-length")
            if declared and declared.isdigit() and int(declared) > self.max_bytes:
                logger.info(
                    "body_too_large",
                    path=request.url.path,
                    declared=int(declared),
                    limit=self.max_bytes,
                )
                return JSONResponse(
                    status_code=413,
                    content={
                        "error": {
                            "code": "PAYLOAD_TOO_LARGE",
                            "message": f"Request body exceeds {self.max_bytes} bytes",
                        }
                    },
                )
        return await call_next(request)
