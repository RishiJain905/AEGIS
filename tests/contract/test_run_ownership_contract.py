"""RunV1 ownerUserId is an additive optional field (schemaVersion stays 1).

See ADR 0034 / AEGIS-OITB-008. Guards backward compatibility: pre-ownership run
payloads (no ownerUserId) must still parse, and the new field must round-trip.
"""

from __future__ import annotations

from aegis_contracts import RunV1
from aegis_contracts.parsing import parse_contract
from aegis_contracts.versioning import RUN_SCHEMA_VERSION

_BASE_RUN = {
    "schemaVersion": 1,
    "id": "run_01ARZ3NDEKTSV4RRFFQ69G5FAV",
    "scenarioVersionId": "scenario-version:v1.0.0-synthetic",
    "seed": 424242,
    "status": "running",
    "startedAt": "2026-06-30T02:00:00.000Z",
    "simTime": "2026-01-01T18:42:03.420Z",
    "revision": 1,
}


def test_run_schema_version_unchanged() -> None:
    assert RUN_SCHEMA_VERSION == 1


def test_legacy_run_without_owner_still_parses() -> None:
    run = parse_contract(RunV1, dict(_BASE_RUN))
    assert run.owner_user_id is None


def test_run_with_owner_round_trips() -> None:
    payload = {**_BASE_RUN, "ownerUserId": "user:operator-alpha"}
    run = parse_contract(RunV1, payload)
    assert run.owner_user_id == "user:operator-alpha"
    dumped = run.model_dump(by_alias=True)
    assert dumped["ownerUserId"] == "user:operator-alpha"
    assert dumped["schemaVersion"] == 1
