"""Evidence grounding for BASTION response proposals."""

from __future__ import annotations

from dataclasses import dataclass

from aegis_agents.runtime.errors import AgentRuntimeError, AgentRuntimeErrorCode
from aegis_contracts.investigation import InvestigationDetailV1
from aegis_contracts.proposals import ScenarioCommandTemplateV1
from aegis_policy.commands import COMMAND_TO_ACTION_CLASS, parse_command


@dataclass(frozen=True)
class GroundingContext:
    visible_evidence_ids: set[str]
    visible_hypothesis_ids: set[str]
    attachment_evidence_ids: set[str]


def build_grounding_context(
    investigation: InvestigationDetailV1,
    visible_evidence_ids: set[str],
) -> GroundingContext:
    attachment_ids = {
        attachment.evidence_id
        for attachment in investigation.evidence_attachments
        if attachment.evidence_id
    }
    hypothesis_ids = {hypothesis.id for hypothesis in investigation.hypotheses}
    return GroundingContext(
        visible_evidence_ids=visible_evidence_ids,
        visible_hypothesis_ids=hypothesis_ids,
        attachment_evidence_ids=attachment_ids,
    )


def validate_response_option_grounding(
    *,
    evidence_ids: list[str],
    hypothesis_ids: list[str],
    scenario_command: str,
    context: GroundingContext,
    trace_id: str,
) -> ScenarioCommandTemplateV1:
    parsed = parse_command(scenario_command)
    if parsed is None:
        raise AgentRuntimeError(
            code=AgentRuntimeErrorCode.TOOL_VALIDATION_FAILED,
            message=f"Unsupported scenario command: {scenario_command}",
            trace_id=trace_id,
        )

    if parsed not in COMMAND_TO_ACTION_CLASS:
        raise AgentRuntimeError(
            code=AgentRuntimeErrorCode.TOOL_VALIDATION_FAILED,
            message=f"Command not allowlisted: {scenario_command}",
            trace_id=trace_id,
        )

    allowed_evidence = context.visible_evidence_ids | context.attachment_evidence_ids
    for evidence_id in evidence_ids:
        if evidence_id not in allowed_evidence:
            raise AgentRuntimeError(
                code=AgentRuntimeErrorCode.GROUNDING_FAILED,
                message=f"Evidence not visible: {evidence_id}",
                trace_id=trace_id,
            )

    for hypothesis_id in hypothesis_ids:
        if hypothesis_id not in context.visible_hypothesis_ids:
            raise AgentRuntimeError(
                code=AgentRuntimeErrorCode.GROUNDING_FAILED,
                message=f"Hypothesis not visible: {hypothesis_id}",
                trace_id=trace_id,
            )

    return parsed
