# syntax=docker/dockerfile:1

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY services/simulation/pyproject.toml services/simulation/
COPY packages/contracts-python/pyproject.toml packages/contracts-python/
COPY packages/persistence/pyproject.toml packages/persistence/
COPY packages/scenario-sdk/pyproject.toml packages/scenario-sdk/
COPY packages/simulation-domain/pyproject.toml packages/simulation-domain/
COPY packages/contracts-python/src packages/contracts-python/src
COPY packages/persistence/src packages/persistence/src
COPY packages/scenario-sdk/src packages/scenario-sdk/src
COPY packages/simulation-domain/src packages/simulation-domain/src
COPY services/simulation/src services/simulation/src
RUN uv sync --frozen --no-dev --package aegis-simulation

FROM python:3.12.10-slim-bookworm AS runner
WORKDIR /app
RUN groupadd -r aegis && useradd -r -g aegis aegis
COPY --from=builder /app/.venv /app/.venv
COPY services/simulation/src services/simulation/src
COPY packages/contracts-python/src packages/contracts-python/src
COPY packages/persistence/src packages/persistence/src
COPY packages/scenario-sdk/src packages/scenario-sdk/src
COPY packages/simulation-domain/src packages/simulation-domain/src
ENV PATH="/app/.venv/bin:$PATH"
USER aegis
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "from aegis_simulation import get_health; assert get_health('simulator').status == 'ok'"
CMD ["aegis-simulator"]
