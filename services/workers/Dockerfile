# syntax=docker/dockerfile:1

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY services/workers/pyproject.toml services/workers/
COPY packages/contracts-python/pyproject.toml packages/contracts-python/
COPY packages/persistence/pyproject.toml packages/persistence/
COPY packages/event-streaming/pyproject.toml packages/event-streaming/
COPY packages/model-provider/pyproject.toml packages/model-provider/
COPY packages/policy/pyproject.toml packages/policy/
COPY services/reports/pyproject.toml services/reports/
COPY services/agents/pyproject.toml services/agents/
COPY packages/contracts-python/src packages/contracts-python/src
COPY packages/persistence/src packages/persistence/src
COPY packages/event-streaming/src packages/event-streaming/src
COPY packages/model-provider/src packages/model-provider/src
COPY packages/policy/src packages/policy/src
COPY services/reports/src services/reports/src
COPY services/agents/src services/agents/src
COPY services/workers/src services/workers/src
RUN uv sync --frozen --no-dev --package aegis-workers

FROM python:3.12.10-slim-bookworm AS runner
WORKDIR /app
RUN groupadd -r aegis && useradd -r -g aegis aegis
COPY --from=builder /app/.venv /app/.venv
COPY services/workers/src services/workers/src
COPY packages/contracts-python/src packages/contracts-python/src
COPY packages/persistence/src packages/persistence/src
COPY packages/event-streaming/src packages/event-streaming/src
COPY packages/model-provider/src packages/model-provider/src
COPY packages/policy/src packages/policy/src
COPY services/reports/src services/reports/src
COPY services/agents/src services/agents/src
ENV PATH="/app/.venv/bin:$PATH"
USER aegis
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "from aegis_workers import get_health; assert get_health('worker').status == 'ok'"
CMD ["aegis-worker"]
