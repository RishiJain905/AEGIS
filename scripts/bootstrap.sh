#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "==> AEGIS bootstrap (Phase 00)"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example"
fi

if ! command -v pnpm >/dev/null 2>&1; then
  echo "pnpm is not installed. Install Node 22 and enable pnpm via the packageManager field:"
  echo "  corepack enable && corepack prepare pnpm@11.9.0 --activate"
  exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is not installed. See https://docs.astral.sh/uv/getting-started/installation/"
  exit 1
fi

echo "==> Installing JavaScript dependencies (frozen lockfile)"
pnpm install --frozen-lockfile

echo "==> Installing Python dependencies (frozen lockfile)"
uv sync --frozen --all-packages

echo "==> Ensuring a provider-credential encryption key exists"
# Cloud model providers store the operator's API key encrypted, which needs a Fernet
# key. Generating it here means a fresh clone can connect a provider without anyone
# reading the docs; it is written once and never regenerated, because rotating it
# strands every key already stored.
uv run python - <<'PY'
from pathlib import Path

from cryptography.fernet import Fernet

NAME = "AEGIS_CREDENTIAL_ENCRYPTION_KEY"
env_path = Path(".env")
lines = env_path.read_text(encoding="utf-8").splitlines()

for index, line in enumerate(lines):
    if not line.startswith(f"{NAME}="):
        continue
    if line[len(NAME) + 1 :].strip():
        print(f"{NAME} is already set; leaving it alone")
        break
    lines[index] = f"{NAME}={Fernet.generate_key().decode()}"
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Generated {NAME} in .env")
    break
else:
    lines.append(f"{NAME}={Fernet.generate_key().decode()}")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Appended {NAME} to .env")
PY

echo "==> Validating environment configuration"
pnpm validate-env
uv run python scripts/validate_env.py

echo ""
echo "Bootstrap complete. Next steps:"
echo "  pnpm lint && pnpm typecheck && pnpm test && pnpm build"
echo "  uv run ruff check . && pnpm typecheck:py && uv run pytest -q"
echo "  docker compose config && docker compose build"
