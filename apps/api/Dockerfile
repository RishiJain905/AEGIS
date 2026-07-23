# syntax=docker/dockerfile:1

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY apps/api/pyproject.toml apps/api/
COPY services/ml/pyproject.toml services/ml/
COPY services/incidents/pyproject.toml services/incidents/
COPY services/simulation/pyproject.toml services/simulation/
COPY packages/contracts-python/pyproject.toml packages/contracts-python/
COPY packages/persistence/pyproject.toml packages/persistence/
COPY packages/event-streaming/pyproject.toml packages/event-streaming/
COPY packages/scenario-sdk/pyproject.toml packages/scenario-sdk/
COPY packages/simulation-domain/pyproject.toml packages/simulation-domain/
COPY packages/graph-risk/pyproject.toml packages/graph-risk/
COPY packages/model-provider/pyproject.toml packages/model-provider/
COPY packages/policy/pyproject.toml packages/policy/
COPY packages/observability/pyproject.toml packages/observability/
COPY services/reports/pyproject.toml services/reports/
COPY services/agents/pyproject.toml services/agents/
COPY services/replay/pyproject.toml services/replay/
COPY services/scoring/pyproject.toml services/scoring/
COPY packages/contracts-python/src packages/contracts-python/src
COPY packages/persistence/src packages/persistence/src
COPY packages/event-streaming/src packages/event-streaming/src
COPY packages/scenario-sdk/src packages/scenario-sdk/src
COPY packages/simulation-domain/src packages/simulation-domain/src
COPY packages/graph-risk/src packages/graph-risk/src
COPY packages/model-provider/src packages/model-provider/src
COPY packages/policy/src packages/policy/src
COPY packages/observability/src packages/observability/src
COPY services/reports/src services/reports/src
COPY services/agents/src services/agents/src
COPY services/replay/src services/replay/src
COPY services/scoring/src services/scoring/src
COPY services/ml/src services/ml/src
COPY services/incidents/src services/incidents/src
COPY services/simulation/src services/simulation/src
COPY apps/api/src apps/api/src
RUN uv sync --frozen --no-dev --package aegis-api
# The copilot's local/openai-compatible provider adapter needs the OpenAI SDK
# (an optional extra of aegis-model-provider not pulled by the frozen sync).
# Installed explicitly so the deployed api can call the local llama-serve model.
RUN uv pip install "openai>=1.68"

FROM python:3.12.10-slim-bookworm AS runner
WORKDIR /app
RUN groupadd -r aegis && useradd -r -g aegis aegis
RUN apt-get update \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder /app/.venv /app/.venv
COPY --chown=aegis:aegis apps/api/src apps/api/src
COPY --chown=aegis:aegis services/ml/src services/ml/src
COPY --chown=aegis:aegis services/incidents/src services/incidents/src
COPY --chown=aegis:aegis services/simulation/src services/simulation/src
COPY --chown=aegis:aegis services/replay/src services/replay/src
COPY --chown=aegis:aegis services/scoring/src services/scoring/src
COPY --chown=aegis:aegis packages/contracts-python/src packages/contracts-python/src
COPY --chown=aegis:aegis packages/persistence/src packages/persistence/src
COPY --chown=aegis:aegis packages/event-streaming/src packages/event-streaming/src
COPY --chown=aegis:aegis packages/scenario-sdk/src packages/scenario-sdk/src
COPY --chown=aegis:aegis packages/simulation-domain/src packages/simulation-domain/src
COPY --chown=aegis:aegis packages/graph-risk/src packages/graph-risk/src
COPY --chown=aegis:aegis packages/model-provider/src packages/model-provider/src
COPY --chown=aegis:aegis packages/policy/src packages/policy/src
COPY --chown=aegis:aegis packages/observability/src packages/observability/src
COPY --chown=aegis:aegis services/reports/src services/reports/src
COPY --chown=aegis:aegis services/agents/src services/agents/src
COPY --chown=aegis:aegis scenarios/operation-silent-relay scenarios/operation-silent-relay
COPY --chown=aegis:aegis alembic.ini alembic.ini
COPY --chown=aegis:aegis migrations migrations
ENV PATH="/app/.venv/bin:$PATH" \
    HOME=/tmp \
    TMPDIR=/tmp \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
USER aegis
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"
CMD ["uvicorn", "aegis_api.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
