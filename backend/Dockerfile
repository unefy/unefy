FROM python:3.13-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-editable

COPY . .

FROM python:3.13-slim

RUN groupadd --system appuser && useradd --system --gid appuser appuser

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app .

ENV PATH="/app/.venv/bin:$PATH"

USER appuser
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# `--timeout-graceful-shutdown` is not optional here. On shutdown uvicorn waits
# for open responses to finish, and `GET /api/v1/stream` is a response that never
# finishes by design — so a single phone or browser holding a change stream makes
# every restart and every deploy hang forever. Verified: with a client attached
# the container went silent and never came back; with none it restarted in
# seconds. Cutting the stream off is harmless, the client reconnects with
# `Last-Event-ID` and resumes exactly where it stopped.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--timeout-graceful-shutdown", "10"]
