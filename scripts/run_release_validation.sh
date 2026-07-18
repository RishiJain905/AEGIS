#!/usr/bin/env sh
set -u

environment="local"
include_performance=""
include_e2e=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --environment)
      environment="${2:-}"
      shift 2
      ;;
    --include-performance)
      include_performance="--include-performance"
      shift
      ;;
    --include-e2e)
      include_e2e="--include-e2e"
      shift
      ;;
    *)
      echo "usage: $0 [--environment local|staging] [--include-performance] [--include-e2e]" >&2
      exit 2
      ;;
  esac
done

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repo_root" || exit 2
set -- --environment "$environment"
if [ -n "$include_performance" ]; then
  set -- "$@" "$include_performance"
fi
if [ -n "$include_e2e" ]; then
  set -- "$@" "$include_e2e"
fi
uv run python scripts/release_validation.py "$@"
