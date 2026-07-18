from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.demo_v1 import build_demo_manifest
from scripts.generate_release_manifest import build_manifest, validate_manifest


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
