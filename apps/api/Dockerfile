# syntax=docker/dockerfile:1

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY apps/api/pyproject.toml apps/api/
COPY packages/contracts-python/pyproject.toml packages/contracts-python/
COPY packages/persistence/pyproject.toml packages/persistence/
COPY packages/event-streaming/pyproject.toml packages/event-streaming/
COPY packages/contracts-python/src packages/contracts-python/src
COPY packages/persistence/src packages/persistence/src
COPY packages/event-streaming/src packages/event-streaming/src
RUN uv sync --frozen --no-dev --package aegis-api

FROM python:3.12.10-slim-bookworm AS runner
WORKDIR /app
RUN groupadd -r aegis && useradd -r -g aegis aegis
COPY --from=builder /app/.venv /app/.venv
COPY apps/api/src apps/api/src
COPY packages/contracts-python/src packages/contracts-python/src
COPY packages/persistence/src packages/persistence/src
COPY packages/event-streaming/src packages/event-streaming/src
ENV PATH="/app/.venv/bin:$PATH"
USER aegis
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"
CMD ["uvicorn", "aegis_api.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
