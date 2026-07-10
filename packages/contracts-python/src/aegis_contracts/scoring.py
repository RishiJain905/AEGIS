"""Phase 29 scoring and after-action contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aegis_contracts.errors import ContractErrorCode, ContractValidationError
from aegis_contracts.primitives import (
    AssetId,
    EventId,
    EvidenceId,
    HypothesisId,
    IncidentId,
    ProposalId,
    RunId,
    Sequence,
    UtcTimestamp,
)
from aegis_contracts.versioning import (
    AFTER_ACTION_VIEW_MODEL_SCHEMA_VERSION,
    DECISION_REVIEW_SCHEMA_VERSION,
    MISSED_EVIDENCE_ITEM_SCHEMA_VERSION,
    RUN_COMPARISON_SCORE_SCHEMA_VERSION,
    RUN_SCORE_SCHEMA_VERSION,
    SCORE_COMPONENT_SCHEMA_VERSION,
    SCORE_EXPLANATION_SCHEMA_VERSION,
    SCORE_EXPORT_ARTIFACT_SCHEMA_VERSION,
    SCORE_PROVENANCE_SCHEMA_VERSION,
    SCORE_RUBRIC_SCHEMA_VERSION,
    VALID_ALTERNATIVE_SCHEMA_VERSION,
    assert_supported_schema_version,
)

GRADING_ENGINE_VERSION = "1.0.0-phase29"


class ScoreErrorCode(StrEnum):
    SCORE_INCOMPLETE_RUN = "SCORE_INCOMPLETE_RUN"
    SCORE_RUBRIC_MISSING = "SCORE_RUBRIC_MISSING"
    SCORE_RUBRIC_INCOMPATIBLE = "SCORE_RUBRIC_INCOMPATIBLE"
    SCORE_INPUT_TAMPERED = "SCORE_INPUT_TAMPERED"
    SCORE_CHECKSUM_MISMATCH = "SCORE_CHECKSUM_MISMATCH"
    SCORE_NOT_FOUND = "SCORE_NOT_FOUND"
    SCORE_COMPARISON_INVALID = "SCORE_COMPARISON_INVALID"
    SCORE_EXPORT_FAILED = "SCORE_EXPORT_FAILED"
    SCORE_VALIDATION_FAILED = "SCORE_VALIDATION_FAILED"


class ScoreGradeBandV1(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    F = "F"


class DecisionReviewOutcomeV1(StrEnum):
    CREDITED = "credited"
    PENALIZED = "penalized"
    NEUTRAL = "neutral"
    RESTRAINT_CREDITED = "restraint_credited"


class ValidAlternativeKindV1(StrEnum):
    COUNTERFACTUAL = "counterfactual"
    VALID_RESPONSE_BRANCH = "valid_response_branch"
    ALTERNATIVE_DECISION = "alternative_decision"


class ScoreExportFormatV1(StrEnum):
    JSON = "json"
    MARKDOWN = "markdown"


class DecisionReviewKindV1(StrEnum):
    APPROVAL = "approval"
    REJECTION = "rejection"
    MODIFICATION = "modification"
    CANCELLATION = "cancellation"
    AGENT_RECOMMENDATION = "agent_recommendation"


class AfterActionBookmarkKindV1(StrEnum):
    DETECTION = "detection"
    EVIDENCE = "evidence"
    DECISION = "decision"
    MISSED_EVIDENCE = "missed_evidence"
    ALTERNATIVE = "alternative"
    CUSTOM = "custom"


class ScoreExplanationV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    rule_id: str = Field(alias="ruleId", min_length=1, max_length=128)
    reason: str = Field(min_length=1, max_length=2048)
    event_ids: list[EventId] = Field(default_factory=list, alias="eventIds")
    evidence_ids: list[EvidenceId] = Field(default_factory=list, alias="evidenceIds")
    decision_ids: list[str] = Field(default_factory=list, alias="decisionIds")
    hypothesis_ids: list[HypothesisId] = Field(default_factory=list, alias="hypothesisIds")
    proposal_ids: list[ProposalId] = Field(default_factory=list, alias="proposalIds")
    sequence: Sequence | None = None

    @model_validator(mode="after")
    def validate_schema_version(self) -> ScoreExplanationV1:
        assert_supported_schema_version("score_explanation", self.schema_version)
        if self.schema_version != SCORE_EXPLANATION_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported score explanation schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class ScoreRubricCriterionV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str = Field(min_length=1, max_length=128)
    label: str = Field(min_length=1, max_length=256)
    weight: float = Field(ge=0.0, le=1.0)
    description: str = Field(default="", max_length=1024)


class ScoreRubricV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    scenario_id: str = Field(alias="scenarioId", min_length=1, max_length=128)
    scenario_version: str = Field(alias="scenarioVersion", min_length=1, max_length=64)
    rubric_version: str = Field(alias="rubricVersion", min_length=1, max_length=64)
    grading_engine_version: str = Field(alias="gradingEngineVersion", min_length=1, max_length=64)
    max_score: float = Field(alias="maxScore", gt=0.0)
    criteria: list[ScoreRubricCriterionV1] = Field(min_length=1)
    rubric_text: str = Field(default="", alias="rubricText", max_length=8192)
    rubric_text_hash: str = Field(alias="rubricTextHash", min_length=1, max_length=128)

    @model_validator(mode="after")
    def validate_schema_version(self) -> ScoreRubricV1:
        assert_supported_schema_version("score_rubric", self.schema_version)
        if self.schema_version != SCORE_RUBRIC_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported score rubric schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class ScoreComponentV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    criterion_id: str = Field(alias="criterionId", min_length=1, max_length=128)
    label: str = Field(min_length=1, max_length=256)
    weight: float = Field(ge=0.0, le=1.0)
    raw_score: float = Field(alias="rawScore", ge=0.0, le=1.0)
    weighted_contribution: float = Field(alias="weightedContribution", ge=0.0)
    rule_ids: list[str] = Field(default_factory=list, alias="ruleIds")
    explanations: list[ScoreExplanationV1] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_schema_version(self) -> ScoreComponentV1:
        assert_supported_schema_version("score_component", self.schema_version)
        if self.schema_version != SCORE_COMPONENT_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported score component schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class ScoreProvenanceV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    run_id: RunId = Field(alias="runId")
    scenario_id: str = Field(alias="scenarioId", min_length=1, max_length=128)
    scenario_version: str = Field(alias="scenarioVersion", min_length=1, max_length=64)
    rubric_version: str = Field(alias="rubricVersion", min_length=1, max_length=64)
    grading_engine_version: str = Field(alias="gradingEngineVersion", min_length=1, max_length=64)
    input_event_sequence_from: Sequence = Field(alias="inputEventSequenceFrom")
    input_event_sequence_to: Sequence = Field(alias="inputEventSequenceTo")
    input_checksum: str = Field(alias="inputChecksum", min_length=1, max_length=128)
    integrity_checksum: str = Field(alias="integrityChecksum", min_length=1, max_length=128)
    calculated_at: UtcTimestamp = Field(alias="calculatedAt")
    fingerprint: str = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def validate_schema_version(self) -> ScoreProvenanceV1:
        assert_supported_schema_version("score_provenance", self.schema_version)
        if self.schema_version != SCORE_PROVENANCE_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported score provenance schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class DecisionReviewV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    decision_id: str = Field(alias="decisionId", min_length=1, max_length=128)
    kind: DecisionReviewKindV1
    sequence: Sequence
    proposal_id: ProposalId | None = Field(default=None, alias="proposalId")
    operator_action: str = Field(alias="operatorAction", min_length=1, max_length=256)
    agent_recommendation: str | None = Field(
        default=None, alias="agentRecommendation", max_length=1024
    )
    available_info_summary: str = Field(default="", alias="availableInfoSummary", max_length=2048)
    available_event_ids: list[EventId] = Field(default_factory=list, alias="availableEventIds")
    available_evidence_ids: list[EvidenceId] = Field(
        default_factory=list, alias="availableEvidenceIds"
    )
    outcome: DecisionReviewOutcomeV1
    score_delta: float = Field(alias="scoreDelta")
    rule_ids: list[str] = Field(default_factory=list, alias="ruleIds")
    explanations: list[ScoreExplanationV1] = Field(default_factory=list)
    used_future_knowledge: Literal[False] = Field(default=False, alias="usedFutureKnowledge")

    @model_validator(mode="after")
    def validate_schema_version(self) -> DecisionReviewV1:
        assert_supported_schema_version("decision_review", self.schema_version)
        if self.schema_version != DECISION_REVIEW_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported decision review schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class MissedEvidenceItemV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    expected_evidence_key: str = Field(alias="expectedEvidenceKey", min_length=1, max_length=256)
    event_type: str = Field(alias="eventType", min_length=1, max_length=128)
    asset_id: AssetId | None = Field(default=None, alias="assetId")
    description: str = Field(default="", max_length=1024)
    discovered: bool
    related_event_ids: list[EventId] = Field(default_factory=list, alias="relatedEventIds")
    related_evidence_ids: list[EvidenceId] = Field(default_factory=list, alias="relatedEvidenceIds")
    bookmark_sequence: Sequence | None = Field(default=None, alias="bookmarkSequence")

    @model_validator(mode="after")
    def validate_schema_version(self) -> MissedEvidenceItemV1:
        assert_supported_schema_version("missed_evidence_item", self.schema_version)
        if self.schema_version != MISSED_EVIDENCE_ITEM_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported missed evidence item schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class ValidAlternativeV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    alternative_id: str = Field(alias="alternativeId", min_length=1, max_length=128)
    kind: ValidAlternativeKindV1
    authoritative: Literal[False] = False
    label: str = Field(min_length=1, max_length=256)
    description: str = Field(default="", max_length=2048)
    projected_overall_score: float = Field(alias="projectedOverallScore", ge=0.0)
    score_delta: float = Field(alias="scoreDelta")
    rule_ids: list[str] = Field(default_factory=list, alias="ruleIds")
    explanations: list[ScoreExplanationV1] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_schema_version(self) -> ValidAlternativeV1:
        assert_supported_schema_version("valid_alternative", self.schema_version)
        if self.schema_version != VALID_ALTERNATIVE_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported valid alternative schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class RunScoreV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    score_id: str = Field(alias="scoreId", min_length=1, max_length=64)
    run_id: RunId = Field(alias="runId")
    incident_id: IncidentId | None = Field(default=None, alias="incidentId")
    overall_score: float = Field(alias="overallScore", ge=0.0)
    max_score: float = Field(alias="maxScore", gt=0.0)
    grade: ScoreGradeBandV1
    passed: bool
    components: list[ScoreComponentV1] = Field(min_length=1)
    provenance: ScoreProvenanceV1
    decision_reviews: list[DecisionReviewV1] = Field(default_factory=list, alias="decisionReviews")
    missed_evidence: list[MissedEvidenceItemV1] = Field(
        default_factory=list, alias="missedEvidence"
    )
    valid_alternatives: list[ValidAlternativeV1] = Field(
        default_factory=list, alias="validAlternatives"
    )
    coaching_text: str | None = Field(default=None, alias="coachingText", max_length=8192)
    coaching_authoritative: Literal[False] = Field(default=False, alias="coachingAuthoritative")
    hidden_cause_id: str | None = Field(default=None, alias="hiddenCauseId", max_length=128)
    hidden_cause_label: str | None = Field(default=None, alias="hiddenCauseLabel", max_length=256)
    hidden_cause_revealed: bool = Field(default=False, alias="hiddenCauseRevealed")

    @model_validator(mode="after")
    def validate_schema_version(self) -> RunScoreV1:
        assert_supported_schema_version("run_score", self.schema_version)
        if self.schema_version != RUN_SCORE_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported run score schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class AfterActionBookmarkRefV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    label: str = Field(min_length=1, max_length=256)
    sequence: Sequence
    kind: AfterActionBookmarkKindV1
    related_id: str | None = Field(default=None, alias="relatedId", max_length=128)


class AfterActionTimelineHighlightV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    sequence: Sequence
    label: str = Field(min_length=1, max_length=512)
    kind: str = Field(min_length=1, max_length=64)
    related_id: str | None = Field(default=None, alias="relatedId", max_length=128)


class AfterActionViewModelV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    run_id: RunId = Field(alias="runId")
    run_status: str = Field(alias="runStatus", min_length=1, max_length=64)
    score: RunScoreV1
    affected_asset_ids: list[AssetId] = Field(default_factory=list, alias="affectedAssetIds")
    lessons: list[str] = Field(default_factory=list)
    scribe_report_id: str | None = Field(default=None, alias="scribeReportId", max_length=64)
    scribe_version_number: int | None = Field(default=None, alias="scribeVersionNumber", ge=1)
    bookmarks: list[AfterActionBookmarkRefV1] = Field(default_factory=list)
    timeline_highlights: list[AfterActionTimelineHighlightV1] = Field(
        default_factory=list, alias="timelineHighlights"
    )

    @model_validator(mode="after")
    def validate_schema_version(self) -> AfterActionViewModelV1:
        assert_supported_schema_version("after_action_view_model", self.schema_version)
        if self.schema_version != AFTER_ACTION_VIEW_MODEL_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported after-action view model schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class RunComparisonComponentDeltaV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    criterion_id: str = Field(alias="criterionId", min_length=1, max_length=128)
    left_raw_score: float = Field(alias="leftRawScore", ge=0.0, le=1.0)
    right_raw_score: float = Field(alias="rightRawScore", ge=0.0, le=1.0)
    delta: float


class RunComparisonV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    left_run_id: RunId = Field(alias="leftRunId")
    right_run_id: RunId = Field(alias="rightRunId")
    left_score_id: str = Field(alias="leftScoreId", min_length=1, max_length=64)
    right_score_id: str = Field(alias="rightScoreId", min_length=1, max_length=64)
    left_overall_score: float = Field(alias="leftOverallScore", ge=0.0)
    right_overall_score: float = Field(alias="rightOverallScore", ge=0.0)
    overall_delta: float = Field(alias="overallDelta")
    component_deltas: list[RunComparisonComponentDeltaV1] = Field(
        default_factory=list, alias="componentDeltas"
    )
    grading_engine_version: str = Field(alias="gradingEngineVersion", min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_schema_version(self) -> RunComparisonV1:
        assert_supported_schema_version("run_comparison", self.schema_version)
        if self.schema_version != RUN_COMPARISON_SCORE_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported run comparison schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class ScoreExportArtifactV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    export_id: str = Field(alias="exportId", min_length=1, max_length=64)
    score_id: str = Field(alias="scoreId", min_length=1, max_length=64)
    run_id: RunId = Field(alias="runId")
    format: ScoreExportFormatV1
    scenario_version: str = Field(alias="scenarioVersion", min_length=1, max_length=64)
    rubric_version: str = Field(alias="rubricVersion", min_length=1, max_length=64)
    grading_engine_version: str = Field(alias="gradingEngineVersion", min_length=1, max_length=64)
    integrity_checksum: str = Field(alias="integrityChecksum", min_length=1, max_length=128)
    content_checksum: str = Field(alias="contentChecksum", min_length=1, max_length=128)
    created_at: UtcTimestamp = Field(alias="createdAt")

    @model_validator(mode="after")
    def validate_schema_version(self) -> ScoreExportArtifactV1:
        assert_supported_schema_version("score_export_artifact", self.schema_version)
        if self.schema_version != SCORE_EXPORT_ARTIFACT_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported score export artifact schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self
