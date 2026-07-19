from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from scripts.demo_v1 import build_demo_manifest
from scripts.generate_release_manifest import (
    build_manifest,
    validate_manifest,
    verify_manifest_correspondence,
)

_REV = "facf0979bf1bb654531c1141cd8ff526b7af6747"
_HEAD = "013_auth_identity"
_DIGEST = "sha256:" + "a" * 64


def _correspondence_manifest() -> dict[str, object]:
    return {
        "source": {"revision": _REV},
        "migration": {"head": _HEAD},
        "images": [{"reference": "aegis-api:latest", "digest": _DIGEST}],
        "checksums": {
            "docker-compose.yml": "sha256:" + "b" * 64,
            "apps/api/Dockerfile": "sha256:" + "c" * 64,
        },
    }


def _inspector(digest: str):
    return lambda _reference: {"Id": digest}


def test_generated_manifest_has_schema_and_correct_artifact_checksums(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.txt"
    artifact.write_text("release evidence\n", encoding="utf-8")

    manifest = build_manifest(
        repo_root=tmp_path,
        revision="facf0979bf1bb654531c1141cd8ff526b7af6747",
        migration_head="013_auth_identity",
        image_inspector=lambda _: {
            "imageId": "sha256:" + "a" * 64,
            "repoDigests": [],
        },
        image_refs={"api": "aegis-api:v1.0.0"},
        artifact_paths=[artifact],
        scenario_package=tmp_path,
        scenario_version="1.0.0",
        scenario_checksum="sha256:" + "b" * 64,
        model_manifest_paths=[],
        sbom_references=["security-artifacts/dependencies.cdx.json"],
    )

    validate_manifest(manifest, repo_root=tmp_path)
    assert manifest["schemaVersion"] == "aegis.release-manifest/v1"
    assert manifest["source"]["revision"] == "facf0979bf1bb654531c1141cd8ff526b7af6747"
    assert manifest["migration"]["head"] == "013_auth_identity"
    assert manifest["images"][0]["digest"] == "sha256:" + "a" * 64
    expected = "sha256:" + hashlib.sha256(artifact.read_bytes()).hexdigest()
    assert manifest["checksums"]["artifact.txt"] == expected


def test_manifest_json_is_deterministically_serializable() -> None:
    path = Path("release/manifest.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert json.dumps(payload, sort_keys=True, separators=(",", ":"))


def test_demo_manifest_declares_the_documented_deterministic_run() -> None:
    manifest = build_demo_manifest(seed=42)
    assert manifest["schemaVersion"] == "aegis.demo/v1"
    assert manifest["scenario"]["version"] == "operation-silent-relay@1.0.0"
    assert manifest["seed"] == 42
    assert any("approval" in outcome for outcome in manifest["expectedHeadlineOutcomes"])


# --- AEGIS-OITB-003: manifest correspondence verification (fail-closed) ---

_REQUIRED = ("docker-compose.yml", "apps/api/Dockerfile")


def test_correspondence_passes_for_a_matching_manifest(tmp_path: Path) -> None:
    verify_manifest_correspondence(
        _correspondence_manifest(),
        repo_root=tmp_path,
        expected_revision=_REV,
        expected_migration_head=_HEAD,
        image_inspector=_inspector(_DIGEST),
        required_artifacts=_REQUIRED,
        required_artifact_prefixes=(),
    )


def test_correspondence_fails_on_stale_revision(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="source.revision"):
        verify_manifest_correspondence(
            _correspondence_manifest(),
            repo_root=tmp_path,
            expected_revision="0" * 40,
            expected_migration_head=_HEAD,
            image_inspector=_inspector(_DIGEST),
            required_artifacts=_REQUIRED,
            required_artifact_prefixes=(),
        )


def test_correspondence_fails_on_stale_migration_head(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="migration.head"):
        verify_manifest_correspondence(
            _correspondence_manifest(),
            repo_root=tmp_path,
            expected_revision=_REV,
            expected_migration_head="999_future_head",
            image_inspector=_inspector(_DIGEST),
            required_artifacts=_REQUIRED,
            required_artifact_prefixes=(),
        )


def test_correspondence_fails_on_image_digest_mismatch(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="image digest mismatch"):
        verify_manifest_correspondence(
            _correspondence_manifest(),
            repo_root=tmp_path,
            expected_revision=_REV,
            expected_migration_head=_HEAD,
            image_inspector=_inspector("sha256:" + "d" * 64),
            required_artifacts=_REQUIRED,
            required_artifact_prefixes=(),
        )


def test_correspondence_fails_on_missing_artifact_coverage(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="missing required artifact coverage"):
        verify_manifest_correspondence(
            _correspondence_manifest(),
            repo_root=tmp_path,
            expected_revision=_REV,
            expected_migration_head=_HEAD,
            image_inspector=_inspector(_DIGEST),
            required_artifacts=(*_REQUIRED, "docs/release/newly-required.md"),
            required_artifact_prefixes=(),
        )


def test_correspondence_skips_checks_for_none_providers(tmp_path: Path) -> None:
    # Detached/offline build: providers explicitly disabled, coverage still enforced.
    verify_manifest_correspondence(
        _correspondence_manifest(),
        repo_root=tmp_path,
        expected_revision=None,
        expected_migration_head=None,
        image_inspector=None,
        required_artifacts=_REQUIRED,
        required_artifact_prefixes=(),
    )


def test_generated_manifest_passes_validation_and_correspondence(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.txt"
    artifact.write_text("release evidence\n", encoding="utf-8")

    manifest = build_manifest(
        repo_root=tmp_path,
        revision=_REV,
        migration_head=_HEAD,
        image_inspector=lambda _: {"imageId": _DIGEST, "repoDigests": []},
        image_refs={"api": "aegis-api:v1.0.0"},
        artifact_paths=[artifact],
        scenario_package=tmp_path,
        scenario_version="1.0.0",
        scenario_checksum="sha256:" + "b" * 64,
        model_manifest_paths=[],
        sbom_references=["security-artifacts/dependencies.cdx.json"],
    )

    validate_manifest(manifest, repo_root=tmp_path)
    verify_manifest_correspondence(
        manifest,
        repo_root=tmp_path,
        expected_revision=_REV,
        expected_migration_head=_HEAD,
        image_inspector=_inspector(_DIGEST),
        required_artifacts=("artifact.txt",),
        required_artifact_prefixes=(),
    )
