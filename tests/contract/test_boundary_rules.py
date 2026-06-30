"""Boundary enforcement contract tests."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run_command(
    command: list[str], *, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
    )


def test_typescript_boundaries_pass() -> None:
    result = run_command(["pnpm", "boundaries"])
    assert result.returncode == 0, result.stdout + result.stderr


def test_python_import_boundaries_pass() -> None:
    result = run_command(["uv", "run", "lint-imports"])
    assert result.returncode == 0, result.stdout + result.stderr


def test_typescript_boundary_violation_is_detected() -> None:
    fixture_config = ROOT / "tests/fixtures/boundary-violation/.dependency-cruiser.fixture.cjs"
    assert fixture_config.is_file()
    result = run_command(
        [
            "pnpm",
            "exec",
            "depcruise",
            "tests/fixtures/boundary-violation",
            "--config",
            str(fixture_config),
        ]
    )
    assert result.returncode != 0, "Expected deliberate boundary violation to fail"
    assert "pkg-a-not-to-pkg-b" in result.stdout + result.stderr


def test_python_boundary_violation_is_detected() -> None:
    fixture_root = ROOT / "tests/fixtures/boundary-violation/python"
    result = run_command(
        [
            "uv",
            "run",
            "lint-imports",
            "--config",
            str(fixture_root / "importlinter.ini"),
        ],
        env={"PYTHONPATH": str(fixture_root)},
    )
    assert result.returncode != 0, "Expected deliberate Python boundary violation to fail"
