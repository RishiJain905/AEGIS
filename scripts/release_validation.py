#!/usr/bin/env python3
"""Run Phase 34 validation and write schema-versioned release evidence."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, TextIO

SCHEMA_VERSION = "aegis.release-evidence/v1"
SCENARIO_VERSION = "operation-silent-relay@1.0.0"
DETERMINISTIC_SEED = 42


@dataclass(frozen=True, slots=True)
class Stage:
    name: str
    command: list[str]
    environment: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class StageResult:
    name: str
    command: list[str]
    status: Literal["passed", "failed", "skipped"]
    exit_code: int | None
    started_at: str
    duration_seconds: float
    artifact_path: str
    output_tail: str

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        return {
            "name": data["name"],
            "command": data["command"],
            "status": data["status"],
            "exitCode": data["exit_code"],
            "startedAt": data["started_at"],
            "durationSeconds": data["duration_seconds"],
            "artifactPath": data["artifact_path"],
            "outputTail": data["output_tail"],
        }


@dataclass(slots=True)
class EvidenceManifest:
    run_id: str
    started_at: datetime
    environment: str
    revision: str
    scenario_version: str
    seed: int
    results: list[StageResult]
    artifact_paths: list[str]
    reports: dict[str, str] = field(default_factory=dict)

    @property
    def status(self) -> Literal["passed", "failed"]:
        all_passed = self.results and all(result.status == "passed" for result in self.results)
        return "passed" if all_passed else "failed"

    def to_dict(self) -> dict[str, object]:
        return {
            "schemaVersion": SCHEMA_VERSION,
            "runId": self.run_id,
            "timestamp": _iso_utc(self.started_at),
            "environment": self.environment,
            "revision": self.revision,
            "status": self.status,
            "scenario": {
                "version": self.scenario_version,
                "seed": self.seed,
            },
            "commandResults": [result.to_dict() for result in self.results],
            "artifactPaths": self.artifact_paths,
            **({"reports": self.reports} if self.reports else {}),
        }

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")


def _iso_utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def configure_console(stream: TextIO) -> None:
    """Allow UTF-8 child-process output on legacy Windows console encodings."""
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8", errors="replace")


def _powershell() -> str:
    for candidate in ("pwsh", "powershell"):
        if shutil.which(candidate):
            return candidate
    return "pwsh"


def _configure_pnpm_path() -> None:
    """Make the checked-in pnpm/corepack shims visible to child stages on Windows."""
    if shutil.which("pnpm"):
        return
    local_app_data = os.environ.get("LOCALAPPDATA")
    candidates = []
    if os.environ.get("PNPM_HOME"):
        candidates.append(Path(os.environ["PNPM_HOME"]) / "bin")
    if local_app_data:
        candidates.extend(
            [
                Path(local_app_data) / "pnpm" / "bin",
                Path(local_app_data) / "corepack-bin",
            ]
        )
    for candidate in candidates:
        if (candidate / "pnpm.CMD").exists() or (candidate / "pnpm").exists():
            os.environ["PATH"] = f"{candidate}{os.pathsep}{os.environ.get('PATH', '')}"
            return


def ensure_supported_environment(environment: str) -> None:
    if environment != "local":
        raise ValueError(
            "Phase 34 validates the local production-like stack only; "
            "staging is unavailable because ADR 0033 removed real staging deployment."
        )


def build_validation_plan(
    environment: str,
    *,
    include_performance: bool = False,
    include_e2e: bool = False,
) -> list[Stage]:
    ensure_supported_environment(environment)
    ps = _powershell()
    stages = [
        Stage("verify", [ps, "-NoProfile", "-File", "scripts/verify.ps1"]),
        Stage(
            "docker-services",
            [
                "docker",
                "compose",
                "up",
                "-d",
                "--build",
                "--wait",
                "postgres",
                "redis",
                "minio",
                "api",
                "worker",
                "simulator",
            ],
        ),
    ]
    if include_performance:
        stages.append(
            Stage(
                "performance",
                ["uv", "run", "python", "tests/performance/release/run_performance.py"],
            )
        )
    if include_e2e:
        stages.append(
            Stage("e2e", ["uv", "run", "python", "scripts/run_release_e2e.py"])
        )
    stages.extend(
        [
            Stage("integration", ["uv", "run", "pytest", "tests/integration", "-q"]),
        Stage("golden-replays", ["uv", "run", "pytest", "tests/golden-replays", "-q"]),
        Stage(
            "failure-injection",
            ["uv", "run", "pytest", "tests/failure-injection", "-q"],
            {"AEGIS_RUN_FAILURE_INJECTION": "1"},
        ),
        Stage("security", ["uv", "run", "pytest", "tests/security", "-q"]),
        Stage(
            "deployment-smoke",
            [ps, "-NoProfile", "-File", "scripts/verify.ps1", "-Deployment"],
        ),
        ]
    )
    return stages


def _revision(repo_root: Path) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip() or "unknown"


def _tail(lines: list[str], count: int = 40) -> str:
    return "\n".join(lines[-count:])


def _run_stage(stage: Stage, *, repo_root: Path, log_path: Path) -> StageResult:
    started = datetime.now(UTC)
    began = time.monotonic()
    relative_log = log_path.relative_to(repo_root).as_posix()
    env = os.environ.copy()
    env.update(stage.environment)
    lines: list[str] = []
    print(f"=== [{stage.name}] {' '.join(stage.command)}", flush=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with log_path.open("w", encoding="utf-8", errors="replace") as log:
            process = subprocess.Popen(
                stage.command,
                cwd=repo_root,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            assert process.stdout is not None
            for raw_line in process.stdout:
                line = raw_line.rstrip("\r\n")
                lines.append(line)
                log.write(line + "\n")
                log.flush()
                print(line, flush=True)
            exit_code = process.wait()
    except (OSError, ValueError) as exc:
        exit_code = 127
        lines.append(f"Unable to execute stage: {exc}")
        log_path.write_text(lines[-1] + "\n", encoding="utf-8")
        print(lines[-1], flush=True)

    status: Literal["passed", "failed", "skipped"] = "passed" if exit_code == 0 else "failed"
    duration = round(time.monotonic() - began, 3)
    print(f"--- [{stage.name}] {status.upper()} ({duration:.3f}s)", flush=True)
    return StageResult(
        name=stage.name,
        command=stage.command,
        status=status,
        exit_code=exit_code,
        started_at=_iso_utc(started),
        duration_seconds=duration,
        artifact_path=relative_log,
        output_tail=_tail(lines),
    )


def run(
    environment: str,
    *,
    repo_root: Path,
    include_performance: bool = False,
    include_e2e: bool = False,
) -> tuple[EvidenceManifest, Path]:
    _configure_pnpm_path()
    plan = build_validation_plan(
        environment,
        include_performance=include_performance,
        include_e2e=include_e2e,
    )
    started = datetime.now(UTC)
    revision = _revision(repo_root)
    run_id = f"release-{started.strftime('%Y%m%dT%H%M%SZ')}-{revision[:8]}"
    evidence_root = repo_root / "docs" / "release" / "evidence"
    log_root = evidence_root / run_id / "logs"
    report_paths = {
        "performance": evidence_root / run_id / "performance.json",
        "e2e": evidence_root / run_id / "e2e.json",
    }
    results: list[StageResult] = []
    reports: dict[str, str] = {}
    for stage in plan:
        report_path = report_paths.get(stage.name)
        if report_path is not None:
            stage = replace(
                stage,
                environment={
                    **stage.environment,
                    "AEGIS_RELEASE_REPORT_PATH": str(report_path),
                },
            )
        result = _run_stage(
            stage,
            repo_root=repo_root,
            log_path=log_root / f"{stage.name}.log",
        )
        results.append(result)
        if report_path is not None and report_path.exists():
            reports[stage.name] = report_path.relative_to(repo_root).as_posix()
    manifest = EvidenceManifest(
        run_id=run_id,
        started_at=started,
        environment=environment,
        revision=revision,
        scenario_version=SCENARIO_VERSION,
        seed=DETERMINISTIC_SEED,
        results=results,
        artifact_paths=[
            *[result.artifact_path for result in results],
            *reports.values(),
        ],
        reports=reports,
    )
    manifest_path = evidence_root / f"{run_id}.json"
    manifest.write(manifest_path)
    return manifest, manifest_path


def main(argv: list[str] | None = None) -> int:
    configure_console(sys.stdout)
    configure_console(sys.stderr)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", choices=("local", "staging"), default="local")
    parser.add_argument(
        "--include-performance",
        action="store_true",
        help="run API, streaming, database, and browser performance validation",
    )
    parser.add_argument(
        "--include-e2e",
        action="store_true",
        help="run the local Playwright release journeys",
    )
    args = parser.parse_args(argv)
    repo_root = Path(__file__).resolve().parents[1]
    try:
        ensure_supported_environment(args.environment)
    except ValueError as exc:
        print(f"RELEASE VALIDATION: REFUSED - {exc}")
        return 2

    manifest, path = run(
        args.environment,
        repo_root=repo_root,
        include_performance=args.include_performance,
        include_e2e=args.include_e2e,
    )
    print(f"Evidence manifest: {path.relative_to(repo_root).as_posix()}")
    verdict = "PASS" if manifest.status == "passed" else "FAIL"
    print(f"RELEASE VALIDATION: {verdict}")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
