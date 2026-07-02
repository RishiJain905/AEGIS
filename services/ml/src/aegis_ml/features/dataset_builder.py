"""Content-addressed dataset export."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from aegis_contracts.entities import RunV1
from aegis_contracts.events import DomainEventEnvelopeV1
from aegis_contracts.features import TRANSFORM_VERSION, DatasetManifestV1, DatasetSourceRunV1
from aegis_contracts.versioning import (
    DATASET_MANIFEST_SCHEMA_VERSION,
    FEATURE_SCHEMA_VERSION,
    WORKSPACE_VERSION,
)

from aegis_ml.features.engine import compute_features_from_events
from aegis_ml.features.schema_registry import FEATURE_SCHEMA_MANIFEST_V1


def canonical_jsonl_line(payload: dict[str, object]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def build_dataset_from_events(
    *,
    run: RunV1,
    events: list[DomainEventEnvelopeV1],
    output_dir: Path,
) -> DatasetManifestV1:
    output_dir.mkdir(parents=True, exist_ok=True)
    result = compute_features_from_events(run_id=run.id, events=events)
    lines = [
        canonical_jsonl_line(vector.model_dump(mode="json", by_alias=True))
        for vector in result.vectors
    ]
    features_path = output_dir / "features.jsonl"
    features_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    dataset_checksum = f"sha256:{hashlib.sha256(features_path.read_bytes()).hexdigest()}"
    manifest = DatasetManifestV1(
        schema_version=DATASET_MANIFEST_SCHEMA_VERSION,
        dataset_checksum=dataset_checksum,
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        transform_version=TRANSFORM_VERSION,
        row_count=len(result.vectors),
        source_runs=[
            DatasetSourceRunV1(
                run_id=run.id,
                seed=run.seed,
                scenario_version_id=run.scenario_version_id,
            )
        ],
        window_duration_sim_seconds=FEATURE_SCHEMA_MANIFEST_V1.window_duration_sim_seconds,
        created_at=datetime.now(tz=UTC),
        workspace_version=WORKSPACE_VERSION,
        compatibility_metadata={
            "rejectionCount": len(result.rejections),
            "lastProcessedSequence": result.last_processed_sequence,
        },
    )
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest.model_dump(mode="json", by_alias=True), indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest
