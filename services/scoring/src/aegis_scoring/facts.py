"""Scoring input facts assembled from authoritative run data."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aegis_contracts.scoring import ScoreRubricV1


@dataclass(frozen=True)
class ExpectedEvidenceFact:
    key: str
    event_type: str
    asset_id: str | None
    description: str
    cause_id: str


@dataclass(frozen=True)
class EventFact:
    event_id: str
    sequence: int
    event_type: str
    asset_id: str | None
    sim_time: str | None
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EvidenceFact:
    evidence_id: str
    source_event_id: str | None
    asset_id: str | None
    summary: str
    created_sequence: int | None = None


@dataclass(frozen=True)
class HypothesisFact:
    hypothesis_id: str
    statement: str
    confidence: float | None
    status: str
    revision: int
    created_sequence: int | None = None


@dataclass(frozen=True)
class ProposalFact:
    proposal_id: str
    action_class: str
    status: str
    summary: str
    target_asset_ids: tuple[str, ...] = ()
    created_sequence: int | None = None
    policy_decision: str | None = None
    #: The session that authored the proposal. Operator direct actions anchor to the
    #: deterministic operator-console session; agent proposals carry their agent session.
    #: Lets the decision review tell an operator's own justification apart from an agent
    #: recommendation instead of rendering the operator's words as "vs agent".
    agent_session_id: str | None = None


@dataclass(frozen=True)
class ApprovalFact:
    approval_id: str
    proposal_id: str
    decision: str
    sequence: int
    decided_at: str | None = None


@dataclass(frozen=True)
class ExecutedActionFact:
    action_id: str
    proposal_id: str
    sequence: int
    outcome: str
    impact_score: float = 0.0
    target_asset_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ObjectiveFact:
    objective_id: str
    label: str
    success_criteria: str
    failure_criteria: str


@dataclass(frozen=True)
class ResponseBranchFact:
    branch_id: str
    label: str
    description: str = ""


@dataclass
class ScoringFacts:
    """Authoritative facts for a completed run. Pure data — no I/O."""

    run_id: str
    run_status: str
    scenario_id: str
    scenario_version: str
    rubric: ScoreRubricV1
    events: list[EventFact] = field(default_factory=list)
    alerts: list[EventFact] = field(default_factory=list)
    evidence: list[EvidenceFact] = field(default_factory=list)
    hypotheses: list[HypothesisFact] = field(default_factory=list)
    proposals: list[ProposalFact] = field(default_factory=list)
    approvals: list[ApprovalFact] = field(default_factory=list)
    executed_actions: list[ExecutedActionFact] = field(default_factory=list)
    expected_evidence: list[ExpectedEvidenceFact] = field(default_factory=list)
    objectives: list[ObjectiveFact] = field(default_factory=list)
    response_branches: list[ResponseBranchFact] = field(default_factory=list)
    true_cause_id: str | None = None
    true_cause_label: str | None = None
    selected_response_branch: str | None = None
    incident_id: str | None = None
    affected_asset_ids: list[str] = field(default_factory=list)
    lessons: list[str] = field(default_factory=list)
    scribe_report_id: str | None = None
    scribe_version_number: int | None = None
    calculated_at: str | None = None
