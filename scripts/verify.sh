#!/usr/bin/env bash
# AEGIS verify gate (POSIX). Final line is the verdict: "VERIFY: PASS" (exit 0)
# or "VERIFY: FAIL (<stages>)" (exit 1).
#
# Usage:
#   scripts/verify.sh                      # full offline gate (lint, types, tests, contracts)
#   scripts/verify.sh --test-path <path>   # scoped: run ONLY that test file (pytest or vitest)
#   scripts/verify.sh --build              # also run production builds (pnpm build)
#   scripts/verify.sh --integration        # also run tests/integration (needs postgres+redis+minio up)
set -u
cd "$(dirname "$0")/.."

# This repo requires Node 22 (engines) and pnpm; on Windows both live under
# PNPM_HOME (standalone pnpm + `pnpm env use --global 22.x`). Prepend when needed.
if [ -n "${LOCALAPPDATA:-}" ] && command -v cygpath >/dev/null 2>&1; then
  PNPM_BIN="$(cygpath "${PNPM_HOME:-$LOCALAPPDATA/pnpm}")/bin"
  if [ -x "$PNPM_BIN/node.exe" ]; then
    PATH="$PNPM_BIN:$PATH"
  fi
fi
if ! command -v pnpm >/dev/null 2>&1 && command -v corepack >/dev/null 2>&1; then
  pnpm() { corepack pnpm "$@"; }
fi

TEST_PATH=""
RUN_BUILD=0
RUN_INTEGRATION=0
while [ $# -gt 0 ]; do
  case "$1" in
    --test-path) TEST_PATH="$2"; shift 2 ;;
    --build) RUN_BUILD=1; shift ;;
    --integration) RUN_INTEGRATION=1; shift ;;
    *) echo "unknown argument: $1"; echo "VERIFY: FAIL (usage)"; exit 1 ;;
  esac
done

FAILED=""
run_stage() {
  name="$1"; shift
  echo "=== [$name] $*"
  if "$@"; then
    echo "--- [$name] ok"
  else
    echo "--- [$name] FAILED"
    FAILED="$FAILED $name"
  fi
}

if [ -n "$TEST_PATH" ]; then
  case "$TEST_PATH" in
    *.test.ts|*.test.tsx|*.spec.ts|*.spec.tsx|*.test.js|*.test.jsx|*.test.mts)
      run_stage scoped-vitest pnpm exec vitest run "$TEST_PATH" ;;
    *)
      run_stage scoped-pytest uv run pytest "$TEST_PATH" -q ;;
  esac
else
  run_stage format pnpm format:check
  run_stage eslint pnpm lint
  run_stage tsc pnpm typecheck
  run_stage vitest pnpm test
  run_stage ruff uv run ruff check .
  run_stage mypy pnpm typecheck:py
  run_stage import-linter uv run lint-imports
  run_stage pytest uv run pytest -q --ignore=tests/integration
  run_stage contracts pnpm check-contracts
  [ "$RUN_BUILD" -eq 1 ] && run_stage build pnpm build
  [ "$RUN_INTEGRATION" -eq 1 ] && run_stage pytest-integration uv run pytest tests/integration -q
fi

if [ -n "$FAILED" ]; then
  echo "VERIFY: FAIL ($(echo "$FAILED" | sed 's/^ //;s/ /, /g'))"
  exit 1
fi
echo "VERIFY: PASS"
exit 0
