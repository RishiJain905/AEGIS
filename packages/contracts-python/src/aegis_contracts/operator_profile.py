"""Operator skill-telemetry profile contracts.

A cross-run, read-only aggregation of the operator's own habits, computed on demand
from persisted run data (events, alerts, actions, scores). No new tables; capped to a
recent window of the caller's terminal runs. The metrics and coaching lines are all
deterministic heuristics — clearly non-authoritative — surfaced between runs so the
operator can see patterns in their speed, bias, and containment discipline.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aegis_contracts.errors import ContractErrorCode, ContractValidationError
from aegis_contracts.versioning import (
    OPERATOR_PROFILE_SCHEMA_VERSION,
    assert_supported_schema_version,
)

# Coaching tone: reinforce a good habit, suggest an improvement, or a neutral observation.
CoachingTone = Literal["reinforce", "improve", "neutral"]


class OperatorRunSummaryV1(BaseModel):
    """Per-run derived metrics for one of the operator's terminal runs.

    Timing metrics are measured in event-sequence units (the monotonic run event
    sequence) — an ordinal, always-present, deterministic proxy for latency that is
    comparable across runs of different lengths. ``None`` means the metric was not
    derivable for that run (e.g. no alert ever fired, or no containment executed).
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    run_id: str = Field(alias="runId", min_length=1)
    scenario_id: str = Field(alias="scenarioId")
    seed: int
    status: str
    started_at: str = Field(alias="startedAt")
    # Overall run score as a fraction in [0,1] (overallScore / maxScore); None when the
    # run was never scored.
    score: float | None = Field(default=None, ge=0.0, le=1.0)
    # Events between the first alert and the first agent task after it.
    time_to_first_triage: float | None = Field(default=None, alias="timeToFirstTriage", ge=0.0)
    # Events between the first alert and the first executed class>=2 containment after it.
    containment_latency: float | None = Field(default=None, alias="containmentLatency", ge=0.0)
    # Role of the first agent tasked after the first alert (e.g. "TRACE"); None if none.
    first_agent_role: str | None = Field(default=None, alias="firstAgentRole")
    # Count of executed class 2/3 (aggressive) containment actions in the run.
    aggressive_action_count: int = Field(default=0, alias="aggressiveActionCount", ge=0)
    # Of those, how many hit an asset not on the known attack path. None when the attack
    # path is unknown for the run (no hidden-condition reveal), so over-containment is
    # not judgeable and the run is excluded from the ratio.
    over_containment_count: int | None = Field(
        default=None, alias="overContainmentCount", ge=0
    )
    hypothesis_count: int = Field(default=0, alias="hypothesisCount", ge=0)
    false_hypothesis_count: int = Field(default=0, alias="falseHypothesisCount", ge=0)

    @model_validator(mode="after")
    def validate_schema_version(self) -> OperatorRunSummaryV1:
        return self


class OperatorProfileMetricsV1(BaseModel):
    """Aggregate metrics across the analyzed runs. Averages skip runs where the
    underlying per-run metric is ``None``; a field is ``None`` when no run supplied it."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    runs_analyzed: int = Field(alias="runsAnalyzed", ge=0)
    avg_time_to_first_triage: float | None = Field(
        default=None, alias="avgTimeToFirstTriage", ge=0.0
    )
    avg_containment_latency: float | None = Field(
        default=None, alias="avgContainmentLatency", ge=0.0
    )
    # Fraction of executed aggressive actions that hit off-path assets, over runs where
    # the attack path is known. None when no such run exists.
    over_containment_ratio: float | None = Field(
        default=None, alias="overContainmentRatio", ge=0.0, le=1.0
    )
    # Fraction of the operator's hypotheses that were refuted/abandoned. None when the
    # operator raised no hypotheses across the window.
    false_hypothesis_rate: float | None = Field(
        default=None, alias="falseHypothesisRate", ge=0.0, le=1.0
    )
    avg_score: float | None = Field(default=None, alias="avgScore", ge=0.0, le=1.0)
    # Per-run overall score fraction, oldest to newest, for a trend sparkline.
    score_trend: list[float] = Field(default_factory=list, alias="scoreTrend")


class CoachingLineV1(BaseModel):
    """A single deterministic, template-generated coaching observation."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str = Field(min_length=1)
    tone: CoachingTone
    message: str = Field(min_length=1, max_length=400)


class OperatorProfileV1(BaseModel):
    """The operator's cross-run skill-telemetry profile (owner-scoped, on-demand)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(
        default=OPERATOR_PROFILE_SCHEMA_VERSION, alias="schemaVersion", ge=1
    )
    owner_user_id: str = Field(alias="ownerUserId", min_length=1)
    generated_at: str = Field(alias="generatedAt")
    metrics: OperatorProfileMetricsV1
    runs: list[OperatorRunSummaryV1] = Field(default_factory=list)
    coaching: list[CoachingLineV1] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_schema_version(self) -> OperatorProfileV1:
        assert_supported_schema_version("operator_profile", self.schema_version)
        if self.schema_version != OPERATOR_PROFILE_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported operator profile schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self
