"""Evidence citation grounding validation."""

from __future__ import annotations

from aegis_agents.runtime.errors import AgentRuntimeError, AgentRuntimeErrorCode
from aegis_contracts.agent_runtime import EvidenceCitationV1


def validate_citations(
    citations: list[EvidenceCitationV1],
    *,
    visible_evidence_ids: set[str],
    trace_id: str | None = None,
) -> None:
    for citation in citations:
        if citation.evidence_id not in visible_evidence_ids:
            raise AgentRuntimeError(
                code=AgentRuntimeErrorCode.EVIDENCE_NOT_VISIBLE,
                message=f"Evidence citation not visible to session: {citation.evidence_id}",
                details={"evidenceId": citation.evidence_id},
                trace_id=trace_id,
            )
