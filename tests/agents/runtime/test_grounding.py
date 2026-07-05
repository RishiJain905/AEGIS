"""Evidence grounding validation tests."""

from __future__ import annotations

import pytest
from aegis_agents.runtime.errors import AgentRuntimeError, AgentRuntimeErrorCode
from aegis_agents.runtime.grounding import validate_citations
from aegis_contracts.agent_runtime import EvidenceCitationV1
from aegis_contracts.versioning import EVIDENCE_CITATION_SCHEMA_VERSION


def test_valid_citation_passes() -> None:
    validate_citations(
        [
            EvidenceCitationV1(
                schema_version=EVIDENCE_CITATION_SCHEMA_VERSION,
                evidence_id="evidence:evd_synthetic_001",
            )
        ],
        visible_evidence_ids={"evidence:evd_synthetic_001"},
    )


def test_nonvisible_citation_rejected() -> None:
    with pytest.raises(AgentRuntimeError) as exc:
        validate_citations(
            [
                EvidenceCitationV1(
                    schema_version=EVIDENCE_CITATION_SCHEMA_VERSION,
                    evidence_id="evidence:evd_hidden",
                )
            ],
            visible_evidence_ids={"evidence:evd_synthetic_001"},
        )
    assert exc.value.code == AgentRuntimeErrorCode.EVIDENCE_NOT_VISIBLE
