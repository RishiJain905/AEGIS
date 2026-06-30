"""Repository layout contract tests."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

REQUIRED_DIRECTORIES = [
    "apps/web",
    "apps/api",
    "services/simulation",
    "services/incidents",
    "services/agents",
    "services/ml",
    "services/workers",
    "packages/contracts-python",
    "packages/contracts-ts",
    "packages/scenario-sdk",
    "packages/graph-domain",
    "packages/policy",
    "packages/observability",
    "packages/ui",
    "scenarios/operation-silent-relay",
    "models/manifests",
    "models/evaluation",
    "tests/contract",
    "tests/integration",
    "tests/e2e",
    "tests/performance",
    "tests/golden-replays",
    "infra",
    "scripts",
    "handoffs",
    "docs",
]


@pytest.mark.parametrize("relative_path", REQUIRED_DIRECTORIES)
def test_required_directory_exists(relative_path: str) -> None:
    assert (ROOT / relative_path).is_dir(), f"Missing required directory: {relative_path}"


def test_env_example_exists_without_secrets() -> None:
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "POSTGRES_PASSWORD=aegis_dev" in env_example
    assert "changeme" not in env_example.lower() or "aegis_dev" in env_example
    forbidden_patterns = ["sk-", "AKIA", "BEGIN RSA PRIVATE KEY"]
    for pattern in forbidden_patterns:
        assert pattern not in env_example


def test_gitignore_excludes_env() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".env" in gitignore
