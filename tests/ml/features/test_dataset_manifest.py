"""Dataset manifest tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from aegis_contracts.entities import RunV1
from aegis_contracts.versioning import RUN_SCHEMA_VERSION
from aegis_ml.features.dataset_builder import build_dataset_from_events

from tests.ml.features.helpers import RUN_ID, sample_auth_failed, sample_auth_succeeded


def test_dataset_manifest_is_checksum_stable(tmp_path: Path) -> None:
    run = RunV1(
        schema_version=RUN_SCHEMA_VERSION,
        id=RUN_ID,
        scenario_version_id="scenario-version:v1.0.0-synthetic",
        seed=1000,
        status="completed",
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
        sim_time=datetime(2026, 1, 1, tzinfo=UTC),
        revision=1,
    )
    events = [sample_auth_failed(), sample_auth_succeeded()]
    first = build_dataset_from_events(run=run, events=events, output_dir=tmp_path / "a")
    second = build_dataset_from_events(run=run, events=events, output_dir=tmp_path / "b")
    assert first.dataset_checksum == second.dataset_checksum
    assert first.dataset_checksum.startswith("sha256:")
    manifest = json.loads((tmp_path / "a" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["featureSchemaVersion"] == 1
    assert manifest["rowCount"] == 1
