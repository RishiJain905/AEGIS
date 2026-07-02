"""Filesystem baseline artifact storage."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from aegis_contracts.detection import (
    BASELINE_VERSION,
    StatisticalBaselineManifestV1,
    StatisticalBaselineV1,
)
from aegis_contracts.versioning import (
    FEATURE_SCHEMA_VERSION,
    STATISTICAL_BASELINE_MANIFEST_SCHEMA_VERSION,
    WORKSPACE_VERSION,
)

DEFAULT_BASELINE_DIR = Path("models/baselines/v1")


def canonical_baseline_json(baseline: StatisticalBaselineV1) -> str:
    return json.dumps(baseline.model_dump(mode="json", by_alias=True), sort_keys=True, separators=(",", ":"))


def baseline_checksum(baseline: StatisticalBaselineV1) -> str:
    digest = hashlib.sha256(canonical_baseline_json(baseline).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def save_baseline(
    baseline: StatisticalBaselineV1,
    *,
    output_dir: Path = DEFAULT_BASELINE_DIR,
    holdout_seeds: list[int],
) -> StatisticalBaselineManifestV1:
    output_dir.mkdir(parents=True, exist_ok=True)
    checksum = baseline_checksum(baseline)
    baseline_path = output_dir / "baseline.json"
    baseline_path.write_text(
        json.dumps(baseline.model_dump(mode="json", by_alias=True), indent=2) + "\n",
        encoding="utf-8",
    )
    manifest = StatisticalBaselineManifestV1(
        schema_version=STATISTICAL_BASELINE_MANIFEST_SCHEMA_VERSION,
        baseline_version=BASELINE_VERSION,
        baseline_checksum=checksum,
        training_seeds=list(baseline.training_seeds),
        holdout_seeds=holdout_seeds,
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        workspace_version=WORKSPACE_VERSION,
        created_at=datetime.now(tz=UTC),
    )
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest.model_dump(mode="json", by_alias=True), indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def load_baseline(*, baseline_dir: Path = DEFAULT_BASELINE_DIR) -> StatisticalBaselineV1:
    baseline_path = baseline_dir / "baseline.json"
    raw = json.loads(baseline_path.read_text(encoding="utf-8"))
    return StatisticalBaselineV1.model_validate(raw)


def load_baseline_manifest(*, baseline_dir: Path = DEFAULT_BASELINE_DIR) -> StatisticalBaselineManifestV1:
    manifest_path = baseline_dir / "manifest.json"
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    return StatisticalBaselineManifestV1.model_validate(raw)
