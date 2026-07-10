"""Score export rendering."""

from __future__ import annotations

import json

from aegis_contracts.scoring import (
    GRADING_ENGINE_VERSION,
    RunScoreV1,
    ScoreExportArtifactV1,
    ScoreExportFormatV1,
)
from aegis_contracts.versioning import SCORE_EXPORT_ARTIFACT_SCHEMA_VERSION

from aegis_scoring.checksums import hash_payload, sha256_hex
from aegis_scoring.ids import new_runtime_id


def render_score_export(
    score: RunScoreV1, export_format: ScoreExportFormatV1
) -> tuple[bytes, ScoreExportArtifactV1]:
    if export_format == ScoreExportFormatV1.JSON:
        content = json.dumps(score.model_dump(by_alias=True), indent=2, sort_keys=True).encode(
            "utf-8"
        )
    elif export_format == ScoreExportFormatV1.MARKDOWN:
        lines = [
            f"# Run Score — {score.run_id}",
            "",
            f"- **Overall:** {score.overall_score} / {score.max_score} (grade {score.grade.value})",
            f"- **Passed:** {score.passed}",
            f"- **Scenario version:** {score.provenance.scenario_version}",
            f"- **Rubric version:** {score.provenance.rubric_version}",
            f"- **Grading engine:** {score.provenance.grading_engine_version}",
            f"- **Input checksum:** {score.provenance.input_checksum}",
            f"- **Integrity checksum:** {score.provenance.integrity_checksum}",
            f"- **Fingerprint:** {score.provenance.fingerprint}",
            "",
            "## Components",
        ]
        for component in score.components:
            lines.append(
                f"- **{component.label}** (`{component.criterion_id}`): "
                f"raw={component.raw_score:.2f}, contribution={component.weighted_contribution:.2f}"
            )
            for explanation in component.explanations:
                lines.append(f"  - `{explanation.rule_id}`: {explanation.reason}")
        if score.valid_alternatives:
            lines.extend(["", "## Valid alternatives (non-authoritative)"])
            for alt in score.valid_alternatives:
                lines.append(
                    f"- **{alt.label}** (counterfactual): projected={alt.projected_overall_score}, "
                    f"delta={alt.score_delta}"
                )
        if score.coaching_text:
            lines.extend(["", "## Coaching (non-authoritative)", score.coaching_text])
        content = "\n".join(lines).encode("utf-8")
    else:
        content = b""

    artifact = ScoreExportArtifactV1.model_validate(
        {
            "schemaVersion": SCORE_EXPORT_ARTIFACT_SCHEMA_VERSION,
            "exportId": new_runtime_id("aaf"),
            "scoreId": score.score_id,
            "runId": score.run_id,
            "format": export_format.value,
            "scenarioVersion": score.provenance.scenario_version,
            "rubricVersion": score.provenance.rubric_version,
            "gradingEngineVersion": GRADING_ENGINE_VERSION,
            "integrityChecksum": score.provenance.integrity_checksum,
            "contentChecksum": sha256_hex(content),
            "createdAt": score.provenance.calculated_at,
        }
    )
    # Touch hash_payload for stable import usage in tests
    _ = hash_payload({"exportId": artifact.export_id})
    return content, artifact
