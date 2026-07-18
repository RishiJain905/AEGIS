"""Contract tests for the Phase 34 release-validation runner."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from io import BytesIO, TextIOWrapper

import pytest
from scripts.release_validation import (
    EvidenceManifest,
    StageResult,
    build_validation_plan,
    configure_console,
    ensure_supported_environment,
)


def test_local_plan_covers_every_core_release_gate() -> None:
    stages = build_validation_plan("local")

    assert [stage.name for stage in stages] == [
        "verify",
        "docker-services",
        "integration",
        "golden-replays",
        "failure-injection",
        "security",
        "deployment-smoke",
    ]
    assert "tests/integration" in stages[2].command
    assert "tests/failure-injection" in stages[4].command
    assert "tests/security" in stages[5].command
    assert "--build" in stages[1].command


def test_optional_release_stages_are_additive() -> None:
    stages = build_validation_plan("local", include_performance=True, include_e2e=True)

    assert [stage.name for stage in stages] == [
        "verify",
        "docker-services",
        "performance",
        "e2e",
        "integration",
        "golden-replays",
        "failure-injection",
        "security",
        "deployment-smoke",
    ]
    assert stages[2].command == [
        "uv",
        "run",
        "python",
        "tests/performance/release/run_performance.py",
    ]
    assert stages[3].command == ["uv", "run", "python", "scripts/run_release_e2e.py"]


def test_staging_is_refused_without_cloud_validation() -> None:
    with pytest.raises(ValueError, match="local production-like stack"):
        ensure_supported_environment("staging")


def test_console_accepts_utf8_child_output_on_legacy_windows_encoding() -> None:
    stream = TextIOWrapper(BytesIO(), encoding="cp1252", errors="strict")

    configure_console(stream)
    stream.write("\u2714 release gate\n")
    stream.flush()


def test_evidence_manifest_is_schema_versioned_and_serializable(tmp_path) -> None:
    result = StageResult(
        name="verify",
        command=["pwsh", "-File", "scripts/verify.ps1"],
        status="passed",
        exit_code=0,
        started_at="2026-07-18T12:00:00Z",
        duration_seconds=1.25,
        artifact_path="docs/release/evidence/run/logs/verify.log",
        output_tail="VERIFY: PASS",
    )
    manifest = EvidenceManifest(
        run_id="release-20260718T120000Z-deadbeef",
        started_at=datetime(2026, 7, 18, 12, tzinfo=UTC),
        environment="local",
        revision="deadbeef",
        scenario_version="operation-silent-relay@1.0.0",
        seed=42,
        results=[result],
        artifact_paths=[result.artifact_path],
    )

    path = tmp_path / "manifest.json"
    manifest.write(path)
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["schemaVersion"] == "aegis.release-evidence/v1"
    assert payload["runId"] == manifest.run_id
    assert payload["status"] == "passed"
    assert payload["scenario"]["seed"] == 42
    assert payload["commandResults"][0]["outputTail"] == "VERIFY: PASS"


def test_evidence_manifest_can_reference_structured_release_reports(tmp_path) -> None:
    result = StageResult(
        name="performance",
        command=["uv", "run", "python", "tests/performance/release/run_performance.py"],
        status="passed",
        exit_code=0,
        started_at="2026-07-18T12:00:00Z",
        duration_seconds=2.0,
        artifact_path="docs/release/evidence/run/logs/performance.log",
        output_tail="PERFORMANCE BUDGET: PASS",
    )
    manifest = EvidenceManifest(
        run_id="release-20260718T120000Z-deadbeef",
        started_at=datetime(2026, 7, 18, 12, tzinfo=UTC),
        environment="local",
        revision="deadbeef",
        scenario_version="operation-silent-relay@1.0.0",
        seed=42,
        results=[result],
        artifact_paths=[result.artifact_path],
        reports={"performance": "docs/release/evidence/run/performance.json"},
    )

    path = tmp_path / "manifest.json"
    manifest.write(path)
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["reports"] == {
        "performance": "docs/release/evidence/run/performance.json"
    }
