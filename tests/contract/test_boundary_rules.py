"""Boundary enforcement contract tests."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run_command(
    command: list[str], *, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    # Windows CreateProcess only resolves .exe from PATH; tools like pnpm are
    # installed as .cmd/.ps1 shims (plus extensionless POSIX scripts that Windows
    # cannot spawn), so resolve to a launchable executable explicitly.
    executable: str | None = None
    if os.name == "nt":
        for ext in (".exe", ".cmd", ".bat"):
            executable = shutil.which(command[0] + ext)
            if executable is not None:
                break
    if executable is None:
        executable = shutil.which(command[0])
    if executable is None:
        raise FileNotFoundError(f"required tool not found on PATH: {command[0]}")
    return subprocess.run(
        [executable, *command[1:]],
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
