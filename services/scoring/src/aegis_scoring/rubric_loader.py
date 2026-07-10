"""Load scenario rubric and expected-evidence into scoring structures."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import yaml
from aegis_contracts.scoring import GRADING_ENGINE_VERSION, ScoreRubricV1
from aegis_contracts.versioning import SCORE_RUBRIC_SCHEMA_VERSION

from aegis_scoring.checksums import sha256_hex
from aegis_scoring.facts import ExpectedEvidenceFact, ObjectiveFact, ResponseBranchFact


def load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected mapping in {path}")
    return payload


def build_rubric_from_manifest(manifest: dict[str, Any]) -> ScoreRubricV1:
    metadata = manifest.get("metadata") or {}
    scoring = manifest.get("scoring") or {}
    rubric_text = str(scoring.get("rubric") or "")
    criteria = scoring.get("criteria") or []
    scenario_version = str(metadata.get("version") or "0.0.0")
    return ScoreRubricV1.model_validate(
        {
            "schemaVersion": SCORE_RUBRIC_SCHEMA_VERSION,
            "scenarioId": str(metadata.get("scenarioId") or "scenario:unknown"),
            "scenarioVersion": scenario_version,
            "rubricVersion": scenario_version,
            "gradingEngineVersion": GRADING_ENGINE_VERSION,
            "maxScore": float(scoring.get("maxScore") or 100),
            "criteria": [
                {
                    "id": c["id"],
                    "label": c["label"],
                    "weight": float(c["weight"]),
                    "description": str(c.get("description") or ""),
                }
                for c in criteria
            ],
            "rubricText": rubric_text,
            "rubricTextHash": sha256_hex(rubric_text.encode("utf-8")),
        }
    )


def load_expected_evidence(path: Path) -> list[ExpectedEvidenceFact]:
    payload = load_yaml(path)
    causes = payload.get("causes") or {}
    items: list[ExpectedEvidenceFact] = []
    for cause_id, cause in causes.items():
        for entry in cause.get("supportingEvidence") or []:
            event_type = str(entry["eventType"])
            asset_id = entry.get("assetId")
            key = f"{event_type}:{asset_id or '*'}"
            items.append(
                ExpectedEvidenceFact(
                    key=key,
                    event_type=event_type,
                    asset_id=str(asset_id) if asset_id else None,
                    description=str(entry.get("description") or ""),
                    cause_id=str(cause_id),
                )
            )
    return items


def load_objectives(manifest: dict[str, Any]) -> list[ObjectiveFact]:
    return [
        ObjectiveFact(
            objective_id=str(o["id"]),
            label=str(o.get("label") or o["id"]),
            success_criteria=str(o.get("successCriteria") or ""),
            failure_criteria=str(o.get("failureCriteria") or ""),
        )
        for o in (manifest.get("objectives") or [])
    ]


def load_response_branches(manifest: dict[str, Any]) -> list[ResponseBranchFact]:
    branches: list[ResponseBranchFact] = []
    for branch in manifest.get("branches") or []:
        branch_id = str(branch.get("id") or "")
        if not branch_id.startswith("branch-response"):
            continue
        branches.append(
            ResponseBranchFact(
                branch_id=branch_id,
                label=str(branch.get("label") or branch_id),
                description=str(branch.get("description") or ""),
            )
        )
    return branches


def resolve_scenario_dir(scenario_id: str, scenarios_root: Path | None = None) -> Path | None:
    root = scenarios_root or Path("scenarios")
    # scenario:operation-silent-relay -> operation-silent-relay
    slug = scenario_id.split(":")[-1]
    candidate = root / slug
    if (candidate / "manifest.yaml").exists():
        return candidate
    # Fallback scan
    if root.exists():
        for path in root.iterdir():
            manifest_path = path / "manifest.yaml"
            if not manifest_path.exists():
                continue
            data = load_yaml(manifest_path)
            meta = data.get("metadata") or {}
            if meta.get("scenarioId") == scenario_id:
                return path
    return None


def fingerprint_bytes(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"
