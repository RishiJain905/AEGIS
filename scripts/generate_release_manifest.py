#!/usr/bin/env python3
"""Generate and validate the local, schema-versioned AEGIS release manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "aegis.release-manifest/v1"
RELEASE_VERSION = "1.0.0"
DEFAULT_MIGRATION_HEAD = "013_auth_identity"
DEFAULT_IMAGE_REFS = {
    "api": "aegis-api:latest",
    "web": "aegis-web:latest",
    "worker": "aegis-worker:latest",
    "simulator": "aegis-simulator:latest",
}
DEFAULT_MODEL_MANIFESTS = (
    "models/manifests/isolation-forest-v1/manifest.json",
    "models/baselines/v1/manifest.json",
    "fixtures/model-responses/manifest.json",
)
DEFAULT_SBOM_REFERENCES = (
    "security-artifacts/dependencies.cdx.json",
    "security-artifacts/sbom-api.cdx.json",
    "security-artifacts/sbom-web.cdx.json",
    "security-artifacts/sbom-worker.cdx.json",
    "security-artifacts/sbom-simulator.cdx.json",
)
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")

ImageInspector = Callable[[str], Mapping[str, Any]]


def sha256_file(path: Path) -> str:
    """Return a prefixed SHA-256 digest for a file."""

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _relative_path(path: Path, repo_root: Path) -> str:
    return path.resolve().relative_to(repo_root.resolve()).as_posix()


def _docker_inspect(image_ref: str) -> Mapping[str, Any]:
    completed = subprocess.run(
        ["docker", "inspect", image_ref, "--format", "{{json .}}"],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or "image is not present locally"
        raise RuntimeError(f"docker inspect failed for {image_ref}: {detail}")
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"docker inspect returned invalid JSON for {image_ref}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"docker inspect returned a non-object for {image_ref}")
    return value


def _image_record(service: str, image_ref: str, inspector: ImageInspector) -> dict[str, object]:
    inspected = inspector(image_ref)
    digest = inspected.get("Id") or inspected.get("imageId")
    if not isinstance(digest, str) or not _DIGEST_RE.fullmatch(digest):
        raise RuntimeError(f"docker inspect did not return a sha256 image ID for {image_ref}")
    repo_digests = inspected.get("RepoDigests", inspected.get("repoDigests", []))
    if not isinstance(repo_digests, list) or not all(
        isinstance(item, str) for item in repo_digests
    ):
        repo_digests = []
    return {
        "service": service,
        "reference": image_ref,
        "digest": digest,
        "repoDigests": sorted(repo_digests),
    }


def _scenario_metadata(package_dir: Path) -> tuple[str, str]:
    package_manifest = package_dir / "package.manifest.yaml"
    if not package_manifest.exists():
        raise RuntimeError(f"scenario package manifest is missing: {package_manifest}")
    try:
        import yaml

        payload = yaml.safe_load(package_manifest.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - convert parser failures to a release error
        raise RuntimeError(f"could not read scenario package manifest: {package_manifest}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"scenario package manifest is not an object: {package_manifest}")
    version = payload.get("version")
    checksum = payload.get("packageChecksum")
    if not isinstance(version, str) or not isinstance(checksum, str):
        raise RuntimeError("scenario package manifest must contain version and packageChecksum")
    return version, checksum


def _default_artifacts(repo_root: Path) -> list[Path]:
    evidence = sorted((repo_root / "docs/release/evidence").glob("release-*.json"))
    if not evidence:
        raise RuntimeError("no Phase 34 release evidence manifest was found")
    relative_paths = [
        _relative_path(evidence[-1], repo_root),
        "docs/release/test-plan.md",
        "docs/release/known-issues.md",
        "docs/release/evidence-manifest.schema.json",
        "docker-compose.yml",
        "docker-compose.prod.yml",
        ".dockerignore",
        "apps/api/Dockerfile",
        "scenarios/operation-silent-relay/package.manifest.yaml",
        "models/manifests/isolation-forest-v1/manifest.json",
        "models/manifests/isolation-forest-v1/artifact.joblib",
        "models/baselines/v1/manifest.json",
        "fixtures/model-responses/manifest.json",
        "release/demo-manifest.json",
        "release/manifest.schema.json",
        "scripts/demo_v1.py",
    ]
    return [repo_root / relative for relative in relative_paths]


def build_manifest(
    *,
    repo_root: Path,
    revision: str,
    migration_head: str,
    image_inspector: ImageInspector,
    image_refs: Mapping[str, str],
    artifact_paths: Sequence[Path],
    scenario_package: Path,
    scenario_version: str,
    scenario_checksum: str,
    model_manifest_paths: Sequence[Path],
    sbom_references: Sequence[str],
) -> dict[str, object]:
    """Build a deterministic manifest from explicit release inputs."""

    images = [
        _image_record(service, image_refs[service], image_inspector)
        for service in sorted(image_refs)
    ]
    model_artifacts = [
        {
            "path": _relative_path(path, repo_root),
            "sha256": sha256_file(path),
        }
        for path in sorted(model_manifest_paths, key=lambda item: _relative_path(item, repo_root))
    ]
    checksums: dict[str, str] = {}
    for path in sorted(artifact_paths, key=lambda item: _relative_path(item, repo_root)):
        if not path.exists():
            raise RuntimeError(
                f"key release artifact is missing: {_relative_path(path, repo_root)}"
            )
        checksums[_relative_path(path, repo_root)] = sha256_file(path)

    return {
        "schemaVersion": SCHEMA_VERSION,
        "releaseVersion": RELEASE_VERSION,
        "tag": f"v{RELEASE_VERSION}",
        "source": {"revision": revision},
        "environment": "local",
        "images": images,
        "migration": {"head": migration_head},
        "scenario": {
            "id": "scenario:operation-silent-relay",
            "version": scenario_version,
            "packagePath": _relative_path(scenario_package, repo_root),
            "packageChecksum": scenario_checksum,
        },
        "modelArtifacts": model_artifacts,
        "sbom": {
            "references": [
                {
                    "path": reference,
                    "source": ".github/workflows/security.yml",
                    "status": "ci-generated",
                }
                for reference in sorted(sbom_references)
            ]
        },
        "checksums": checksums,
    }


def validate_manifest(manifest: Mapping[str, object], *, repo_root: Path) -> None:
    """Validate the release manifest shape and every checked-in checksum."""

    required = {
        "schemaVersion",
        "releaseVersion",
        "tag",
        "source",
        "environment",
        "images",
        "migration",
        "scenario",
        "modelArtifacts",
        "sbom",
        "checksums",
    }
    missing = required.difference(manifest)
    if missing:
        raise ValueError(f"manifest is missing required fields: {sorted(missing)}")
    if manifest["schemaVersion"] != SCHEMA_VERSION or manifest["releaseVersion"] != RELEASE_VERSION:
        raise ValueError("manifest schema or release version is unsupported")
    source = manifest["source"]
    if not isinstance(source, dict) or not isinstance(source.get("revision"), str):
        raise ValueError("manifest source.revision must be a string")
    if manifest["environment"] != "local":
        raise ValueError("release manifest environment must be local")
    checksums = manifest["checksums"]
    if not isinstance(checksums, dict):
        raise ValueError("manifest checksums must be an object")
    for relative, expected in checksums.items():
        if (
            not isinstance(relative, str)
            or not isinstance(expected, str)
            or not _DIGEST_RE.fullmatch(expected)
        ):
            raise ValueError(f"invalid checksum entry: {relative!r}")
        path = (repo_root / relative).resolve()
        if not path.is_file():
            raise ValueError(f"manifest checksum references missing file: {relative}")
        actual = sha256_file(path)
        if actual != expected:
            raise ValueError(f"checksum mismatch for {relative}: {actual} != {expected}")
    images = manifest["images"]
    if not isinstance(images, list) or not images:
        raise ValueError("manifest images must be a non-empty list")
    for image in images:
        if not isinstance(image, dict) or not isinstance(image.get("digest"), str):
            raise ValueError("every image must contain a digest")
        if not _DIGEST_RE.fullmatch(image["digest"]):
            raise ValueError(f"invalid image digest: {image['digest']}")


def _git_revision(repo_root: Path) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _migration_head(repo_root: Path) -> str:
    completed = subprocess.run(
        ["uv", "run", "alembic", "heads"],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode == 0:
        match = re.search(r"^([A-Za-z0-9_]+)\s+\(head\)", completed.stdout, re.MULTILINE)
        if match:
            return match.group(1)
    return DEFAULT_MIGRATION_HEAD


def _parse_image_args(values: Sequence[str]) -> dict[str, str]:
    refs = dict(DEFAULT_IMAGE_REFS)
    for value in values:
        service, separator, image_ref = value.partition("=")
        if not separator or service not in refs or not image_ref:
            raise ValueError(f"--image must be SERVICE=IMAGE for one of {sorted(refs)}")
        refs[service] = image_ref
    return refs


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("release/manifest.json"))
    parser.add_argument("--migration-head", default=None)
    parser.add_argument("--image", action="append", default=[], metavar="SERVICE=IMAGE")
    parser.add_argument("--artifact", action="append", default=[], type=Path)
    parser.add_argument("--sbom-reference", action="append", default=[])
    args = parser.parse_args(argv)
    repo_root = Path(__file__).resolve().parents[1]
    try:
        package_dir = repo_root / "scenarios/operation-silent-relay"
        scenario_version, scenario_checksum = _scenario_metadata(package_dir)
        image_refs = _parse_image_args(args.image)
        artifact_paths = args.artifact or _default_artifacts(repo_root)
        model_paths = [repo_root / path for path in DEFAULT_MODEL_MANIFESTS]
        sbom_references = args.sbom_reference or list(DEFAULT_SBOM_REFERENCES)
        manifest = build_manifest(
            repo_root=repo_root,
            revision=_git_revision(repo_root),
            migration_head=args.migration_head or _migration_head(repo_root),
            image_inspector=_docker_inspect,
            image_refs=image_refs,
            artifact_paths=[
                path if path.is_absolute() else repo_root / path for path in artifact_paths
            ],
            scenario_package=package_dir,
            scenario_version=scenario_version,
            scenario_checksum=scenario_checksum,
            model_manifest_paths=model_paths,
            sbom_references=sbom_references,
        )
        validate_manifest(manifest, repo_root=repo_root)
        output = args.output if args.output.is_absolute() else repo_root / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"Release manifest: {_relative_path(output, repo_root)}")
        print("RELEASE MANIFEST: PASS")
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"RELEASE MANIFEST: FAIL - {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
